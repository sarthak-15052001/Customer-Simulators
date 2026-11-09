"""Django admin function-based views for the activity scraper control panel."""
from __future__ import annotations

import json

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.catalog.models import Village
from apps.scraper.models import ScrapingCandidate, ScrapingJob
from apps.scraper.services.admin_helpers import VALID_SOURCES, cancel_scraping_job, queue_scraping_job
from common.enums import Region


def _actor(request: HttpRequest) -> str:
    if request.user.is_authenticated:
        return request.user.email or request.user.get_username()
    return "staff"


def _parse_sources(request: HttpRequest) -> list[str]:
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            payload = {}
        raw = payload.get("sources", [])
    else:
        raw = request.POST.getlist("sources")

    if not raw:
        return list(VALID_SOURCES)

    selected = [source for source in raw if source in VALID_SOURCES]
    return selected or list(VALID_SOURCES)


@staff_member_required
@require_GET
def scraper_control_view(request: HttpRequest) -> HttpResponse:
    """Main scraper control page with start/stop controls."""
    villages = Village.objects.order_by("region", "nom").values("id", "nom", "region")
    regions = [{"key": choice.value, "label": choice.label} for choice in Region]
    active_job = (
        ScrapingJob.objects.filter(status__in=["queued", "running"])
        .order_by("-created_at")
        .first()
    )
    recent_jobs = ScrapingJob.objects.order_by("-created_at")[:10]

    context = {
        **admin.site.each_context(request),
        "title": "Scraper d'activités",
        "villages": list(villages),
        "regions": regions,
        "sources": VALID_SOURCES,
        "active_job": active_job,
        "recent_jobs": recent_jobs,
        "start_url": reverse("admin:scraper_start"),
        "stop_url": reverse("admin:scraper_stop"),
        "status_url_template": reverse(
            "admin:scraper_status", kwargs={"job_id": "__JOB_ID__"}
        ),
    }
    return render(request, "admin/scraper/scraper_control.html", context)


@staff_member_required
@require_POST
def scraper_start_view(request: HttpRequest) -> HttpResponse:
    """Start a scraping job (same behaviour as POST /api/v3/admin/scraper/activities)."""
    if ScrapingJob.objects.filter(status__in=["queued", "running"]).exists():
        messages.error(
            request,
            "Un scraping est déjà en cours. Arrêtez-le avant d'en lancer un nouveau.",
        )
        return redirect("admin:scraper_control")

    target_type = request.POST.get("target", "village")
    village_id = request.POST.get("village_id", "").strip()
    region_key = request.POST.get("region_key", "").strip()
    radius_km = int(request.POST.get("radius_km", "30") or 30)
    max_results = int(request.POST.get("max_results", "50") or 50)
    sources = _parse_sources(request)

    if target_type == "village":
        if not village_id:
            messages.error(request, "Sélectionnez un village.")
            return redirect("admin:scraper_control")
        if not Village.objects.filter(pk=village_id).exists():
            messages.error(request, f"Village inconnu : {village_id}.")
            return redirect("admin:scraper_control")
        target_id = village_id
    elif target_type == "region":
        valid_regions = {choice.value for choice in Region}
        if not region_key or region_key not in valid_regions:
            messages.error(request, "Sélectionnez une région valide.")
            return redirect("admin:scraper_control")
        target_id = region_key
    else:
        messages.error(request, "Type de cible invalide.")
        return redirect("admin:scraper_control")

    radius_km = max(1, min(radius_km, 100))

    job = queue_scraping_job(
        target_type=target_type,
        target_id=target_id,
        sources=sources,
        radius_km=radius_km,
        max_results=max_results,
        triggered_by=_actor(request),
    )

    messages.success(
        request,
        f"Scraping lancé (job {job.id}) — sources : {', '.join(sources)}.",
    )
    return redirect(f"{reverse('admin:scraper_control')}?job={job.id}")


@staff_member_required
@require_POST
def scraper_stop_view(request: HttpRequest) -> HttpResponse:
    """Stop the active scraping job."""
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            payload = {}
        job_id = payload.get("job_id", "")
    else:
        job_id = request.POST.get("job_id", "")

    if not job_id:
        active = (
            ScrapingJob.objects.filter(status__in=["queued", "running"])
            .order_by("-created_at")
            .first()
        )
        job_id = active.id if active else ""

    if not job_id:
        messages.warning(request, "Aucun scraping actif à arrêter.")
        return redirect("admin:scraper_control")

    job = cancel_scraping_job(job_id, _actor(request))
    if job is None:
        messages.error(request, f"Job introuvable : {job_id}.")
    elif job.status in ("completed", "failed") and not (job.result_summary or {}).get(
        "cancelled"
    ):
        messages.info(request, f"Le job {job_id} est déjà terminé.")
    else:
        messages.success(request, f"Scraping arrêté (job {job_id}).")

    return redirect("admin:scraper_control")


@staff_member_required
@require_GET
def scraper_status_view(request: HttpRequest, job_id: str) -> JsonResponse:
    """Poll job status for the admin UI (JSON)."""
    try:
        job = ScrapingJob.objects.get(pk=job_id)
    except ScrapingJob.DoesNotExist:
        return JsonResponse({"error": f"Job {job_id} not found."}, status=404)

    summary = job.result_summary or {}
    candidates = ScrapingCandidate.objects.filter(job=job)
    new_count = candidates.filter(status="new").count()

    return JsonResponse(
        {
            "jobId": job.id,
            "status": job.status,
            "targetType": job.target_type,
            "targetId": job.target_id,
            "sources": job.sources,
            "radiusKm": job.radius_km,
            "maxResults": job.max_results,
            "startedAt": job.started_at.isoformat() if job.started_at else None,
            "completedAt": job.completed_at.isoformat() if job.completed_at else None,
            "cancelled": bool(summary.get("cancelled")),
            "summary": {
                "totalNew": summary.get("totalNew", new_count),
                "totalDuplicates": summary.get("totalDuplicates", 0),
                "readyForReview": summary.get("readyForReview", new_count),
                "totalPriceAlerts": summary.get("totalPriceAlerts", 0),
                "sources": summary.get("sources", {}),
                "error": summary.get("error"),
            },
            "isActive": job.status in ("queued", "running"),
        }
    )
