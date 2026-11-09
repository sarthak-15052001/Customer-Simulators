"""Django admin function-based views for the translation control panel
(mirrors apps/header_scraper/admin_views.py — cache-based job bookkeeping,
no extra Job model)."""
from __future__ import annotations

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

_ACTIVE_JOB_CACHE_KEY = "translation_manager:active_job"
_RECENT_JOBS_CACHE_KEY = "translation_manager:recent_jobs"
_CACHE_TIMEOUT = 60 * 60 * 6

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


def _set_active_job(job: dict | None) -> None:
    if job is None:
        cache.delete(_ACTIVE_JOB_CACHE_KEY)
    else:
        cache.set(_ACTIVE_JOB_CACHE_KEY, job, timeout=_CACHE_TIMEOUT)


def _push_recent_job(job: dict) -> None:
    recent = cache.get(_RECENT_JOBS_CACHE_KEY) or []
    recent = [job] + [r for r in recent if r.get("task_id") != job.get("task_id")]
    cache.set(_RECENT_JOBS_CACHE_KEY, recent[:10], timeout=_CACHE_TIMEOUT)


def _registry_group_counts() -> dict:
    from apps.translation_manager.services.registry import group_counts

    return group_counts()


def _task_state(task_id: str) -> str:
    from config.celery_app import app as celery_app

    result = celery_app.AsyncResult(task_id)
    return _CELERY_STATE_LABELS.get(result.state, "queued")


@staff_member_required
@require_GET
def translation_control_view(request: HttpRequest) -> HttpResponse:
    from apps.translation_manager.models import TARGET_LANGUAGE_CHOICES, TranslationEntry

    languages = [{"id": code, "label": f"{label} ({code})"} for code, label in TARGET_LANGUAGE_CHOICES]

    active_job = cache.get(_ACTIVE_JOB_CACHE_KEY)
    if active_job:
        active_job = dict(active_job)
        active_job["status"] = _task_state(active_job["task_id"])
        if active_job["status"] in ("completed", "failed"):
            _push_recent_job(active_job)
            _set_active_job(None)

    context = {
        **admin.site.each_context(request),
        "title": "Traduction automatique",
        "languages": languages,
        "active_job": active_job,
        "recent_jobs": cache.get(_RECENT_JOBS_CACHE_KEY) or [],
        "pending_count": TranslationEntry.objects.filter(status="pending").count(),
        "failed_count": TranslationEntry.objects.filter(status="failed").count(),
        "registry_field_count": sum(_registry_group_counts().values()),
        "registry_groups": sorted(_registry_group_counts().items()),
        "start_url": reverse("admin:translation_manager_control_start"),
        "sync_url": reverse("admin:translation_manager_control_sync"),
        "status_url_template": reverse(
            "admin:translation_manager_control_status", kwargs={"task_id": "__TASK_ID__"}
        ),
    }
    return render(request, "admin/translation_manager/translation_control.html", context)


@staff_member_required
@require_POST
def translation_control_start_view(request: HttpRequest) -> HttpResponse:
    """Queue the pending/stale sweep, or re-translate every active source."""
    from apps.translation_manager.models import TranslationSource
    from apps.translation_manager.tasks import task_translate_pending, task_translate_source

    mode = request.POST.get("mode", "pending")
    language = request.POST.get("language", "").strip().upper()
    language_label = f" → {language}" if language else " → toutes langues"

    if mode == "all":
        sources = TranslationSource.objects.filter(is_active=True)
        excluded_same_language_count = 0
        if language:
            same_language_count = sources.filter(source_language=language).count()
            sources = sources.exclude(source_language=language)
            excluded_same_language_count = same_language_count
        source_ids = list(sources.values_list("pk", flat=True))
        for source_id in source_ids:
            task_translate_source.delay(source_id, [language] if language else None)
        async_result = None
        target_id = f"{len(source_ids)} source(s){language_label}"
        task_id = f"batch-{len(source_ids)}"

        if not source_ids and excluded_same_language_count:
            # Every active source is already in `language` (this always
            # happens when language == FR, since catalog sources are
            # canonically French) — nothing was queued because there's
            # nothing to translate: same-language entries are just a copy
            # of the source text, already kept in sync automatically.
            # Tell the admin that explicitly instead of a bare "0 queued".
            messages.info(
                request,
                f"Rien à retraduire vers {language} : les {excluded_same_language_count} "
                f"source(s) active(s) sont déjà en {language}, donc simplement recopiées "
                "automatiquement — aucun appel LLM n'est nécessaire.",
            )
            return redirect("admin:translation_manager_control")
    else:
        async_result = task_translate_pending.delay(language=language or None)
        target_id = f"pending/stale entries{language_label}"
        task_id = async_result.id

    job = {
        "task_id": task_id,
        "target_type": mode,
        "target_id": target_id,
        "status": "queued",
        "triggered_by": _actor(request),
    }
    if async_result is not None:
        _set_active_job(job)

    messages.success(request, f"Translation run queued ({target_id}).")
    return redirect("admin:translation_manager_control")


@staff_member_required
@require_POST
def translation_control_sync_view(request: HttpRequest) -> HttpResponse:
    """Pull every registered catalog field into TranslationSource rows now.
    Saving each changed row queues its own translation
    via the post_save signal, so this alone is enough to catch up."""
    from apps.translation_manager.tasks import task_sync_translation_sources

    async_result = task_sync_translation_sources.delay()
    _set_active_job(
        {
            "task_id": async_result.id,
            "target_type": "sync",
            "target_id": "catalog model fields",
            "status": "queued",
            "triggered_by": _actor(request),
        }
    )
    messages.success(request, "Queued sync of catalog fields into the translation table.")
    return redirect("admin:translation_manager_control")


@staff_member_required
@require_GET
def translation_control_status_view(request: HttpRequest, task_id: str) -> JsonResponse:
    from config.celery_app import app as celery_app

    result = celery_app.AsyncResult(task_id)
    status = _CELERY_STATE_LABELS.get(result.state, "queued")
    summary = {}
    if status == "completed" and isinstance(result.result, dict):
        summary = result.result
    elif status == "failed" and result.result:
        summary = {"error": str(result.result)}
    return JsonResponse(
        {
            "taskId": task_id,
            "status": status,
            "summary": summary,
            "isActive": status in ("queued", "running"),
        }
    )
