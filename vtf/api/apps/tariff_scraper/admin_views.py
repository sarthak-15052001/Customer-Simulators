"""Django admin function-based views for the tariff price health dashboard
and the tariff scraper start/stop control panel."""
from __future__ import annotations

import json

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone as dj_timezone
from django.views.decorators.http import require_GET, require_POST

from apps.catalog.models import Village
from apps.tariff_scraper.models import FormatChangeLog
from apps.tariff_scraper.services.alerts import (
    _classify_failure,
    _classify_format_change,
)
from apps.tariff_scraper.services.dashboard import (
    compute_village_health,
    _parse_pipeline_error,
)
from apps.tariff_scraper.services.village_urls import VILLAGE_URLS


@staff_member_required
@require_GET
def price_health_dashboard_view(request: HttpRequest) -> HttpResponse:
    """Global-vision monitoring page: one colored row per village.

    🟢 green = prices fine, 🟠 orange = stale scrape, 🔴 red = problem
    detected. Rolls up PriceSnapshot / FormatChangeLog / VillageTarif —
    no separate tracking table, so it's always in sync with the scraper.
    """
    summary = compute_village_health()

    region_filter = request.GET.get("region", "")
    status_filter = request.GET.get("status", "")
    rows = summary.rows
    if region_filter:
        rows = [r for r in rows if r.region == region_filter]
    if status_filter:
        rows = [r for r in rows if r.status == status_filter]

    regions = sorted({r.region for r in summary.rows})

    context = dict(
        admin.site.each_context(request),
        title="Tableau de bord ; Santé des prix",
        summary=summary,
        rows=rows,
        regions=regions,
        region_filter=region_filter,
        status_filter=status_filter,
    )
    return render(request, "admin/tariff_scraper/price_health_dashboard.html", context)


@staff_member_required
@require_GET
def village_error_detail_view(request: HttpRequest, village_id: str) -> HttpResponse:
    """Step-by-step error detail page for a single village."""
    village = get_object_or_404(Village, pk=village_id)

    latest_log = (
        FormatChangeLog.objects.filter(village=village)
        .order_by("-detected_at")
        .first()
    )

    error_details = []
    if latest_log and latest_log.errors:
        error_details = [_parse_pipeline_error(e) for e in latest_log.errors]

    alert_reports = []
    if latest_log:
        summary = {
            "village_id": village.pk,
            "url": latest_log.source_url,
            "bands_scraped": latest_log.bands_scraped,
            "priced_bands": latest_log.priced_bands,
            "bands_proposed": 0,
            "approval_id": None,
            "scrape_errors": latest_log.errors,
            "build_errors": [],
            "format_change": {
                "change_detected": True,
                "change_type": latest_log.change_type,
                "expected_markers": latest_log.expected_markers,
                "found_markers": latest_log.found_markers,
                "missing_markers": latest_log.missing_markers,
                "html_length": latest_log.html_length,
                "table_count": latest_log.table_count,
                "bands_scraped": latest_log.bands_scraped,
                "priced_bands": latest_log.priced_bands,
            },
        }
        format_title, format_reason, _ = _classify_format_change(summary)
        failure_title, failure_reason, _ = _classify_failure(summary)
        alert_reports = [
            {
                "heading": "Alerte changement de format",
                "title": format_title,
                "details": format_reason,
            },
            {
                "heading": "Alerte échec du scrape",
                "title": failure_title,
                "details": failure_reason,
            },
        ]

    context = dict(
        admin.site.each_context(request),
        title=f"Détail erreurs \u2014 {village.nom}",
        village=village,
        latest_log=latest_log,
        error_details=error_details,
        alert_reports=alert_reports,
    )
    return render(
        request, "admin/tariff_scraper/village_error_detail.html", context
    )


# ---------------------------------------------------------------------------
# Start / stop control panel — apps/tariff_scraper equivalent of the
# apps/scraper "Lancer le scraping" admin page (see apps/scraper/admin_views.py).
#
# The tariff scraper has no ScrapingJob model, so job bookkeeping is kept in
# the Django cache instead of the database (no new migration, nothing else
# in the app is touched). Two cache keys are used:
#   tariff_scraper:active_job -> dict describing the in-flight task (or None)
#   tariff_scraper:recent_jobs -> list of the last 10 dicts (most recent first)
# Real progress/state comes from Celery's AsyncResult against the task id
# stored in the active job dict, so the panel reflects the actual worker.
# ---------------------------------------------------------------------------

_ACTIVE_JOB_CACHE_KEY = "tariff_scraper:active_job"
_RECENT_JOBS_CACHE_KEY = "tariff_scraper:recent_jobs"
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
def tariff_scraper_control_view(request: HttpRequest) -> HttpResponse:
    """Main tariff scraper control page with start/stop controls.

    Only "village" targets exist here (unlike apps/scraper there is no
    region grouping for tariffs), plus an "all villages" option that mirrors
    task_scrape_all_village_tariffs.
    """
    # `nom` alone is not unique — e.g. "carcans-les-oyats" and
    # "carcans-les-bruyeres" both have nom="Carcans" — so the dropdown label
    # also carries `nom2` (the disambiguating sub-name, e.g. "Les Oyats")
    # and falls back to showing the id itself when nom2 is blank.
    villages = list(
        Village.objects.filter(pk__in=VILLAGE_URLS.keys())
        .order_by("nom", "id")
        .values("id", "nom")
    )
    for village in villages:
        village["label"] = f"{village['nom']} ({village['id']})"

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
        "title": "Scraper de tarifs",
        "villages": villages,
        "active_job": active_job,
        "recent_jobs": _get_recent_jobs(),
        "start_url": reverse("admin:tariff_scraper_control_start"),
        "stop_url": reverse("admin:tariff_scraper_control_stop"),
        "status_url_template": reverse(
            "admin:tariff_scraper_control_status", kwargs={"task_id": "__TASK_ID__"}
        ),
    }
    return render(request, "admin/tariff_scraper/scraper_control.html", context)


@staff_member_required
@require_POST
def tariff_scraper_start_view(request: HttpRequest) -> HttpResponse:
    """Start a tariff scraping run for one village or all villages."""
    from apps.tariff_scraper.tasks import (
        task_scrape_all_village_tariffs,
        task_scrape_village_tariffs,
    )

    if _get_active_job():
        messages.error(
            request,
            "Un scraping de tarifs est déjà en cours. Arrêtez-le avant d'en lancer un nouveau.",
        )
        return redirect("admin:tariff_scraper_control")

    target_type = request.POST.get("target", "village")

    if target_type == "all":
        async_result = task_scrape_all_village_tariffs.delay()
        target_id = "toutes"
    else:
        village_id = request.POST.get("village_id", "").strip()
        if not village_id:
            messages.error(request, "Sélectionnez un village.")
            return redirect("admin:tariff_scraper_control")
        if village_id not in VILLAGE_URLS:
            messages.error(request, f"Village inconnu : {village_id}.")
            return redirect("admin:tariff_scraper_control")
        async_result = task_scrape_village_tariffs.delay(village_id)
        target_id = village_id

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
        request, f"Scraping de tarifs lancé (task {async_result.id}) — cible : {target_id}."
    )
    return redirect(f"{reverse('admin:tariff_scraper_control')}?task={async_result.id}")


@staff_member_required
@require_POST
def tariff_scraper_stop_view(request: HttpRequest) -> HttpResponse:
    """Revoke/terminate the active tariff scraping task."""
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
        messages.warning(request, "Aucun scraping de tarifs actif à arrêter.")
        return redirect("admin:tariff_scraper_control")

    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")

    if active_job and active_job.get("task_id") == task_id:
        active_job = dict(active_job)
        active_job["status"] = "failed"
        active_job["cancelled"] = True
        active_job["cancelled_by"] = _actor(request)
        _push_recent_job(active_job)
        _set_active_job(None)

    messages.success(request, f"Scraping de tarifs arrêté (task {task_id}).")
    return redirect("admin:tariff_scraper_control")


@staff_member_required
@require_GET
def tariff_scraper_status_view(request: HttpRequest, task_id: str) -> JsonResponse:
    """Poll task status for the tariff scraper control panel (JSON)."""
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
