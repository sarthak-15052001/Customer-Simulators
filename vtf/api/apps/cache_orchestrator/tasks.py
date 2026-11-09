"""Celery tasks for cache_orchestrator.

Single task: task_rebuild_cache
  - Called by signals (async, non-blocking)
  - Called by the admin endpoint (async)
  - Can also be triggered manually via .delay() / .apply_async()

The management command (rebuild_cache) calls CacheOrchestrator.rebuild()
directly (synchronous) — no Celery needed for CLI usage.
"""
from __future__ import annotations

import logging

from celery import shared_task
from apps.cache_orchestrator.service import CacheOrchestrator

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.cache_orchestrator.tasks.task_rebuild_cache",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    ignore_result=False,
)
def task_rebuild_cache(
    self,
    scope: str = "all",
    reason: str = "",
    triggered_by: str = "system:celery",
) -> dict:
    """Async wrapper around CacheOrchestrator.rebuild().

    Retries up to 3 times (30s apart) on transient Redis failures.
    Returns the same summary dict as the sync rebuild.
    """
    try:
        result = CacheOrchestrator.rebuild(
            scope=scope,
            reason=reason,
            triggered_by=triggered_by,
        )
        logger.info(
            "task_rebuild_cache completed scope=%s keys_rebuilt=%s duration_ms=%s",
            scope,
            result.get("keysRebuilt"),
            result.get("durationMs"),
        )
        return result
    except Exception as exc:
        logger.error(
            "task_rebuild_cache failed scope=%s error=%s — retrying",
            scope,
            exc,
            exc_info=True,
        )
        raise self.retry(exc=exc)
