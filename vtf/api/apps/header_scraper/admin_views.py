"""Django admin function-based views for the header scraper start/stop
control panel (mirrors apps/tariff_scraper/admin_views.py)."""
from __future__ import annotations

import json

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone as dj_timezone
from django.views.decorators.http import require_GET, require_POST

from apps.header_scraper.models import HeaderBanner

# ---------------------------------------------------------------------------
# Start / stop control panel — apps/header_scraper equivalent of the
# apps/tariff_scraper "Scraper de tarifs" admin page (see
# apps/tariff_scraper/admin_views.py).
#
# There is no ScrapingJob model here either, so job bookkeeping is kept in
# the Django cache (no new migration, nothing else in the app is touched).
# Two cache keys are used:
#   header_scraper:active_job -> dict describing the in-flight task (or None)
#   header_scraper:recent_jobs -> list of the last 10 dicts (most recent first)
# Real progress/state comes from Celery's AsyncResult against the task id
# stored in the active job dict, so the panel reflects the actual worker.
#
# Unlike apps/tariff_scraper there are no villages — the only target is a
# language (FR / GB, from HeaderBanner.LANGUAGE_CHOICES), plus an "all
# languages" option that mirrors task_scrape_header_banner.
# ---------------------------------------------------------------------------

_ACTIVE_JOB_CACHE_KEY = "header_scraper:active_job"
_RECENT_JOBS_CACHE_KEY = "header_scraper:recent_jobs"
_CACHE_TIMEOUT = 60 * 60 * 6  # 6h — long enough to cover a full scrape run

_CELERY_STATE_LABELS = {
    "PENDING": "queued",
    "RECEIVED": "queued",
    "STARTED": "running",
    "RETRY": "running",
    "SUCCESS": "completed",
    "FAILURE": "failed",
    "REVOKED": "failed",
}


def _actor(request: HttpRequest) -> str:
    if request.user.is_authenticated:
        return request.user.email or request.user.get_username()
    return "staff"


def _get_active_job() -> dict | None:
    return cache.get(_ACTIVE_JOB_CACHE_KEY)


def _set_active_job(job: dict | None) -> None:
    if job is None:
        cache.delete(_ACTIVE_JOB_CACHE_KEY)
    else:
        cache.set(_ACTIVE_JOB_CACHE_KEY, job, timeout=_CACHE_TIMEOUT)


def _push_recent_job(job: dict) -> None:
    recent = cache.get(_RECENT_JOBS_CACHE_KEY) or []
    recent = [job] + [r for r in recent if r.get("task_id") != job.get("task_id")]
    cache.set(_RECENT_JOBS_CACHE_KEY, recent[:10], timeout=_CACHE_TIMEOUT)


def _get_recent_jobs() -> list[dict]:
    return cache.get(_RECENT_JOBS_CACHE_KEY) or []


def _task_state(task_id: str) -> str:
    from config.celery_app import app as celery_app

    result = celery_app.AsyncResult(task_id)
    return _CELERY_STATE_LABELS.get(result.state, "queued")


# A queued task that's been PENDING longer than this is treated as lost
# (worker died before pickup, result backend restarted, etc.) so the active
# slot doesn't stay blocked forever — Celery reports PENDING for both
# "queued" and "unknown/expired task id".
_STALE_PENDING_SECONDS = 60 * 10


def _job_is_stale(job: dict) -> bool:
    created_at = job.get("created_at")
    if not created_at:
        return False
    try:
        created = dj_timezone.datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return False
    if dj_timezone.is_naive(created):
        created = dj_timezone.make_aware(created)
    return (dj_timezone.now() - created).total_seconds() > _STALE_PENDING_SECONDS


@staff_member_required
@require_GET
def header_scraper_control_view(request: HttpRequest) -> HttpResponse:
    """Main header scraper control page with start/stop controls.

    Only "language" targets exist here (no villages), plus an "all
    languages" option that mirrors task_scrape_header_banner.
    """
    languages = [
        {"id": code, "label": f"{label} ({code})"}
        for code, label in HeaderBanner.LANGUAGE_CHOICES
    ]

    active_job = _get_active_job()
    if active_job:
        active_job = dict(active_job)
        active_job["status"] = _task_state(active_job["task_id"])
        if active_job["status"] in ("completed", "failed"):
            _push_recent_job(active_job)
            _set_active_job(None)
        elif active_job["status"] == "queued" and _job_is_stale(active_job):
            active_job["status"] = "failed"
            active_job["summary"] = {"error": "Tâche perdue (aucune réponse du worker)."}
            _push_recent_job(active_job)
            _set_active_job(None)

    context = {
        **admin.site.each_context(request),
        "title": "Scraper de bandeau",
        "languages": languages,
        "active_job": active_job,
        "recent_jobs": _get_recent_jobs(),
        "start_url": reverse("admin:header_scraper_control_start"),
        "stop_url": reverse("admin:header_scraper_control_stop"),
        "status_url_template": reverse(
            "admin:header_scraper_control_status", kwargs={"task_id": "__TASK_ID__"}
        ),
    }
    return render(request, "admin/header_scraper/scraper_control.html", context)


@staff_member_required
@require_POST
def header_scraper_start_view(request: HttpRequest) -> HttpResponse:
    """Start a header banner scraping run for one language or all languages."""
    from apps.header_scraper.tasks import (
        task_scrape_header_banner,
        task_scrape_header_banner_language,
    )

    if _get_active_job():
        messages.error(
            request,
            "Un scraping de bandeau est déjà en cours. Arrêtez-le avant d'en lancer un nouveau.",
        )
        return redirect("admin:header_scraper_control")

    target_type = request.POST.get("target", "language")
    valid_languages = dict(HeaderBanner.LANGUAGE_CHOICES)

    if target_type == "all":
        async_result = task_scrape_header_banner.delay()
        target_id = "toutes"
    else:
        language = request.POST.get("language", "").strip().upper()
        if not language:
            messages.error(request, "Sélectionnez une langue.")
            return redirect("admin:header_scraper_control")
        if language not in valid_languages:
            messages.error(request, f"Langue inconnue : {language}.")
            return redirect("admin:header_scraper_control")
        async_result = task_scrape_header_banner_language.delay(language)
        target_id = language

    job = {
        "task_id": async_result.id,
        "target_type": target_type,
        "target_id": target_id,
        "status": "queued",
        "triggered_by": _actor(request),
        "created_at": dj_timezone.now().isoformat(),
    }
    _set_active_job(job)

    messages.success(
        request, f"Scraping de bandeau lancé (task {async_result.id}) — cible : {target_id}."
    )
    return redirect(f"{reverse('admin:header_scraper_control')}?task={async_result.id}")


@staff_member_required
@require_POST
def header_scraper_stop_view(request: HttpRequest) -> HttpResponse:
    """Revoke/terminate the active header scraping task."""
    from config.celery_app import app as celery_app

    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            payload = {}
        task_id = payload.get("task_id", "")
    else:
        task_id = request.POST.get("task_id", "")

    active_job = _get_active_job()
    if not task_id and active_job:
        task_id = active_job.get("task_id", "")

    if not task_id:
        messages.warning(request, "Aucun scraping de bandeau actif à arrêter.")
        return redirect("admin:header_scraper_control")

    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")

    if active_job and active_job.get("task_id") == task_id:
        active_job = dict(active_job)
        active_job["status"] = "failed"
        active_job["cancelled"] = True
        active_job["cancelled_by"] = _actor(request)
        _push_recent_job(active_job)
        _set_active_job(None)

    messages.success(request, f"Scraping de bandeau arrêté (task {task_id}).")
    return redirect("admin:header_scraper_control")


@staff_member_required
@require_GET
def header_scraper_status_view(request: HttpRequest, task_id: str) -> JsonResponse:
    """Poll task status for the header scraper control panel (JSON)."""
    from config.celery_app import app as celery_app

    result = celery_app.AsyncResult(task_id)
    status = _CELERY_STATE_LABELS.get(result.state, "queued")

    active_job = _get_active_job()
    target_type = active_job.get("target_type", "") if active_job else ""
    target_id = active_job.get("target_id", "") if active_job else ""

    if (
        status == "queued"
        and active_job
        and active_job.get("task_id") == task_id
        and _job_is_stale(active_job)
    ):
        status = "failed"
        stale_job = dict(active_job)
        stale_job["status"] = "failed"
        stale_job["summary"] = {"error": "Tâche perdue (aucune réponse du worker)."}
        _push_recent_job(stale_job)
        _set_active_job(None)

    summary = {}
    if status == "completed" and isinstance(result.result, dict):
        summary = result.result
    elif status == "failed" and result.result:
        summary = {"error": str(result.result)}
    elif status == "failed" and not result.result:
        summary = {"error": "Tâche perdue (aucune réponse du worker)."}

    return JsonResponse(
        {
            "taskId": task_id,
            "status": status,
            "targetType": target_type,
            "targetId": target_id,
            "summary": summary,
            "isActive": status in ("queued", "running"),
        }
    )
