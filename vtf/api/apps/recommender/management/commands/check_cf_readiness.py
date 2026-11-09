"""Management command: check_cf_readiness.

Checks SVD thresholds and sets the `cf_model_ready` cache flag.
Run daily via cron (e.g., at 2:50 AM before train_cf_model at 3 AM).

  python manage.py check_cf_readiness
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.recommender.services.cf_state import (
    evaluate_cf_readiness,
    save_cf_readiness_state,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Check if collaborative filtering SVD thresholds are met and set cache flag."

    def _thresholds(self) -> dict:
        min_sims = int(getattr(settings, "RECO_MIN_CF_INTERACTIONS", 500))
        return {
            "min_simulations": min_sims,
            "min_sessions": 100,
            "min_multi_village_sessions": 50,
            "min_villages_with_sims": 20,
            "min_sims_per_village": 10,
        }

    def handle(self, *args, **options):
        th = self._thresholds()
        self.stdout.write("Checking CF readiness thresholds…")
        logger.info("recommender_check_cf_readiness_started thresholds=%s", th)

        result = evaluate_cf_readiness(th)
        counts = result["counts"]
        ready = result["ready"]

        self.stdout.write(
            f"  Total simulations:          {counts['simulation_logs']:,} / {th['min_simulations']:,}"
        )
        self.stdout.write(
            f"  Unique sessions:            {counts['unique_sessions']:,} / {th['min_sessions']:,}"
        )
        self.stdout.write(
            f"  Multi-village sessions:     {counts['multi_village_sessions']:,} / {th['min_multi_village_sessions']:,}"
        )
        self.stdout.write(
            f"  Villages with ≥{th['min_sims_per_village']} sims: "
            f"{counts['villages_with_enough_sims']:,} / {th['min_villages_with_sims']:,}"
        )

        save_cf_readiness_state(ready=ready, metadata=result["metadata"])

        if ready:
            self.stdout.write(
                self.style.SUCCESS("✓ CF thresholds MET — collaborative filtering ACTIVE")
            )
        else:
            self.stdout.write(
                self.style.WARNING("✗ CF thresholds NOT met — content-based only")
            )
        logger.info(
            "recommender_check_cf_readiness_done ready=%s counts=%s",
            ready,
            counts,
        )
