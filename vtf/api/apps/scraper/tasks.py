"""Celery tasks for the scraper app (Phase 3).

Tasks:
  task_run_scraping_job   — executes a ScrapingJob asynchronously
  task_monthly_scrape_all — scheduled monthly scrape of all 32 villages
  task_notify_scraping    — sends Slack/email notification after scrape
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from celery import shared_task
from common.discord import add_origin_to_embeds
from django.utils import timezone as dj_timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def task_run_scraping_job(self, job_id: str) -> dict:
    """Execute a ScrapingJob asynchronously.

    Calls the scraping pipeline for the job's target (village or region),
    deduplicates results against the catalog, and stores candidates.

    Args:
        job_id: The ScrapingJob.id (e.g. "scrape-biarritz-20260915-143200").
    """
    from apps.scraper.models import ScrapingJob
    from apps.scraper.pipeline import run_scraping_job
    from apps.scraper.services.admin_helpers import is_job_cancelled

    try:
        job = ScrapingJob.objects.get(pk=job_id)
    except ScrapingJob.DoesNotExist:
        logger.error("task_run_scraping_job: job_id=%s not found", job_id)
        return {"error": f"Job {job_id} not found"}

    if is_job_cancelled(job):
        logger.info("task_run_scraping_job: job_id=%s already cancelled", job_id)
        return {"error": "Job cancelled", "cancelled": True}

    job.status = "running"
    job.started_at = dj_timezone.now()
    job.save(update_fields=["status", "started_at"])

    try:
        result = run_scraping_job(job)
        job.refresh_from_db()
        if is_job_cancelled(job):
            logger.info("task_run_scraping_job: job_id=%s cancelled during run", job_id)
            return {"error": "Job cancelled", "cancelled": True}
        job.status = "completed"
        job.result_summary = result
        job.completed_at = dj_timezone.now()
        job.save(update_fields=["status", "result_summary", "completed_at"])
        logger.info(
            "task_run_scraping_job completed job_id=%s candidates=%s",
            job_id,
            result.get("totalNew", 0),
        )
        return result
    except Exception as exc:
        from apps.scraper.services.admin_helpers import JobCancelled

        if isinstance(exc, JobCancelled):
            logger.info("task_run_scraping_job cancelled job_id=%s", job_id)
            return {"error": "Job cancelled", "cancelled": True}
        logger.exception("task_run_scraping_job failed job_id=%s", job_id)
        job.status = "failed"
        job.result_summary = {"error": str(exc)}
        job.completed_at = dj_timezone.now()
        job.save(update_fields=["status", "result_summary", "completed_at"])
        raise self.retry(exc=exc)


@shared_task
def task_monthly_scrape_all() -> dict:
    """Monthly cron: scrape all 32 villages and notify staff.

    Spec §US-5.6 — runs 1st of each month at 04:00.
    """
    from apps.catalog.models import Village
    from apps.scraper.models import ScrapingJob

    villages = list(Village.objects.values_list("id", flat=True))
    job_ids = []

    for village_id in villages:
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        job_id = f"scrape-{village_id}-{ts}-{uuid.uuid4().hex[:4]}"
        job = ScrapingJob.objects.create(
            id=job_id,
            target_type="village",
            target_id=village_id,
            sources=["google_places", "tripadvisor", "ot_local"],
            radius_km=30,
            status="queued",
            triggered_by="system:cron:monthly",
        )
        task_run_scraping_job.delay(job_id)
        job_ids.append(job_id)

    logger.info(
        "task_monthly_scrape_all: queued %d jobs for %d villages",
        len(job_ids),
        len(villages),
    )

    # Fire notification after all jobs are queued
    task_notify_scraping.delay(job_ids=job_ids, trigger="monthly_cron")

    return {"jobsQueued": len(job_ids), "villages": villages}


@shared_task
def task_notify_scraping(job_ids: list[str], trigger: str = "manual") -> None:
    """Send Discord notification when scraping completes.

    Spec §US-5.6 — notify staff of new candidates for review.
    """
    discord_webhook = os.environ.get("DISCORD_WEBHOOK", "")
    if not discord_webhook:
        logger.debug("task_notify_scraping: no discord webhook configured")
        return

    try:
        from apps.scraper.models import ScrapingCandidate

        new_count = ScrapingCandidate.objects.filter(
            job__in=job_ids, status="new"
        ).count()

        if new_count == 0:
            return

        import requests

        payload = {
            "embeds": [
                {
                    "title": "🔍 VTF Activity Scraper",
                    "color": 0x3498DB,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "fields": [
                        {"name": "Trigger", "value": trigger, "inline": True},
                        {"name": "Villages Scraped", "value": str(len(job_ids)), "inline": True},
                        {"name": "New Candidates", "value": str(new_count), "inline": True},
                        {
                            "name": "Review",
                            "value": "`/api/v3/admin/scraper/candidates`",
                            "inline": False,
                        },
                    ],
                    "footer": {"text": "VTF Activity Scraper"},
                }
            ]
        }
        add_origin_to_embeds(payload)
        response = requests.post(discord_webhook, json=payload, timeout=5)
        if response.status_code == 204:
            logger.info(
                "task_notify_scraping: notified discord new_count=%d", new_count
            )
        else:
            logger.warning(
                "task_notify_scraping: discord webhook returned %s",
                response.status_code,
            )
    except Exception as exc:
        logger.warning("task_notify_scraping failed: %s", exc)
