"""Recommender views — Phase 2 on `/api/v2/` (spec §4.3).

Interactions and signals remain on `/api/v1/` (pricing app).
"""
from __future__ import annotations

import logging
from datetime import timedelta

from common.permissions import StaffAPIViewMixin
from common.response import (
    CustomResponse,
    serialize_reco_result,
    serialize_recommended_village,
)
from common.throttles import RecommendIpThrottle
from common.utils import get_session_id as _session_id
from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.views import APIView

from apps.catalog.models import Village
from apps.pricing.services.booking_redirect import BookingRedirectService
from apps.recommender import engine
from apps.recommender.models import (
    RecoWeights,
    VillageInteraction,
    VillagePopularityCache,
)
from apps.recommender.serializers import (
    BookmarkInputSerializer,
    InteractionStatsResponseSerializer,
    RecommendVillagesInputSerializer,
    RecommendVillagesOutputSerializer,
    RecoWeightsInputSerializer,
    SimilarVillageSerializer,
    VillagePopularityCacheSerializer,
)
from apps.recommender.services.estimate import lightweight_estimate
from apps.recommender.strategies.popularity import seed_villages

logger = logging.getLogger(__name__)


# def _session_id(request, fallback_meta: dict | None = None) -> str:
#     sid = request.headers.get("X-Session-ID") or ""
#     if sid:
#         return sid[:64]
#     if fallback_meta:
#         return (fallback_meta.get("sessionId") or "")[:64]
#     return ""


class RecommendVillagesView(APIView):
    """`POST /api/v2/recommend/villages` — personalized recommendation."""

    throttle_classes = [RecommendIpThrottle]

    @extend_schema(
        request=RecommendVillagesInputSerializer,
        responses=RecommendVillagesOutputSerializer,
    )
    def post(self, request):
        ser = RecommendVillagesInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        family = {
            **d["family"],
            "enfants": [{"age": c["age"]} for c in (d["family"].get("enfants") or [])],
        }
        preferences = d.get("preferences") or {}
        session_id = (d.get("sessionId") or "").strip() or None
        limit = d.get("limit") or 6
        explain = bool(d.get("explain"))

        try:
            result = engine.recommend(
                family=family,
                preferences=preferences,
                session_id=session_id,
                limit=limit,
                explain=explain,
            )
        except Exception:
            logger.exception("recommendation_engine_failed")
            seeds = seed_villages(limit=limit)
            result = engine.RecoResult(
                villages=seeds,
                strategy="popular_fallback",
                confidence=0.05,
                total_scored=0,
                relaxed_filters=["all_filters"],
                fallback_used=True,
            )

        if not result.villages:
            logger.error("recommendation_empty_villages", extra={"session_id": session_id})
            seeds = seed_villages(limit=limit)
            result = engine.RecoResult(
                villages=seeds,
                strategy=result.strategy or "popular_fallback",
                confidence=max(result.confidence, 0.05),
                total_scored=result.total_scored,
                relaxed_filters=result.relaxed_filters or ["all_filters"],
                fallback_used=True,
                ab_group=result.ab_group,
            )

        data = serialize_reco_result(result, include_reasons=explain)
        return CustomResponse.success("Recommendations generated.", data=data)


class SimilarVillagesView(APIView):
    """`GET /api/v2/villages/{id}/similar` — same item shape as recommendations."""

    @extend_schema(
        parameters=[
            OpenApiParameter("id", str, location="path"),
            OpenApiParameter("limit", int, location="query", required=False),
            OpenApiParameter("sessionId", str, location="query", required=False),
        ],
        responses={200: SimilarVillageSerializer(many=True)},
    )
    def get(self, request, id: str):
        try:
            village = Village.objects.get(pk=id)
        except Village.DoesNotExist:
            return CustomResponse.error("Village not found.", status_code=404)

        limit = min(int(request.query_params.get("limit", 3)), 10)
        session_id = (request.query_params.get("sessionId") or "").strip() or "anon"
        explain = request.query_params.get("explain", "").lower() in ("1", "true", "yes")

        others = Village.objects.exclude(pk=id)
        scored = []
        for v in others:
            score = 0.0
            reasons: list[str] = []
            warnings: list[str] = []
            if v.region == village.region:
                score += 0.5
                reasons.append(f"Même région ({village.region})")
            if v.env_code == village.env_code:
                score += 0.3
                reasons.append("Même environnement")
            shared_formules = set(v.formules or []) & set(village.formules or [])
            if shared_formules:
                score += 0.1 * len(shared_formules)
                reasons.append("Formule(s) commune(s)")
            if v.ski == village.ski:
                score += 0.05
            if v.bebe_club == village.bebe_club:
                score += 0.05
            scored.append({
                "village": v,
                "score": round(score, 4),
                "reasons": reasons,
                "warnings": warnings,
                "estimated_total": None,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        top = scored[:limit]

        if not top:
            fallback = list(others.filter(region=village.region)[:1])
            if fallback:
                v = fallback[0]
                top = [{
                    "village": v,
                    "score": 0.1,
                    "reasons": [f"Même région ({village.region})"],
                    "warnings": [],
                    "estimated_total": None,
                }]

        family = {"adultes": 2, "enfants": [], "qfVal": None, "isSoloParent": False}
        preferences = {
            "dates": {
                "debut": timezone.now().date(),
                "fin": (timezone.now() + timedelta(days=7)).date(),
            },
            "formule": (village.formules or ["PC"])[0],
        }

        result_data = []
        for rank, item in enumerate(top, start=1):
            v = item["village"]
            est_total = lightweight_estimate(v, family, preferences)
            item["estimated_total"] = est_total
            item["rank"] = rank
            item["booking_url"] = ""
            try:
                debut = preferences["dates"]["debut"]
                fin = preferences["dates"]["fin"]
                token, _row, _params = BookingRedirectService.create_token(
                    village=v,
                    session_id=session_id,
                    family=family,
                    dates={
                        "debut": debut.isoformat() if hasattr(debut, "isoformat") else str(debut),
                        "fin": fin.isoformat() if hasattr(fin, "isoformat") else str(fin),
                    },
                    context={"source": "similar", "estimatedTotal": est_total},
                )
                item["booking_url"] = f"{settings.API_BASE_URL}/api/v1/go/{token}"
            except Exception:
                pass

            result_data.append(
                serialize_recommended_village(item, include_reasons=explain)
            )

        avg_score = (
            sum(item["score"] for item in top) / len(top) if top else 0.1
        )
        payload = {
            "villages": result_data,
            "strategy": "similar",
            "confidence": round(min(1.0, avg_score), 3),
            "totalScored": others.count(),
            "relaxedFilters": [],
            "fallbackUsed": not top or top[0]["score"] <= 0.15,
            "abGroup": None,
        }
        return CustomResponse.success("Similar villages fetched.", data=payload)


class VillagePopularityCacheView(APIView):
    """`GET /api/v2/village-popularity-cache` — precomputed popularity ranking."""

    @extend_schema(responses=VillagePopularityCacheSerializer(many=True))
    def get(self, request):
        rows = (
            VillagePopularityCache.objects
            .select_related("village")
            .prefetch_related("village__formula_objects")
            .order_by("-score", "village__nom")
        )
        data = VillagePopularityCacheSerializer(rows, many=True).data
        return CustomResponse.success("Village popularity cache fetched.", data=data)


PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90, "all": None}


class InteractionStatsView(StaffAPIViewMixin, APIView):
    """`GET /api/v2/admin/interactions/stats` — staff-only analytics."""

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "period",
                str,
                location="query",
                enum=["7d", "30d", "90d"],
                required=False,
            ),
            OpenApiParameter(
                "start_date",
                OpenApiTypes.DATE,
                location="query",
                description="Inclusive start date filter in YYYY-MM-DD format.",
                required=False,
            ),
            OpenApiParameter(
                "end_date",
                OpenApiTypes.DATE,
                location="query",
                description="Inclusive end date filter in YYYY-MM-DD format.",
                required=False,
            )
        ],
        responses=InteractionStatsResponseSerializer,
    )
    def get(self, request):
        period_raw = request.query_params.get("period")
        period = period_raw or "30d"
        if period_raw and period_raw not in PERIOD_DAYS:
            return CustomResponse.error(
                "Invalid period.",
                errors={"period": ["Allowed values are: 7d, 30d, 90d."]},
            )

        start_date_raw = request.query_params.get("start_date")
        end_date_raw = request.query_params.get("end_date")
        start_date = parse_date(start_date_raw) if start_date_raw else None
        end_date = parse_date(end_date_raw) if end_date_raw else None

        errors = {}
        if start_date_raw and start_date is None:
            errors["start_date"] = ["Use YYYY-MM-DD format."]
        if end_date_raw and end_date is None:
            errors["end_date"] = ["Use YYYY-MM-DD format."]
        if start_date and end_date and end_date < start_date:
            errors["end_date"] = ["Must be on or after start_date."]
        if errors:
            return CustomResponse.error("Invalid date filter.", errors=errors)

        qs = VillageInteraction.objects.all()
        has_custom_date_filter = start_date is not None or end_date is not None
        if period_raw or not has_custom_date_filter:
            cutoff = timezone.now() - timedelta(days=PERIOD_DAYS[period])
            qs = qs.filter(created_at__gte=cutoff)
        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)

        agg = qs.values("village_id", "village__nom", "kind").annotate(count=Count("id"))

        stats: dict[str, dict] = {}
        for row in agg:
            vid = row["village_id"]
            if vid not in stats:
                stats[vid] = {
                    "villageId": vid,
                    "villageNom": row["village__nom"],
                    "views": 0,
                    "simulations": 0,
                    "bookmarks": 0,
                    "total": 0,
                }
            kind = row["kind"]
            if kind == "view":
                stats[vid]["views"] += row["count"]
            elif kind == "simulate":
                stats[vid]["simulations"] += row["count"]
            elif kind == "bookmark":
                stats[vid]["bookmarks"] += row["count"]
            stats[vid]["total"] += row["count"]

        sorted_stats = sorted(stats.values(), key=lambda x: x["total"], reverse=True)
        filters = {
            "period": period if period_raw or not has_custom_date_filter else "custom",
            "villages": sorted_stats,
        }
        if start_date:
            filters["startDate"] = start_date.isoformat()
        if end_date:
            filters["endDate"] = end_date.isoformat()
        return CustomResponse.success(
            "Interaction stats fetched.",
            data=filters,
        )


class RecoWeightsView(StaffAPIViewMixin, APIView):
    """`GET|POST /api/v2/admin/reco-weights` — read/update scoring weights."""

    @extend_schema(responses={200: RecoWeightsInputSerializer})
    def get(self, request):
        return CustomResponse.success("Scoring weights fetched.", data=RecoWeights.active())

    @extend_schema(request=RecoWeightsInputSerializer, responses={200: None})
    def post(self, request):
        ser = RecoWeightsInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        merged = {**RecoWeights.active(), **ser.validated_data}

        RecoWeights.objects.filter(is_active=True).update(is_active=False)
        RecoWeights.objects.create(payload=merged, is_active=True)

        return CustomResponse.success("Scoring weights updated.", data=merged)


def _bookmark_session_id(request, data: dict) -> str | None:
    sid = _session_id(request, {"sessionId": data.get("sessionId", "")}).strip()
    return sid or None


class BookmarkCreateView(APIView):
    """`POST /api/v2/interactions/bookmark` — create bookmark for session+village."""

    @extend_schema(request=BookmarkInputSerializer, responses={200: None})
    def post(self, request):
        ser = BookmarkInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        sid = _bookmark_session_id(request, d)
        if sid is None:
            return CustomResponse.error(
                "Session ID is required.",
                errors={"sessionId": ["Provide sessionId in the request body or X-Session-ID header."]},
            )
        if not Village.objects.filter(pk=d["villageId"]).exists():
            return CustomResponse.error("Village not found.", status_code=404)

        existing = VillageInteraction.objects.filter(
            session_id=sid,
            village_id=d["villageId"],
            kind="bookmark",
        ).order_by("id").first()
        if existing:
            return CustomResponse.success(
                "Bookmark already exists.",
                data={"bookmarked": True, "id": existing.id, "created": False},
            )

        row = VillageInteraction.objects.create(
            session_id=sid,
            village_id=d["villageId"],
            kind="bookmark",
            value=1.0,
            metadata={},
        )
        return CustomResponse.success(
            "Bookmark added.",
            data={"bookmarked": True, "id": row.id, "created": True},
        )


class BookmarkRemoveView(APIView):
    """`POST /api/v2/interactions/bookmark/remove` — remove bookmark for session+village."""

    @extend_schema(request=BookmarkInputSerializer, responses={200: None})
    def post(self, request):
        ser = BookmarkInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        sid = _bookmark_session_id(request, d)
        if sid is None:
            return CustomResponse.error(
                "Session ID is required.",
                errors={"sessionId": ["Provide sessionId in the request body or X-Session-ID header."]},
            )
        if not Village.objects.filter(pk=d["villageId"]).exists():
            return CustomResponse.error("Village not found.", status_code=404)

        existing = VillageInteraction.objects.filter(
            session_id=sid,
            village_id=d["villageId"],
            kind="bookmark",
        )
        if existing.exists():
            deleted, _ = existing.delete()
            return CustomResponse.success(
                "Bookmark removed.",
                data={"bookmarked": False, "removed": deleted},
            )

        return CustomResponse.success(
            "Bookmark does not exist.",
            data={"bookmarked": False, "removed": 0},
        )
