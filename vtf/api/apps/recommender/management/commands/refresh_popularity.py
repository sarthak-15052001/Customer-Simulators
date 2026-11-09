"""Management command: refresh_popularity.

Aggregates VillageInteraction counts from the last 30 days and
upserts VillagePopularityCache with a composite score.

Run manually or via cron every 6h:
  python manage.py refresh_popularity
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from apps.catalog.models import Village
from apps.recommender.models import VillageInteraction, VillagePopularityCache
from apps.cache_orchestrator.tasks import task_rebuild_cache
from apps.cache_orchestrator.service import CacheOrchestrator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refresh VillagePopularityCache from last 30 days of interactions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Lookback window in days (default: 30)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timedelta(days=days)
        self.stdout.write(f"Refreshing popularity cache (last {days} days)…")
        logger.info("recommender_refresh_popularity_started days=%d cutoff=%s", days, cutoff.isoformat())

        # Aggregate per village per kind
        agg = (
            VillageInteraction.objects
            .filter(created_at__gte=cutoff)
            .values("village_id", "kind")
            .annotate(count=Count("id"))
        )

        # Pivot
        village_stats: dict[str, dict] = {}
        for row in agg:
            vid = row["village_id"]
            if vid not in village_stats:
                village_stats[vid] = {"views": 0, "simulations": 0, "bookmarks": 0}
            kind = row["kind"]
            if kind == "view":
                village_stats[vid]["views"] += row["count"]
            elif kind == "simulate":
                village_stats[vid]["simulations"] += row["count"]
            elif kind == "bookmark":
                village_stats[vid]["bookmarks"] += row["count"]

        # Composite score: views*1 + simulations*3 + bookmarks*5
        # Normalized 0–100 for easy interpretation
        updated = 0
        for village_id, stats in village_stats.items():
            raw_score = (
                stats["views"] * 1.0
                + stats["simulations"] * 3.0
                + stats["bookmarks"] * 5.0
            )
            try:
                village = Village.objects.get(pk=village_id)
            except Village.DoesNotExist:
                logger.warning(
                    "recommender_refresh_popularity_missing_village village_id=%s",
                    village_id,
                )
                continue

            VillagePopularityCache.objects.update_or_create(
                village=village,
                defaults={
                    "views_30d": stats["views"],
                    "simulations_30d": stats["simulations"],
                    "bookmarks_30d": stats["bookmarks"],
                    "score": round(raw_score, 2),
                },
            )
            updated += 1

        # Villages with zero interactions still need a cache row (score=0)
        for village in Village.objects.all():
            VillagePopularityCache.objects.get_or_create(
                village=village,
                defaults={"views_30d": 0, "simulations_30d": 0, "bookmarks_30d": 0, "score": 0.0},
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Updated {updated} village(s) with interaction data. "
                f"All {Village.objects.count()} villages now have cache rows."
            )
        )
        logger.info(
            "recommender_refresh_popularity_done updated=%d total_villages=%d",
            updated,
            Village.objects.count(),
        )

        try:
            task_rebuild_cache.delay(
                scope="recommendations",
                reason="refresh_popularity completed",
                triggered_by="system:refresh_popularity",
            )
        except Exception:
            try:
                CacheOrchestrator.rebuild(
                    scope="recommendations",
                    reason="refresh_popularity completed",
                    triggered_by="system:refresh_popularity (sync fallback)",
                )
            except Exception as exc:
                logger.warning("refresh_popularity_cache_rebuild_failed: %s", exc)
