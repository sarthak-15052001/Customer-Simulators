"""Management command: verify_ot_urls.

Validates Office de Tourisme URLs used by the ot_local scraper:
  1. Every catalog village has a configured OT URL in VTF_OT_URLS.
  2. Each URL responds with HTTP 2xx/3xx (reachable tourism site).

Usage:
    python manage.py verify_ot_urls
    python manage.py verify_ot_urls --timeout 12
    python manage.py verify_ot_urls --village biarritz chamonix
    python manage.py verify_ot_urls --only-missing
    python manage.py verify_ot_urls --dry-run
"""
from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import urlparse

import requests
from django.core.management.base import BaseCommand

from apps.catalog.models import Village
from apps.scraper.services.ot_urls import VTF_OT_URLS

logger = logging.getLogger(__name__)

_ACCEPTABLE_STATUS = {200, 201, 202, 203, 204, 301, 302, 303, 307, 308}


class Command(BaseCommand):
    help = (
        "Verify OT (Office de Tourisme) URLs for all catalog villages. "
        "Reports missing mappings and unreachable sites."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=10,
            help="HTTP timeout per request in seconds (default: 10)",
        )
        parser.add_argument(
            "--village",
            dest="village_ids",
            nargs="+",
            metavar="ID",
            help="Only check specific village IDs (e.g. biarritz chamonix)",
        )
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Only report villages without an OT URL configured",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print URLs that would be checked without making HTTP requests",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        village_ids = options.get("village_ids")
        only_missing = options["only_missing"]
        dry_run = options["dry_run"]

        qs = Village.objects.all().order_by("region", "nom")
        if village_ids:
            qs = qs.filter(pk__in=village_ids)
        villages = list(qs)

        if not villages:
            self.stdout.write(self.style.WARNING("No villages to check."))
            return

        catalog_ids = {v.id for v in villages}
        extra_urls = set(VTF_OT_URLS) - catalog_ids
        missing_urls = catalog_ids - set(VTF_OT_URLS)

        self.stdout.write(
            f"Catalog villages: {len(catalog_ids)} | "
            f"OT URLs configured: {len(VTF_OT_URLS)}"
        )

        if missing_urls:
            self.stdout.write(
                self.style.ERROR(
                    f"Missing OT URLs ({len(missing_urls)}): "
                    f"{', '.join(sorted(missing_urls))}"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("All catalog villages have OT URLs."))

        if extra_urls:
            self.stdout.write(
                self.style.WARNING(
                    f"OT URLs without catalog village ({len(extra_urls)}): "
                    f"{', '.join(sorted(extra_urls))}"
                )
            )

        if only_missing:
            if not missing_urls:
                self.stdout.write(self.style.SUCCESS("Nothing missing."))
            return

        ok = 0
        failed = 0
        skipped = 0

        self.stdout.write("")
        self.stdout.write(f"{'VILLAGE':<22} {'STATUS':<8} {'URL'}")
        self.stdout.write("-" * 90)

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; VTF-Scraper-Verify/1.0; "
                    "+https://vtf-vacances.com)"
                ),
                "Accept-Language": "fr-FR,fr;q=0.9",
            }
        )

        for village in villages:
            ot_url = VTF_OT_URLS.get(village.id, "")
            if not ot_url:
                self.stdout.write(
                    f"{village.id:<22} {'MISSING':<8} (no OT URL configured)"
                )
                failed += 1
                continue

            if dry_run:
                self.stdout.write(f"{village.id:<22} {'DRY-RUN':<8} {ot_url}")
                skipped += 1
                continue

            status_label, detail = self._check_url(session, ot_url, timeout)
            if status_label == "OK":
                ok += 1
                style = self.style.SUCCESS
            else:
                failed += 1
                style = self.style.ERROR

            self.stdout.write(style(f"{village.id:<22} {status_label:<8} {detail}"))

        self.stdout.write("")
        self.stdout.write(
            f"Done: {ok} OK, {failed} failed, {skipped} skipped "
            f"(timeout={timeout}s, dry_run={dry_run})"
        )
        logger.info(
            "scraper_verify_ot_urls_done ok=%d failed=%d skipped=%d villages=%d",
            ok,
            failed,
            skipped,
            len(villages),
        )

    def _check_url(
        self,
        session: requests.Session,
        url: str,
        timeout: int,
    ) -> tuple[str, str]:
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
            final_url = response.url
            if response.status_code in _ACCEPTABLE_STATUS:
                host = urlparse(final_url).netloc or urlparse(url).netloc
                if final_url.rstrip("/") != url.rstrip("/"):
                    return "OK", f"{url} → {host} ({response.status_code})"
                return "OK", f"{url} ({response.status_code})"
            return "FAIL", f"{url} HTTP {response.status_code}"
        except requests.Timeout:
            return "TIMEOUT", url
        except requests.ConnectionError as exc:
            return "ERR", f"{url} ({exc.__class__.__name__})"
        except requests.RequestException as exc:
            return "ERR", f"{url} ({exc})"
