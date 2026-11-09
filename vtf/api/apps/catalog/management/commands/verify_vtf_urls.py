"""Management command: verify_vtf_urls.

Hits each village's constructed VTF URL and records whether it returns 200.
Updates `vtf_url_verified_at` on success. Prints a summary table.

Required by the PDF roadmap:
  "Action required: Before Phase 1 deploy, manually verify each slug by
   loading the constructed URL in a browser. Script: python manage.py
   verify_vtf_urls (hits each URL, checks for 200)."

Usage:
    python manage.py verify_vtf_urls
    python manage.py verify_vtf_urls --season ete        # default: ete
    python manage.py verify_vtf_urls --timeout 10        # seconds per request
    python manage.py verify_vtf_urls --only-unverified   # skip already-verified
    python manage.py verify_vtf_urls --fix-slugs         # update slug from redirect
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone as dj_timezone

from apps.catalog.models import Village

logger = logging.getLogger(__name__)

# VTF URL template — uses English season segment + hyphenated "village-vacances"
# Confirmed from live site: /fr_FR/summer/village-vacances/{dept}/{city}/{slug}
VTF_URL_TEMPLATE = (
    "https://www.vtf-vacances.com/fr_FR/{season}/village-vacances"
    "/{department}/{city}/{slug}"
)

# Season key → VTF URL segment mapping (French key → English URL word)
SEASON_MAP = {
    "ete": "summer",
    "hiver": "winter",
    "vs": "winter",      # vacances scolaires (Feb/ski) → winter
    "hs": "summer",      # hors saison default → summer
    "toussaint": "winter",
    "noel": "winter",
    "printemps": "summer",
    "paques": "summer",
}

# Accepted CLI season values
SEASONS = list(SEASON_MAP.keys())


class Command(BaseCommand):
    help = (
        "Verify each village's VTF URL returns HTTP 200. "
        "Updates vtf_url_verified_at on success. "
        "Required pre-Phase-1 deploy check."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--season",
            default="ete",
            choices=SEASONS,
            help="Season segment in the VTF URL (default: ete)",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=8,
            help="HTTP timeout per request in seconds (default: 8)",
        )
        parser.add_argument(
            "--only-unverified",
            action="store_true",
            help="Skip villages that already have vtf_url_verified_at set",
        )
        parser.add_argument(
            "--village",
            dest="village_ids",
            nargs="+",
            metavar="ID",
            help="Only check specific village IDs (e.g. biarritz lacanau)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print URLs that would be checked without making requests",
        )

    def handle(self, *args, **options):
        season = options["season"]
        timeout = options["timeout"]
        only_unverified = options["only_unverified"]
        village_ids = options.get("village_ids")
        dry_run = options["dry_run"]
        logger.info(
            "catalog_verify_vtf_urls_started season=%s timeout=%s only_unverified=%s villages=%s dry_run=%s",
            season,
            timeout,
            only_unverified,
            village_ids or [],
            dry_run,
        )

        qs = Village.objects.all().order_by("region", "nom")
        if village_ids:
            qs = qs.filter(pk__in=village_ids)
        if only_unverified:
            qs = qs.filter(vtf_url_verified_at__isnull=True)

        villages = list(qs)
        if not villages:
            logger.warning("catalog_verify_vtf_urls_no_villages")
            self.stdout.write(self.style.WARNING("No villages to check."))
            return

        self.stdout.write(
            self.style.HTTP_INFO(
                f"\n{'DRY RUN — ' if dry_run else ''}"
                f"Verifying {len(villages)} village URL(s) "
                f"[season={season}, timeout={timeout}s]\n"
                + "─" * 80
            )
        )

        results: list[dict] = []
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "VTF-URLVerifier/1.0 (pre-deploy check; "
                    "contact: admin@vtf-vacances.com)"
                )
            }
        )

        for village in villages:
            url = self._build_url(village, season)
            row: dict = {
                "id": village.pk,
                "nom": village.nom,
                "url": url,
                "status": None,
                "ok": False,
                "error": None,
                "redirect_to": None,
                "elapsed_ms": None,
            }

            if not village.vtf_department or not village.vtf_city or not village.vtf_slug:
                row["status"] = "SKIP"
                row["error"] = "Missing vtf_department / vtf_city / vtf_slug"
                results.append(row)
                logger.warning(
                    "catalog_verify_vtf_urls_skipped village_id=%s reason=%s",
                    village.pk,
                    row["error"],
                )
                self._print_row(row)
                continue

            if dry_run:
                row["status"] = "DRY"
                results.append(row)
                self._print_row(row)
                continue

            try:
                t0 = time.monotonic()
                resp = session.get(url, timeout=timeout, allow_redirects=True)
                elapsed = int((time.monotonic() - t0) * 1000)
                row["elapsed_ms"] = elapsed
                row["status"] = resp.status_code

                # Record final URL if we followed redirects
                if resp.url and resp.url != url:
                    row["redirect_to"] = resp.url

                if resp.status_code == 200:
                    row["ok"] = True
                    # Persist verification timestamp
                    Village.objects.filter(pk=village.pk).update(
                        vtf_url_verified_at=dj_timezone.now()
                    )
                else:
                    row["error"] = f"HTTP {resp.status_code}"
                    logger.warning(
                        "catalog_verify_vtf_urls_http_failed village_id=%s status=%s url=%s",
                        village.pk,
                        resp.status_code,
                        url,
                    )

            except requests.exceptions.Timeout:
                row["status"] = "TIMEOUT"
                row["error"] = f"No response within {timeout}s"
                logger.warning(
                    "catalog_verify_vtf_urls_timeout village_id=%s timeout=%s url=%s",
                    village.pk,
                    timeout,
                    url,
                )
            except requests.exceptions.ConnectionError as exc:
                row["status"] = "CONN_ERR"
                row["error"] = str(exc)[:80]
                logger.warning(
                    "catalog_verify_vtf_urls_connection_error village_id=%s error=%s",
                    village.pk,
                    row["error"],
                )
            except Exception as exc:  # noqa: BLE001
                row["status"] = "ERROR"
                row["error"] = str(exc)[:80]
                logger.exception(
                    "catalog_verify_vtf_urls_unexpected_error village_id=%s url=%s",
                    village.pk,
                    url,
                )

            results.append(row)
            self._print_row(row)

            # Polite crawl delay
            time.sleep(0.4)

        self._print_summary(results, dry_run)
        ok = sum(1 for row in results if row["ok"])
        failed = sum(1 for row in results if not row["ok"] and row["status"] not in ("SKIP", "DRY"))
        skipped = sum(1 for row in results if row["status"] == "SKIP")
        logger.info(
            "catalog_verify_vtf_urls_done checked=%d ok=%d failed=%d skipped=%d dry_run=%s",
            len(results),
            ok,
            failed,
            skipped,
            dry_run,
        )

    # ─── helpers ──────────────────────────────────────────────────────────

    def _build_url(self, village: Village, season: str) -> str:
        # Translate French season key (e.g. "ete") to English URL segment (e.g. "summer")
        season_segment = SEASON_MAP.get(season, "summer")
        return VTF_URL_TEMPLATE.format(
            season=season_segment,
            department=village.vtf_department or "",
            city=village.vtf_city or "",
            slug=village.vtf_slug or "",
        )

    def _print_row(self, row: dict) -> None:
        status = str(row["status"] or "?")
        nom = f"{row['id']:<20} {row['nom']:<28}"
        elapsed = f"{row['elapsed_ms']}ms" if row["elapsed_ms"] is not None else ""

        if row["status"] == "DRY":
            self.stdout.write(f"  {'DRY':>7}  {nom}  {row['url']}")
        elif row["ok"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {'200':>7} ✅  {nom}  {elapsed}"
                )
            )
            if row["redirect_to"]:
                self.stdout.write(
                    f"           ↳  redirected to {row['redirect_to']}"
                )
        elif row["status"] == "SKIP":
            self.stdout.write(
                self.style.WARNING(f"  {'SKIP':>7} ⚠️   {nom}  {row['error']}")
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"  {status:>7} ❌  {nom}  {row['error'] or ''}"
                )
            )
            self.stdout.write(f"           URL: {row['url']}")

    def _print_summary(self, results: list[dict], dry_run: bool) -> None:
        if dry_run:
            self.stdout.write("\n" + "─" * 80)
            self.stdout.write(f"Dry run — {len(results)} URL(s) would be checked.")
            return

        ok = [r for r in results if r["ok"]]
        fail = [r for r in results if not r["ok"] and r["status"] not in ("SKIP", "DRY")]
        skip = [r for r in results if r["status"] == "SKIP"]

        self.stdout.write("\n" + "─" * 80)
        self.stdout.write(
            self.style.SUCCESS(f"✅  OK      : {len(ok)}")
            + "   "
            + (self.style.ERROR(f"❌  FAILED  : {len(fail)}") if fail else f"❌  FAILED  : 0")
            + "   "
            + self.style.WARNING(f"⚠️   SKIPPED : {len(skip)}")
        )

        if fail:
            self.stdout.write(
                self.style.ERROR(
                    "\nFailed villages (fix slugs in fixtures before deploy):"
                )
            )
            for r in fail:
                self.stdout.write(f"  • {r['id']:<20} {r['status']}  {r['url']}")

        if ok:
            self.stdout.write(
                self.style.SUCCESS(
                    "\nAll green villages have vtf_url_verified_at updated in the DB."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\nNo URLs verified. Check your internet connection or slug values."
                )
            )
