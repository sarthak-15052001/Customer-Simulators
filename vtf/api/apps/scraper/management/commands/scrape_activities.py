"""Management command: scrape_activities

Usage:
  python manage.py scrape_activities --village=biarritz
  python manage.py scrape_activities --all --notify
  python manage.py scrape_activities --village=chamonix --sources=google_places,tripadvisor
  python manage.py scrape_activities --region="Alpes / Savoie"

Spec §US-5.4, §US-5.6.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Scrape activities for a village or all 33 VTF villages."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--village",
            metavar="VILLAGE_ID",
            help="Scrape one specific village (e.g. biarritz).",
        )
        group.add_argument(
            "--region",
            metavar="REGION_KEY",
            help="Scrape all villages in a region.",
        )
        group.add_argument(
            "--all",
            action="store_true",
            dest="all_villages",
            help="Scrape all 33 villages (monthly cron target).",
        )

        parser.add_argument(
            "--sources",
            default="google_places,tripadvisor,ot_local",
            help="Comma-separated list of sources (default: all three).",
        )
        parser.add_argument(
            "--radius",
            type=int,
            default=30,
            help="Search radius in km (default: 30).",
        )
        parser.add_argument(
            "--max-results",
            type=int,
            default=50,
            help="Max results per source per village (default: 50).",
        )
        parser.add_argument(
            "--notify",
            action="store_true",
            help="Send Discord notification after scraping completes.",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run synchronously (no Celery). Useful for testing.",
        )

    def handle(self, *args, **options):
        from apps.catalog.models import Village
        from apps.scraper.models import ScrapingJob
        from apps.scraper.pipeline import run_scraping_job

        sources = [s.strip() for s in options["sources"].split(",") if s.strip()]
        radius_km = options["radius"]
        max_results = options["max_results"]
        use_sync = options["sync"]
        do_notify = options["notify"]

        # Determine target villages
        village_ids: list[str] = []
        if options["village"]:
            village_ids = [options["village"]]
        elif options["region"]:
            qs = Village.objects.filter(region__icontains=options["region"])
            village_ids = list(qs.values_list("id", flat=True))
            if not village_ids:
                raise CommandError(f"No villages found for region: {options['region']}")
        elif options["all_villages"]:
            village_ids = list(Village.objects.values_list("id", flat=True))

        self.stdout.write(
            f"Scraping {len(village_ids)} village(s) using sources: {sources}"
        )

        job_ids: list[str] = []
        total_new = 0

        for village_id in village_ids:
            ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
            job_id = f"scrape-{village_id}-{ts}"

            job = ScrapingJob.objects.create(
                id=job_id,
                target_type="village",
                target_id=village_id,
                sources=sources,
                radius_km=radius_km,
                max_results=max_results,
                status="queued",
                triggered_by="management:scrape_activities",
            )

            if use_sync:
                from django.utils import timezone as dj_tz
                job.status = "running"
                job.started_at = dj_tz.now()
                job.save(update_fields=["status", "started_at"])
                try:
                    result = run_scraping_job(job)
                    job.status = "completed"
                    job.result_summary = result
                    job.completed_at = dj_tz.now()
                    job.save(update_fields=["status", "result_summary", "completed_at"])
                    new_count = result.get("totalNew", 0)
                    total_new += new_count
                    self.stdout.write(
                        f"  ✓ {village_id}: {new_count} new candidates"
                    )
                except Exception as exc:
                    job.status = "failed"
                    job.save(update_fields=["status"])
                    self.stderr.write(f"  ✗ {village_id}: {exc}")
            else:
                from apps.scraper.tasks import task_run_scraping_job
                task_run_scraping_job.delay(job_id)
                self.stdout.write(f"  → Queued job {job_id}")

            job_ids.append(job_id)

        if use_sync:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Scraping complete. Total new candidates: {total_new}"
                )
            )

            if do_notify:
                from apps.scraper.tasks import task_notify_scraping
                task_notify_scraping.apply(kwargs={"job_ids": job_ids, "trigger": "management_command"})
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Queued {len(job_ids)} scraping jobs. Use --sync for synchronous execution."
                )
            )