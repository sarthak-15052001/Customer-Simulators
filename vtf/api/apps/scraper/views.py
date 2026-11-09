"""Scraper admin views (Phase 3).

Endpoints (all staff-only, mounted under /api/v3/):
  POST /api/v3/admin/scraper/activities         — trigger scraping job
  GET  /api/v3/admin/scraper/jobs               — list scraping jobs
  GET  /api/v3/admin/scraper/jobs/{job_id}      — poll job status + candidates
  POST /api/v3/admin/scraper/import             — import/reject candidates
  GET  /api/v3/admin/scraper/candidates         — list pending candidates
  GET  /api/v3/admin/scraper/price-updates      — list price change alerts
  POST /api/v3/admin/scraper/price-updates/{id} — approve/dismiss alert
"""
from __future__ import annotations

import logging

from common.permissions import StaffAPIViewMixin
from common.response import CustomResponse
from django.utils import timezone as dj_timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.scraper.models import (
    PriceChangeAlert,
    ScrapingCandidate,
    ScrapingImportLog,
    ScrapingJob,
)
from apps.scraper.serializers import (
    ImportCandidatesSerializer,
    PriceChangeAlertSerializer,
    ScrapingCandidateSerializer,
    ScrapingImportLogSerializer,
    ScrapingJobSerializer,
    TriggerScrapingSerializer,
)
from apps.scraper.services.admin_helpers import queue_scraping_job

logger = logging.getLogger(__name__)


class TriggerScrapingView(StaffAPIViewMixin, APIView):
    """POST /api/v3/admin/scraper/activities

    Triggers an async scraping job for a village or region.
    Returns a job ID that can be polled for status.
    """

    @extend_schema(
        operation_id="v3_admin_scraper_activities_create",
        request=TriggerScrapingSerializer,
        responses=inline_serializer(
            name="TriggerScrapingResponse",
            fields={
                "jobId": serializers.CharField(),
                "status": serializers.CharField(),
                "estimatedDurationSec": serializers.IntegerField(),
                "pollUrl": serializers.CharField(),
                "autoImport": serializers.BooleanField(),
            },
        ),
        tags=["v3"],
        summary="Trigger activity scraping job",
    )
    def post(self, request: Request) -> CustomResponse:
        serializer = TriggerScrapingSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                "Invalid request.", errors=serializer.errors, status_code=400
            )

        data = serializer.validated_data
        target_type = data["target"]
        target_id = data.get("villageId") or data.get("regionKey") or ""
        sources = data["sources"]
        radius_km = data["radiusKm"]
        max_results = data["maxResults"]
        auto_import = data["autoImport"]

        triggered_by = (
            request.user.email if request.user.is_authenticated else "staff"
        )

        job = queue_scraping_job(
            target_type=target_type,
            target_id=target_id,
            sources=sources,
            radius_km=radius_km,
            max_results=max_results,
            triggered_by=triggered_by,
        )
        job_id = job.id

        poll_url = f"/api/v3/admin/scraper/jobs/{job_id}"

        return CustomResponse.created(
            "Scraping job queued.",
            data={
                "jobId": job_id,
                "status": "queued",
                "estimatedDurationSec": 45,
                "pollUrl": poll_url,
                "autoImport": auto_import,
            },
        )


class ScrapingJobListView(StaffAPIViewMixin, APIView):
    """GET /api/v3/admin/scraper/jobs — list all scraping jobs."""

    @extend_schema(
        operation_id="v3_admin_scraper_jobs_list",
        responses=ScrapingJobSerializer(many=True),
        tags=["v3"],
        summary="List scraping jobs",
    )
    def get(self, request: Request) -> CustomResponse:
        limit = min(int(request.query_params.get("limit", 20)), 100)
        status_filter = request.query_params.get("status", "")
        qs = ScrapingJob.objects.order_by("-created_at")
        if status_filter:
            qs = qs.filter(status=status_filter)
        jobs = ScrapingJobSerializer(qs[:limit], many=True).data
        return CustomResponse.success(f"{len(jobs)} jobs.", data=jobs)


class ScrapingJobDetailView(StaffAPIViewMixin, APIView):
    """GET /api/v3/admin/scraper/jobs/{job_id} — job status + candidates."""

    @extend_schema(
        operation_id="v3_admin_scraper_job_retrieve",
        responses=inline_serializer(
            name="ScrapingJobDetailResponse",
            fields={
                "jobId": serializers.CharField(),
                "status": serializers.CharField(),
                "village": serializers.CharField(allow_null=True),
                "sources": serializers.DictField(),
                "candidates": ScrapingCandidateSerializer(many=True),
                "summary": serializers.DictField(),
                "startedAt": serializers.DateTimeField(allow_null=True),
                "completedAt": serializers.DateTimeField(allow_null=True),
            },
        ),
        tags=["v3"],
        summary="Get scraping job status and candidates",
    )
    def get(self, request: Request, job_id: str) -> CustomResponse:
        try:
            job = ScrapingJob.objects.get(pk=job_id)
        except ScrapingJob.DoesNotExist:
            return CustomResponse.error(f"Job {job_id} not found.", status_code=404)

        candidates = ScrapingCandidate.objects.filter(job=job).order_by("status", "-match_confidence")

        # Build per-source stats. For a completed job, use result_summary.
        # For a running/queued job, compute live counts from stored candidates.
        result_summary = job.result_summary or {}
        if job.status == "completed" and result_summary.get("sources"):
            source_stats = result_summary["sources"]
        else:
            # Live computation from already-persisted candidates
            from django.db.models import Count
            live_counts = (
                ScrapingCandidate.objects
                .filter(job=job)
                .values("source")
                .annotate(total=Count("id"))
            )
            source_stats = {row["source"]: {"found": row["total"], "new": row["total"], "errors": 0}
                            for row in live_counts}

        summary = {
            "totalNew": result_summary.get("totalNew", candidates.filter(status="new").count()),
            "totalDuplicates": result_summary.get("totalDuplicates", 0),
            "readyForReview": result_summary.get("readyForReview", candidates.filter(status="new").count()),
            "totalPriceAlerts": result_summary.get("totalPriceAlerts", 0),
            "totalExcludedByRule": result_summary.get("totalExcludedByRule", 0),
            "totalAutoHiddenByRule": result_summary.get("totalAutoHiddenByRule", 0),
        }

        return CustomResponse.success(
            "Job details fetched.",
            data={
                "jobId": job.id,
                "status": job.status,
                "village": job.target_id if job.target_type == "village" else None,
                "sources": source_stats,
                "candidates": ScrapingCandidateSerializer(candidates, many=True).data,
                "summary": summary,
                "startedAt": job.started_at,
                "completedAt": job.completed_at,
            },
        )


class ImportCandidatesView(StaffAPIViewMixin, APIView):
    """POST /api/v3/admin/scraper/import

    Batch import/reject/defer candidates after human review.
    Spec §US-5.5.
    """

    @extend_schema(
        operation_id="v3_admin_scraper_import_create",
        request=ImportCandidatesSerializer,
        responses=inline_serializer(
            name="ImportCandidatesResponse",
            fields={
                "imported": serializers.IntegerField(),
                "rejected": serializers.IntegerField(),
                "deferred": serializers.IntegerField(),
                "hidden": serializers.IntegerField(),
                "newActivityCodes": serializers.ListField(
                    child=serializers.CharField()
                ),
                "cacheRebuilt": serializers.BooleanField(),
                "errors": serializers.ListField(child=serializers.CharField()),
            },
        ),
        tags=["v3"],
        summary="Import/reject scraped activity candidates",
    )
    def post(self, request: Request) -> CustomResponse:
        serializer = ImportCandidatesSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                "Invalid request.", errors=serializer.errors, status_code=400
            )

        data = serializer.validated_data
        job_id = data["jobId"]
        actions = data["actions"]

        try:
            ScrapingJob.objects.get(pk=job_id)
        except ScrapingJob.DoesNotExist:
            return CustomResponse.error(f"Job {job_id} not found.", status_code=404)

        actor = request.user.email if request.user.is_authenticated else "staff"

        imported = 0
        rejected = 0
        deferred = 0
        hidden = 0
        new_codes: list[str] = []
        errors: list[str] = []

        from apps.scraper.pipeline import import_candidate

        for action_data in actions:
            cand_id = action_data["candidateId"]
            action = action_data["action"]
            edits = action_data.get("edits") or {}
            reason = action_data.get("reason", "")

            try:
                candidate = ScrapingCandidate.objects.get(pk=cand_id, job_id=job_id)
            except ScrapingCandidate.DoesNotExist:
                errors.append(f"Candidate {cand_id} not found.")
                continue

            if action == "import":
                # Only auto-import high-confidence matches or explicit imports
                if candidate.match_confidence < 0.90 or candidate.matched_activity_code == "":
                    try:
                        activity = import_candidate(candidate, edits=edits, actor=actor)
                        new_codes.append(activity.code)
                        imported += 1
                    except Exception as exc:
                        errors.append(f"Failed to import {cand_id}: {exc}")
                else:
                    errors.append(
                        f"Candidate {cand_id} already matches existing activity — reject or edit first."
                    )

            elif action == "reject":
                candidate.status = "rejected"
                candidate.reviewed_by = actor
                candidate.reviewed_at = dj_timezone.now()
                candidate.edits = {"reason": reason} if reason else None
                candidate.save(update_fields=["status", "reviewed_by", "reviewed_at", "edits"])
                ScrapingImportLog.objects.create(
                    job_id=job_id,
                    candidate=candidate,
                    action="reject",
                    actor=actor,
                    reason=reason,
                )
                rejected += 1

            elif action == "defer":
                candidate.status = "deferred"
                candidate.reviewed_by = actor
                candidate.reviewed_at = dj_timezone.now()
                candidate.save(update_fields=["status", "reviewed_by", "reviewed_at"])
                ScrapingImportLog.objects.create(
                    job_id=job_id,
                    candidate=candidate,
                    action="defer",
                    actor=actor,
                )
                deferred += 1

            elif action == "hide":
                candidate.status = "hidden"
                candidate.reviewed_by = actor
                candidate.reviewed_at = dj_timezone.now()
                candidate.edits = {"reason": reason} if reason else None
                candidate.save(update_fields=["status", "reviewed_by", "reviewed_at", "edits"])
                ScrapingImportLog.objects.create(
                    job_id=job_id,
                    candidate=candidate,
                    action="hide",
                    actor=actor,
                    reason=reason,
                )
                hidden += 1

        # Trigger cache rebuild for affected regions
        cacheRebuilt = False
        if imported > 0:
            try:
                from apps.cache_orchestrator.service import CacheOrchestrator
                CacheOrchestrator.rebuild(
                    scope="catalog",
                    reason=f"Scraper import: {imported} activities",
                    triggered_by=f"scraper:batch_import:{actor}",
                )
                cacheRebuilt = True
            except Exception:
                pass

        return CustomResponse.success(
            f"Processed {len(actions)} actions.",
            data={
                "imported": imported,
                "rejected": rejected,
                "deferred": deferred,
                "hidden": hidden,
                "newActivityCodes": new_codes,
                "cacheRebuilt": cacheRebuilt,
                "errors": errors,
            },
        )


class ScrapingCandidateListView(StaffAPIViewMixin, APIView):
    """GET /api/v3/admin/scraper/candidates — list pending candidates."""

    @extend_schema(
        operation_id="v3_admin_scraper_candidates_list",
        responses=inline_serializer(
            name="ScrapingCandidateListResponse",
            fields={
                "candidates": ScrapingCandidateSerializer(many=True),
                "count": serializers.IntegerField(),
            },
        ),
        tags=["v3"],
        summary="List scraping candidates pending review",
    )
    def get(self, request: Request) -> CustomResponse:
        status_filter = request.query_params.get("status", "new")
        region_filter = request.query_params.get("region", "")
        limit = min(int(request.query_params.get("limit", 50)), 200)

        qs = ScrapingCandidate.objects.select_related("village", "job").order_by("-match_confidence")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if region_filter:
            qs = qs.filter(region=region_filter)

        candidates = ScrapingCandidateSerializer(qs[:limit], many=True).data
        return CustomResponse.success(
            f"{len(candidates)} candidates.",
            data={"candidates": candidates, "count": len(candidates)},
        )


class PriceChangeAlertListView(StaffAPIViewMixin, APIView):
    """GET /api/v3/admin/scraper/price-updates — list pending price alerts."""

    @extend_schema(
        operation_id="v3_admin_scraper_price_updates_list",
        responses=PriceChangeAlertSerializer(many=True),
        tags=["v3"],
        summary="List price change alerts",
    )
    def get(self, request: Request) -> CustomResponse:
        status_filter = request.query_params.get("status", "pending")
        qs = PriceChangeAlert.objects.select_related("activity").order_by("-scraped_at")
        if status_filter:
            qs = qs.filter(status=status_filter)

        alerts = PriceChangeAlertSerializer(qs[:100], many=True).data
        return CustomResponse.success(f"{len(alerts)} price alerts.", data=alerts)


class PriceChangeAlertActionView(StaffAPIViewMixin, APIView):
    """POST /api/v3/admin/scraper/price-updates/{id} — approve/dismiss alert."""

    @extend_schema(
        operation_id="v3_admin_scraper_price_update_action_create",
        request=inline_serializer(
            name="PriceChangeAlertActionRequest",
            fields={
                "action": serializers.ChoiceField(choices=["approve", "dismiss"]),
            },
        ),
        responses=PriceChangeAlertSerializer,
        tags=["v3"],
        summary="Approve or dismiss a price change alert",
    )
    def post(self, request: Request, alert_id: int) -> CustomResponse:
        try:
            alert = PriceChangeAlert.objects.select_related("activity").get(pk=alert_id)
        except PriceChangeAlert.DoesNotExist:
            return CustomResponse.error(f"Alert {alert_id} not found.", status_code=404)

        action = request.data.get("action", "")
        if action not in ("approve", "dismiss"):
            return CustomResponse.error(
                "action must be 'approve' or 'dismiss'.", status_code=400
            )

        if action == "approve":
            # Apply the price change to the catalog activity
            setattr(alert.activity, alert.field, alert.new_value)
            alert.activity.save(update_fields=[alert.field])
            alert.status = "approved"
        else:
            alert.status = "dismissed"

        alert.save(update_fields=["status"])
        return CustomResponse.success(
            f"Alert {alert_id} {alert.status}.",
            data=PriceChangeAlertSerializer(alert).data,
        )
