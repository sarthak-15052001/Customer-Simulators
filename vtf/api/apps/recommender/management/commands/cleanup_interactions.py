"""Management command: cleanup_interactions.

Archives/deletes VillageInteraction rows older than a configurable number
of days. Keeps the high-volume interactions table from growing unbounded.

  python manage.py cleanup_interactions --days=90
  python manage.py cleanup_interactions --days=90 --dry-run
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.recommender.models import VillageInteraction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete VillageInteraction rows older than N days (default: 90)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Delete interactions older than this many days (default: 90).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print count without deleting.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        cutoff = timezone.now() - timedelta(days=days)
        logger.info(
            "recommender_cleanup_interactions_started days=%d dry_run=%s cutoff=%s",
            days,
            dry_run,
            cutoff.isoformat(),
        )

        qs = VillageInteraction.objects.filter(created_at__lt=cutoff)
        count = qs.count()

        if dry_run:
            logger.info(
                "recommender_cleanup_interactions_dry_run_done count=%d days=%d",
                count,
                days,
            )
            self.stdout.write(
                f"[dry-run] Would delete {count:,} interaction(s) older than {days} days "
                f"(before {cutoff.date()})."
            )
            return

        deleted, _ = qs.delete()
        logger.info(
            "recommender_cleanup_interactions_done deleted=%d days=%d",
            deleted,
            days,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted:,} interaction(s) older than {days} days."
            )
        )
