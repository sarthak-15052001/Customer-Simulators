"""Django signals for cache_orchestrator.

Wires two auto-rebuild triggers (spec §5.1 / AC3.5):

  1. PricingRules.save(is_active=True)
       → scope="pricing"  (rules, seasons, promos)

  2. post_load_vtf_mocks   (custom signal sent by load_vtf_mocks command)
       → scope="all"

Both call CacheOrchestrator.rebuild() via a Celery task so the HTTP
response / management command is never blocked.
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import Signal, receiver
from apps.cache_orchestrator.service import CacheOrchestrator
from apps.cache_orchestrator.tasks import task_rebuild_cache

logger = logging.getLogger(__name__)

# Custom signal fired at the end of load_vtf_mocks (AC3.4).
post_load_vtf_mocks = Signal()


def _wire_pricing_rules_signal() -> None:
    """Connect PricingRules.post_save → cache rebuild."""
    try:
        from apps.catalog.models import PricingRules
    except ImportError:
        logger.debug("signals: PricingRules not importable yet — skipping")
        return

    @receiver(post_save, sender=PricingRules, weak=False)
    def on_pricing_rules_saved(sender, instance, **kwargs) -> None:
        """Auto-rebuild pricing scope whenever an active ruleset is saved (AC3.5)."""
        if not instance.is_active:
            return
        try:
            task_rebuild_cache.delay(
                scope="pricing",
                reason=f"PricingRules updated: {instance.updated_at}",
                triggered_by="system:signal:PricingRules",
            )
            logger.info(
                "cache_rebuild_enqueued scope=pricing triggered_by=PricingRules.save"
            )
        except Exception:
            # Never crash the admin save if Celery is down — fall back to sync.
            logger.warning(
                "Celery unavailable — running pricing cache rebuild synchronously",
                exc_info=True,
            )
            try:
                CacheOrchestrator.rebuild(
                    scope="pricing",
                    reason=f"PricingRules updated: {instance.updated_at}",
                    triggered_by="system:signal:PricingRules (sync fallback)",
                )
            except Exception:
                logger.error("Sync cache rebuild also failed", exc_info=True)


@receiver(post_load_vtf_mocks)
def on_load_vtf_mocks_done(sender, **kwargs) -> None:
    """Auto-rebuild all scopes after load_vtf_mocks completes (AC3.4)."""
    reason = kwargs.get("reason", "load_vtf_mocks completed")
    try:
        task_rebuild_cache.delay(
            scope="all",
            reason=reason,
            triggered_by="system:signal:post_load_vtf_mocks",
        )
        logger.info("cache_rebuild_enqueued scope=all triggered_by=load_vtf_mocks")
    except Exception:
        logger.warning(
            "Celery unavailable — running full cache rebuild synchronously",
            exc_info=True,
        )
        try:
            CacheOrchestrator.rebuild(
                scope="all",
                reason=reason,
                triggered_by="system:signal:post_load_vtf_mocks (sync fallback)",
            )
        except Exception:
            logger.error("Sync cache rebuild also failed", exc_info=True)


# Wire immediately on import
_wire_pricing_rules_signal()
