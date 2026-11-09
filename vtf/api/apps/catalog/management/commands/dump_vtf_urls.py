"""Management command: dump_vtf_urls.

Reads vtf_department, vtf_city, vtf_slug, and vtf_url_verified_at from the
live database and writes them back into the villages.json fixture so the
fixture stays in sync with what verify_vtf_urls confirmed.

Run this after verify_vtf_urls has updated the DB:

    python manage.py verify_vtf_urls --timeout 15
    python manage.py dump_vtf_urls

The fixture is the canonical seed for fresh deployments. Without this step,
a fresh `load_vtf_mocks` would load empty slugs and booking URLs would fall
back to the VTF homepage (AC-1.12).

Usage:
    python manage.py dump_vtf_urls
    python manage.py dump_vtf_urls --fixture path/to/villages.json   # custom path
    python manage.py dump_vtf_urls --dry-run                         # preview only
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.catalog.models import Village

logger = logging.getLogger(__name__)

# Default fixture path — relative to manage.py (i.e. vtf/api/)
DEFAULT_FIXTURE = Path(__file__).resolve().parents[4] / "apps" / "catalog" / "fixtures" / "villages.json"


class Command(BaseCommand):
    help = (
        "Sync vtf_department / vtf_city / vtf_slug from the DB back into "
        "villages.json so the fixture always reflects verified URL data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture",
            default=str(DEFAULT_FIXTURE),
            help=f"Path to villages.json fixture (default: {DEFAULT_FIXTURE})",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would change without writing to disk.",
        )

    def handle(self, *args, **options):
        fixture_path = Path(options["fixture"])
        dry_run = options["dry_run"]
        logger.info(
            "catalog_dump_vtf_urls_started fixture=%s dry_run=%s",
            fixture_path,
            dry_run,
        )

        if not fixture_path.exists():
            logger.error("catalog_dump_vtf_urls_fixture_missing fixture=%s", fixture_path)
            self.stderr.write(
                self.style.ERROR(f"Fixture not found: {fixture_path}")
            )
            raise SystemExit(1)

        # Load current fixture
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))

        # Build lookup from DB — only villages that have been verified
        db_villages = Village.objects.all().values(
            "id", "vtf_department", "vtf_city", "vtf_slug", "vtf_url_verified_at"
        )
        db_map = {v["id"]: v for v in db_villages}

        updated = 0
        unchanged = 0
        missing_in_db = []

        for row in raw:
            if row.get("model") != "catalog.village":
                continue

            pk = row["pk"]
            db = db_map.get(pk)

            if db is None:
                missing_in_db.append(pk)
                continue

            fields = row["fields"]
            changed = False

            for field in ("vtf_department", "vtf_city", "vtf_slug"):
                db_val = db[field] or ""
                if fields.get(field, "") != db_val:
                    if dry_run:
                        self.stdout.write(
                            f"  ~ {pk:<25} {field}: "
                            f"{fields.get(field)!r} → {db_val!r}"
                        )
                    fields[field] = db_val
                    changed = True

            # Sync vtf_url_verified_at (store as ISO string or null)
            verified_at = db.get("vtf_url_verified_at")
            db_verified_str = verified_at.isoformat() if verified_at else None
            if fields.get("vtf_url_verified_at") != db_verified_str:
                fields["vtf_url_verified_at"] = db_verified_str
                changed = True

            if changed:
                updated += 1
            else:
                unchanged += 1

        if missing_in_db:
            logger.warning(
                "catalog_dump_vtf_urls_missing_in_db count=%d ids=%s",
                len(missing_in_db),
                missing_in_db[:20],
            )
            self.stdout.write(
                self.style.WARNING(
                    f"Villages in fixture but not in DB (skipped): "
                    + ", ".join(missing_in_db)
                )
            )

        if dry_run:
            logger.info(
                "catalog_dump_vtf_urls_dry_run_done updated=%d unchanged=%d missing=%d",
                updated,
                unchanged,
                len(missing_in_db),
            )
            self.stdout.write(
                self.style.HTTP_INFO(
                    f"\nDry run — {updated} village(s) would be updated, "
                    f"{unchanged} already in sync."
                )
            )
            return

        if updated == 0:
            logger.info(
                "catalog_dump_vtf_urls_done updated=0 unchanged=%d missing=%d",
                unchanged,
                len(missing_in_db),
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Already in sync — {unchanged} village(s) unchanged."
                )
            )
            return

        # Write back to fixture
        fixture_path.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"✅  Updated {updated} village(s) in {fixture_path.name} "
                f"({unchanged} unchanged)."
            )
        )
        logger.info(
            "catalog_dump_vtf_urls_done updated=%d unchanged=%d missing=%d fixture=%s",
            updated,
            unchanged,
            len(missing_in_db),
            fixture_path,
        )
