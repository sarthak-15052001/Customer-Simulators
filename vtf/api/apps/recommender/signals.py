"""Django signal: auto-trigger CF readiness check after /estimate/stay (AC2.11).

How it works:
  After every SimulationLog.save() (which happens inside transaction.on_commit
  in the pricing view), we dispatch a lightweight Celery task that checks
  whether SVD thresholds are now met and updates the cf_model_ready cache flag.

  This means the cf_model_ready flag updates as soon as enough data arrives,
  without waiting for the daily 02:50 AM cron window.

Wiring (in apps/recommender/apps.py):
    def ready(self):
        import apps.recommender.signals  # noqa: F401
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

try:
    from apps.pricing.models import SimulationLog
except ImportError:
    SimulationLog = None

from apps.recommender.tasks import task_check_cf_readiness_after_estimate

logger = logging.getLogger(__name__)


def _wire_simulation_log_signal() -> None:
    """Wire the pricing SimulationLog post-save signal when available."""
    if SimulationLog is None:
        logger.debug("signals: SimulationLog not importable yet — skipping signal wiring")
        return

    @receiver(post_save, sender=SimulationLog, weak=False)
    def on_simulation_log_saved(sender, instance, created: bool, **kwargs) -> None:
        """After each new SimulationLog row, asynchronously check CF thresholds.

        Only fires on creation (not updates) so we don't spam tasks when
        clicked_booking / booking_click_at is updated later.
        Spec addendum §3.1 + AC2.11.
        """
        if not created:
            return
        try:
            task_check_cf_readiness_after_estimate.delay()
            logger.info(
                "recommender_cf_readiness_after_estimate_enqueued simulation_log_id=%s",
                instance.pk,
            )
        except Exception:
            # Never block the estimate response if Celery is unavailable
            logger.debug(
                "on_simulation_log_saved: Celery unavailable, skipping CF check",
                exc_info=True,
            )


# Wire immediately when this module is imported
_wire_simulation_log_signal()
