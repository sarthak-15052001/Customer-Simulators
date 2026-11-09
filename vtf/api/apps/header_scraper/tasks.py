"""Celery tasks for the header_scraper app.

ALERT HOOKS:
  - notify_scrape_success()  — banner content changed and was published
  - notify_scrape_failure()  — fetch_failed (all 3 tiers failed) or parse_failed
  - notify_batch_summary()   — sent once after task_scrape_header_banner scrapes
                                every language (FR + GB)

STATUS_UNCHANGED is intentionally silent (no Discord alert) so routine polls
where nothing changed don't spam the channel.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger("header_scraper")

_FAILURE_STATUSES = ("fetch_failed", "parse_failed")


def _dispatch_alert(result: dict) -> None:
    """Fire the right Discord alert for a single sync_language() result."""
    from apps.header_scraper.services.alerts import (
        notify_scrape_failure,
        notify_scrape_success,
    )

    status = result.get("status")
    if status in _FAILURE_STATUSES:
        notify_scrape_failure(result)
    elif status == "success":
        notify_scrape_success(result)
    # status == "unchanged" -> no alert, on purpose.


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name="apps.header_scraper.tasks.task_scrape_header_banner",
)
def task_scrape_header_banner(self) -> dict:
    """Scrape FR + GB homepage top banners and auto-publish."""
    from apps.header_scraper.services.alerts import notify_batch_summary
    from apps.header_scraper.services.sync import sync_all_languages

    logger.info("task_scrape_header_banner: START")
    try:
        result = sync_all_languages()
        results = result.get("results", [])
        statuses = [r.get("status") for r in results]

        for r in results:
            _dispatch_alert(r)
        notify_batch_summary(results)

        logger.info(
            "task_scrape_header_banner: DONE ok=%s statuses=%s",
            result.get("ok"),
            statuses,
        )
        return result
    except Exception as exc:
        logger.exception("task_scrape_header_banner: FAILED")
        from apps.header_scraper.services.alerts import notify_scrape_failure

        notify_scrape_failure({
            "language": "ALL",
            "status": "fetch_failed",
            "error": f"tasks.py → task_scrape_header_banner() | Unhandled exception: {exc}",
        })
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name="apps.header_scraper.tasks.task_scrape_header_banner_language",
)
def task_scrape_header_banner_language(self, language: str) -> dict:
    """Scrape a single language (FR or GB)."""
    from apps.header_scraper.services.sync import sync_language

    logger.info("task_scrape_header_banner_language: START language=%s", language)
    try:
        result = sync_language(language)
        _dispatch_alert(result)
        logger.info(
            "task_scrape_header_banner_language: DONE language=%s status=%s",
            language,
            result.get("status"),
        )
        return result
    except Exception as exc:
        logger.exception(
            "task_scrape_header_banner_language: FAILED language=%s", language
        )
        from apps.header_scraper.services.alerts import notify_scrape_failure

        notify_scrape_failure({
            "language": language,
            "status": "fetch_failed",
            "error": (
                "tasks.py → task_scrape_header_banner_language() | "
                f"Unhandled exception: {exc}"
            ),
        })
        raise self.retry(exc=exc)
