"""Management command: review_scraping_candidates

Lists pending scraping candidates for staff review in the terminal.

Usage:
  python manage.py review_scraping_candidates
  python manage.py review_scraping_candidates --status=new --region="Alpes / Savoie"
  python manage.py review_scraping_candidates --job=scrape-biarritz-20260915-143200

Spec §US-5.5.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "List pending scraping candidates for review."

    def add_arguments(self, parser):
        parser.add_argument(
            "--status",
            default="new",
            choices=["new", "imported", "rejected", "deferred", "all"],
            help="Filter by status (default: new).",
        )
        parser.add_argument(
            "--region",
            default="",
            help="Filter by region key.",
        )
        parser.add_argument(
            "--job",
            default="",
            metavar="JOB_ID",
            help="Filter by job ID.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Max candidates to show (default: 50).",
        )

    def handle(self, *args, **options):
        from apps.scraper.models import ScrapingCandidate

        qs = ScrapingCandidate.objects.select_related("village", "job").order_by(
            "-match_confidence"
        )

        status = options["status"]
        if status != "all":
            qs = qs.filter(status=status)
        if options["region"]:
            qs = qs.filter(region__icontains=options["region"])
        if options["job"]:
            qs = qs.filter(job_id=options["job"])

        candidates = qs[: options["limit"]]
        count = qs.count()

        if not count:
            self.stdout.write("No candidates found.")
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'=' * 80}\n"
                f"Scraping Candidates — status={status}  total={count}\n"
                f"{'=' * 80}"
            )
        )

        for cand in candidates:
            village_label = cand.village.nom if cand.village else cand.region
            match_info = (
                f"→ matches {cand.matched_activity_code} ({cand.match_confidence:.0%})"
                if cand.matched_activity_code
                else "→ NEW"
            )
            price_info = ""
            if cand.price_adult is not None:
                price_info = f"  Ad:{cand.price_adult}€ / Enf:{cand.price_child}€"

            rating_info = f"  ⭐{cand.rating:.1f} ({cand.review_count})" if cand.rating else ""

            self.stdout.write(
                f"\n[{cand.id}] {cand.nom}\n"
                f"  Village: {village_label}  Source: {cand.source}  Status: {cand.status}\n"
                f"  {match_info}{price_info}{rating_info}\n"
                f"  URL: {cand.source_url[:80]}"
            )

        self.stdout.write(f"\n{'=' * 80}")
        self.stdout.write(
            f"Showing {min(options['limit'], count)} of {count} candidates."
        )
        self.stdout.write(
            "Use POST /api/v3/admin/scraper/import to import/reject/defer."
        )