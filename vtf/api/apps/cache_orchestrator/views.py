"""Cache orchestrator views.

  POST /api/v1/admin/cache/rebuild  — staff only, triggers rebuild by scope
  GET  /api/v1/admin/cache/logs     — staff only, last N rebuild log entries
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from common.permissions import StaffAPIViewMixin
from common.response import CustomResponse
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.cache_orchestrator.models import CacheRebuildLog
from apps.cache_orchestrator.cache_ops import (
    collect_cache_health_stats,
    collect_key_ttl_listing,
    count_logical_keys,
    is_redis_cache_backend,
)
from apps.cache_orchestrator.serializers import (
    CacheRebuildLogSerializer,
    CacheRebuildRequestSerializer,
    CacheRebuildResponseSerializer,
    CacheStatusSerializer,
)
from apps.cache_orchestrator.service import CacheOrchestrator

logger = logging.getLogger(__name__)


class CacheRebuildView(StaffAPIViewMixin, APIView):
    """POST /api/v3/admin/cache/rebuild

    Invalidates then re-warms Redis cache keys for the given scope.
    Runs synchronously and returns when complete (typically < 5s for scope=all).

    Staff-only: HTTP Basic auth required (same as other /admin/* endpoints).

    Example request::

        POST /api/v3/admin/cache/rebuild
        Authorization: Basic <base64(user:pass)>
        Content-Type: application/json

        {
            "scope": "pricing",
            "reason": "New pricing rules uploaded for summer 2027"
        }
    """

    @extend_schema(
        request=CacheRebuildRequestSerializer,
        responses={200: CacheRebuildResponseSerializer},
        tags=["v3"],
        summary="Rebuild Redis cache by scope",
        description=(
            "Invalidates all matching cache keys then pre-populates them. "
            "Returns a summary of how many keys were invalidated and rebuilt. "
            "Scopes: all | catalog | pricing | recommendations | booking_urls | "
            "villages:<id> | regions:<key>"
        ),
    )
    def post(self, request: Request) -> CustomResponse:
        serializer = CacheRebuildRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                "Invalid request body.",
                errors=serializer.errors,
                status_code=400,
            )

        scope = serializer.validated_data["scope"]
        reason = serializer.validated_data["reason"]
        triggered_by = (
            request.user.email
            if request.user.is_authenticated
            else "staff:unknown"
        )

        logger.info(
            "cache_rebuild_requested scope=%s triggered_by=%s reason=%r",
            scope,
            triggered_by,
            reason,
        )
        result = CacheOrchestrator.rebuild(
            scope=scope,
            reason=reason,
            triggered_by=triggered_by,
        )

        result["timestamp"] = datetime.now(tz=timezone.utc).isoformat()

        return CustomResponse.success(
            f"Cache rebuild completed for scope='{scope}'.",
            data=result,
        )


class CacheStatusView(StaffAPIViewMixin, APIView):
    """GET /api/v3/admin/cache/status — cache dashboard (spec US-5.1)."""

    @extend_schema(
        responses={200: CacheStatusSerializer},
        tags=["v3"],
        summary="Cache health dashboard",
        description=(
            "Returns Redis connectivity, key counts, memory usage, hit rate, "
            "and the most recent rebuild metadata."
        ),
    )
    def get(self, request: Request) -> CustomResponse:
        stats = collect_cache_health_stats()
        try:
            last_rebuild = CacheRebuildLog.objects.order_by("-created_at").first()
            if last_rebuild:
                stats["lastRebuild"] = last_rebuild.created_at.isoformat()
                stats["lastRebuildScope"] = last_rebuild.scope
                stats["lastRebuildDurationMs"] = last_rebuild.duration_ms
        except Exception:
            pass

        # Per-scope key counts (best-effort; Redis only).
        stats["scopes"] = _scope_key_counts()

        # Per-key TTL listing for ops (Redis only; empty on LocMem).
        try:
            limit = max(1, min(int(request.query_params.get("keyLimit", 200)), 500))
        except (TypeError, ValueError):
            limit = 200
        stats["keys"] = collect_key_ttl_listing(max_keys=limit)

        return CustomResponse.success("Cache status fetched.", data=stats)


def _scope_key_counts() -> dict[str, int]:

    counts: dict[str, int] = {}
    if not is_redis_cache_backend():
        return counts
    try:
        for scope, pattern in {
            "catalog": "vtf:catalog:*",
            "reco": "vtf:reco:*",
            "booking": "vtf:booking:*",
        }.items():
            counts[scope] = count_logical_keys(pattern)
    except Exception:
        pass
    return counts


class CacheRebuildLogListView(StaffAPIViewMixin, APIView):
    """GET /api/v3/admin/cache/logs?limit=20

    Returns the most recent cache rebuild log entries.
    Useful for auditing who triggered rebuilds and when.
    """

    @extend_schema(
        responses={200: CacheRebuildLogSerializer(many=True)},
        tags=["v3"],
        summary="List recent cache rebuild log entries",
    )
    def get(self, request: Request) -> CustomResponse:
        try:
            limit = max(1, min(int(request.query_params.get("limit", 20)), 100))
        except (TypeError, ValueError):
            limit = 20

        logs = CacheRebuildLog.objects.all()[:limit]
        data = CacheRebuildLogSerializer(logs, many=True).data

        return CustomResponse.success(
            f"Last {len(data)} cache rebuild log entries.",
            data=data,
        )
