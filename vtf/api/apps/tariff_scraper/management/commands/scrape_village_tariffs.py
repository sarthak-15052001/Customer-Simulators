"""Scrape VTF village tarifs synchronously (or queue via Celery).

Usage:
  python manage.py scrape_village_tariffs --village lacanau
  python manage.py scrape_village_tariffs --village lacanau --dry-run
  python manage.py scrape_village_tariffs --all
  python manage.py scrape_village_tariffs --village lacanau --async

Compares scraped adult/unit weekly rates to fixture season buckets when
``--compare-fixtures`` is set (useful to quantify website parity drift).
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from apps.tariff_scraper.services.village_urls import VILLAGE_URLS, get_village_url


class Command(BaseCommand):
    help = (
        "Scrape live VTF tarifs for one or all villages and stage a pending "
        "TariffApproval (activate via admin API after review)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--village",
            type=str,
            default="",
            help="Catalog Village.id (e.g. lacanau). Required unless --all.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Scrape every village in VILLAGE_URLS.",
        )
        parser.add_argument(
            "--async",
            dest="use_async",
            action="store_true",
            help="Queue Celery tasks instead of scraping in-process.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Scrape and print bands without writing to the DB.",
        )
        parser.add_argument(
            "--compare-fixtures",
            action="store_true",
            help="After scrape, print scraped vs fixture season-bucket prices.",
        )

    def handle(self, *args, **options):
        village_id = (options.get("village") or "").strip()
        scrape_all = options["all"]
        use_async = options["use_async"]
        dry_run = options["dry_run"]
        compare = options["compare_fixtures"]

        if scrape_all and village_id:
            raise CommandError("Use either --village or --all, not both.")
        if not scrape_all and not village_id:
            raise CommandError("Provide --village <id> or --all.")

        village_ids = list(VILLAGE_URLS.keys()) if scrape_all else [village_id]

        if use_async:
            from apps.tariff_scraper.tasks import (
                task_scrape_all_village_tariffs,
                task_scrape_village_tariffs,
            )

            if scrape_all:
                result = task_scrape_all_village_tariffs.delay()
                self.stdout.write(self.style.SUCCESS(f"Queued all villages: task_id={result.id}"))
            else:
                if village_id not in VILLAGE_URLS and not get_village_url(village_id):
                    raise CommandError(f"Unknown village_id '{village_id}'")
                result = task_scrape_village_tariffs.delay(village_id)
                self.stdout.write(
                    self.style.SUCCESS(f"Queued '{village_id}': task_id={result.id}")
                )
            return

        from apps.tariff_scraper.services.scraper import scrape_village
        from apps.tariff_scraper.services.tarif_builder import build_tarifs_from_scrape

        for vid in village_ids:
            url = get_village_url(vid)
            if not url:
                self.stderr.write(self.style.ERROR(f"No URL for '{vid}' — skip"))
                continue

            self.stdout.write(f"Scraping {vid} …\n  {url}")
            scrape = scrape_village(vid, url)

            if scrape.errors:
                for err in scrape.errors:
                    self.stderr.write(self.style.WARNING(f"  scrape warning: {err}"))

            self._print_bands(scrape.bands)

            if dry_run:
                self.stdout.write(self.style.WARNING("  dry-run: DB not updated"))
            else:
                build = build_tarifs_from_scrape(scrape)
                if build.errors:
                    for err in build.errors:
                        self.stderr.write(self.style.ERROR(f"  build error: {err}"))
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  snapshots={build.snapshots_created} "
                            f"approval_id={build.approval_id} "
                            f"bands_proposed={build.bands_proposed} "
                            f"(pending admin approve)"
                        )
                    )

            if compare:
                self._compare_fixtures(vid, scrape.bands)

    def _print_bands(self, bands) -> None:
        if not bands:
            self.stdout.write(self.style.WARNING("  no bands found"))
            return
        for b in bands:
            price = f"{b.scraped_price}€" if b.scraped_price is not None else "n/a"
            avail = "OK" if b.is_available else "INDISP"
            unit = f" [{b.unit_type}]" if b.unit_type else ""
            self.stdout.write(
                f"  {b.formule:3} {avail:6} {b.date_start}->{b.date_end} "
                f"{price}{unit} ({b.source_page})"
            )

    def _compare_fixtures(self, village_id: str, bands) -> None:
        """Show how date-band website prices differ from season-bucket fixtures."""
        try:
            from apps.catalog.models import Village
            from apps.pricing.services.calendar import saison_key
        except Exception as exc:
            self.stderr.write(f"  compare skipped: {exc}")
            return

        village = Village.objects.filter(pk=village_id).first()
        if not village or not village.tarifs:
            self.stdout.write("  compare: no fixture tarifs")
            return

        tarifs = village.tarifs
        self.stdout.write("  --- fixture vs scraped (adult/cheap unit weekly) ---")

        by_formule: dict[str, list] = {}
        for b in bands:
            if not b.is_available or b.scraped_price is None or not b.date_start:
                continue
            by_formule.setdefault(b.formule, []).append(b)

        for formule, form_bands in sorted(by_formule.items()):
            fixture_map = tarifs.get(formule) or (
                tarifs.get("PC") if formule == "DP" else {}
            ) or {}
            # Prefer cheapest unit for LOC when comparing “à partir de”
            samples: dict[str, Decimal] = {}
            for b in form_bands:
                if formule == "LOC":
                    sk = saison_key(b.date_start)
                    prev = samples.get(sk)
                    if prev is None or b.scraped_price < prev:
                        samples[sk] = b.scraped_price
                else:
                    sk = saison_key(b.date_start)
                    # Keep first adult PC/DP band price seen for that season key
                    samples.setdefault(sk, b.scraped_price)

            for sk in ("hs", "vs", "ete", "fetes"):
                fixture_price = fixture_map.get(sk)
                scraped_price = samples.get(sk)
                if fixture_price is None and scraped_price is None:
                    continue
                delta = ""
                if fixture_price is not None and scraped_price is not None:
                    d = float(scraped_price) - float(fixture_price)
                    delta = f"  Δ={d:+.0f}€"
                self.stdout.write(
                    f"  {formule}/{sk}: fixture={fixture_price}  "
                    f"scraped≈{scraped_price}{delta}"
                )
