"""Shared scraping job helpers used by the API and Django admin UI."""
from __future__ import annotations

from datetime import datetime, timezone

from django.utils import timezone as dj_timezone

from apps.scraper.models import ScrapingJob
from apps.scraper.tasks import task_run_scraping_job

VALID_SOURCES = ["google_places", "tripadvisor", "ot_local"]
VALID_TARGET_TYPES = ["village", "region"]


class JobCancelled(Exception):
    """Raised when a scraping job was cancelled before completion."""


def is_job_cancelled(job: ScrapingJob) -> bool:
    summary = job.result_summary or {}
    return job.status == "failed" and bool(summary.get("cancelled"))


def queue_scraping_job(
    *,
    target_type: str,
    target_id: str,
    sources: list[str],
    radius_km: int = 30,
    max_results: int = 50,
    triggered_by: str,
) -> ScrapingJob:
    """Create a ScrapingJob and enqueue the Celery task (same logic as the API)."""

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    job_id = f"scrape-{target_id}-{ts}"

    job = ScrapingJob.objects.create(
        id=job_id,
        target_type=target_type,
        target_id=target_id,
        sources=sources,
        radius_km=radius_km,
        max_results=max_results,
        status="queued",
        triggered_by=triggered_by,
    )
    task_run_scraping_job.delay(job_id)
    return job


def cancel_scraping_job(job_id: str, actor: str) -> ScrapingJob | None:
    """Mark a queued or running job as cancelled."""
    try:
        job = ScrapingJob.objects.get(pk=job_id)
    except ScrapingJob.DoesNotExist:
        return None

    if job.status not in ("queued", "running"):
        return job

    job.status = "failed"
    job.result_summary = {
        "error": "Cancelled by admin user",
        "cancelled": True,
        "cancelledBy": actor,
    }
    job.completed_at = dj_timezone.now()
    job.save(update_fields=["status", "result_summary", "completed_at"])
    return job
