"""CacheOrchestrator — invalidate & warm Redis cache by scope.

Spec §5.1 / US-5.1. Called by:
  - Django signal on PricingRules.save(is_active=True)
  - Management command: python manage.py load_vtf_mocks  (post-load)
  - Admin endpoint: POST /api/v3/admin/cache/rebuild
"""

from __future__ import annotations

import logging
import requests
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone
from django.utils.text import slugify
from datetime import date, datetime

from apps.cache_orchestrator.cache_ops import atomic_cache_set, delete_patterns, monotonic_ms
from apps.cache_orchestrator.key_registry import (
    ACTIVITY_CACHE_COMBOS,
    SCOPE_PATTERNS,
    SEASON_DATE_WARM_SAMPLES,
    TTL_1H,
    TTL_24H,
    TTL_6H,
    TTL_7D,
    TTL_72H,
    activities_cache_key,
    booking_token_cache_key,
    popularity_cache_key,
    region_cache_slug,
    village_detail_cache_key,
)
from apps.cache_orchestrator.models import CacheRebuildLog
from common.discord import add_origin_to_embeds
from common.enums import Region as RegionEnum
from common.enums import Saison
from apps.catalog.filters import ActivityFilter, MarketingSeasonEnvironmentFilter
from apps.catalog.models import (
    Activity,
    Animation,
    Attraction,
    FuelOption,
    Formula,
    LandingMapZone,
    MarketingSeasonEnvironment,
    MarketingSeasons,
    Meal,
    PricingRules,
    Promo,
    Village,
)
from apps.catalog.serializers import (
    ActivitySerializer,
    AnimationSerializer,
    AttractionSerializer,
    FuelOptionSerializer,
    FormulaSerializer,
    LandingMapZoneSerializer,
    MarketingSeasonEnvironmentSerializer,
    # MarketingSeasonsSerializer,
    MealSerializer,
    PricingRulesSerializer,
    PromoSerializer,
    VillageDetailSerializer,
)
from apps.catalog.services.marketing_seasons import marketing_seasons_payload
from apps.recommender.models import VillagePopularityCache
from apps.recommender.serializers import VillagePopularityCacheSerializer
from apps.pricing.services.calendar import date_to_saison_idx, saison_key
from apps.pricing.models import BookingRedirectToken


logger = logging.getLogger(__name__)


class CacheOrchestrator:
    """Scope-aware cache invalidation + warming."""

    @staticmethod
    def rebuild(
        *,
        scope: str = "all",
        reason: str = "",
        triggered_by: str = "system",
    ) -> dict[str, Any]:
        start = monotonic_ms()
        invalidated = 0
        rebuilt = 0

        try:
            invalidated = CacheOrchestrator._invalidate(scope)
            rebuilt = CacheOrchestrator._warm(scope)
        except Exception as exc:
            logger.warning("CacheOrchestrator.rebuild(%s) error: %s", scope, exc)

        duration_ms = monotonic_ms() - start

        try:
            CacheRebuildLog.objects.create(
                scope=scope,
                keys_invalidated=invalidated,
                keys_rebuilt=rebuilt,
                duration_ms=duration_ms,
                triggered_by=triggered_by[:128],
                reason=reason,
            )
        except Exception as exc:
            logger.debug("CacheRebuildLog write skipped: %s", exc)

        summary = {
            "status": "completed",
            "scope": scope,
            "keysInvalidated": invalidated,
            "keysRebuilt": rebuilt,
            "durationMs": duration_ms,
            "triggeredBy": triggered_by,
            "reason": reason,
        }
        logger.info("Cache rebuild %s: %s", scope, summary)
        CacheOrchestrator._maybe_notify(summary)
        return summary

    # ── Invalidation ─────────────────────────────────────────────────────

    @staticmethod
    def _invalidate(scope: str) -> int:
        patterns = CacheOrchestrator._patterns_for_scope(scope)
        return delete_patterns(patterns)

    @staticmethod
    def _patterns_for_scope(scope: str) -> list[str]:
        if scope in SCOPE_PATTERNS:
            return list(SCOPE_PATTERNS[scope])
        if scope.startswith("villages:"):
            vid = scope.split(":", 1)[1]
            return [f"vtf:catalog:villages:{vid}:*"]
        if scope.startswith("regions:"):
            rkey = scope.split(":", 1)[1]
            safe = region_cache_slug(rkey)
            return [f"vtf:catalog:regions:{safe}:*"]
        return [f"vtf:{scope}:*"]

    # ── Warming ──────────────────────────────────────────────────────────

    @staticmethod
    def _warm(scope: str) -> int:
        if scope.startswith("villages:"):
            return CacheOrchestrator._warm_village(scope.split(":", 1)[1])
        if scope.startswith("regions:"):
            return CacheOrchestrator._warm_region(scope.split(":", 1)[1])

        warmed = 0
        if scope in ("all", "catalog"):
            warmed += CacheOrchestrator._warm_catalog()
        if scope in ("all", "pricing"):
            warmed += CacheOrchestrator._warm_pricing()
        if scope in ("all", "recommendations"):
            warmed += CacheOrchestrator._warm_recommendations()
        if scope in ("all", "booking_urls"):
            warmed += CacheOrchestrator._warm_booking_urls()
        return warmed

    @staticmethod
    def _warm_catalog() -> int:
        warmed = 0
        try:
            villages_qs = Village.objects.all().prefetch_related("attractions")

            # Village list cache disabled (client request) — do not warm list keys.
            # cache.set("vtf:catalog:villages:list", ...)

            for village in villages_qs:
                atomic_cache_set(
                    village_detail_cache_key(village.id),
                    VillageDetailSerializer(village).data,
                    TTL_24H,
                )
                warmed += 1

            grouped: dict[str, dict] = {}
            for attraction in Attraction.objects.order_by("nom", "village_id", "km"):
                row = AttractionSerializer(attraction).data
                identifier = slugify(row["nom"])
                item = grouped.get(identifier)
                if item is None:
                    grouped[identifier] = {
                        "id": identifier,
                        "nom": row["nom"],
                        "type": row["type"],
                        "icon": row["icon"],
                        "minKm": row["km"],
                        "villageIds": [attraction.village_id],
                    }
                else:
                    item["minKm"] = min(item["minKm"], row["km"])
                    if attraction.village_id not in item["villageIds"]:
                        item["villageIds"].append(attraction.village_id)

            attractions_data = [
                {**item, "villageIds": sorted(item["villageIds"])}
                for item in grouped.values()
            ]
            attractions_data.sort(key=lambda row: row["id"])
            atomic_cache_set("vtf:catalog:attractions", attractions_data, TTL_24H)
            warmed += 1

            villages = dict(
                Village.objects.values("region")
                .annotate(c=Count("id"))
                .values_list("region", "c")
            )
            free = dict(
                Activity.objects.filter(kind="free")
                .values("region")
                .annotate(c=Count("id"))
                .values_list("region", "c")
            )
            paid = dict(
                Activity.objects.filter(kind="paid")
                .values("region")
                .annotate(c=Count("id"))
                .values_list("region", "c")
            )
            regions_rows = [
                {
                    "key": r,
                    "villageCount": villages.get(r, 0),
                    "freeActivityCount": free.get(r, 0),
                    "paidActivityCount": paid.get(r, 0),
                }
                for r in RegionEnum.values
            ]
            atomic_cache_set("vtf:catalog:regions:list", regions_rows, TTL_7D)
            warmed += 1

            for region_key in RegionEnum.values:
                for kind, season in ACTIVITY_CACHE_COMBOS:
                    qs = ActivityFilter(
                        {"kind": kind, "season": season},
                        queryset=Activity.objects.filter(region=region_key),
                    ).qs
                    atomic_cache_set(
                        activities_cache_key(region_key, kind, season),
                        ActivitySerializer(qs, many=True).data,
                        TTL_24H,
                    )
                    warmed += 1

            atomic_cache_set(
                "vtf:catalog:meals",
                MealSerializer(Meal.objects.all(), many=True).data,
                TTL_7D,
            )
            atomic_cache_set(
                "vtf:catalog:formules",
                FormulaSerializer(Formula.objects.all(), many=True).data,
                TTL_7D,
            )
            atomic_cache_set(
                "vtf:catalog:fuels",
                FuelOptionSerializer(FuelOption.objects.all(), many=True).data,
                TTL_7D,
            )
            atomic_cache_set(
                "vtf:catalog:promos_catalog",
                PromoSerializer(Promo.objects.all(), many=True).data,
                TTL_7D,
            )
            atomic_cache_set(
                "vtf:catalog:animations",
                AnimationSerializer(Animation.objects.all(), many=True).data,
                TTL_7D,
            )
            warmed += 5

            zones = list(LandingMapZone.objects.all())
            landing_villages = []
            for zone in zones:
                for marker in zone.villages:
                    landing_villages.append({**marker, "zoneId": zone.id})
            landing_data = {
                "regions": LandingMapZoneSerializer(zones, many=True).data,
                "villages": landing_villages,
            }
            if landing_data["regions"] or landing_data["villages"]:
                atomic_cache_set("vtf:catalog:landing_map", landing_data, TTL_7D)
                warmed += 1

            # marketing_data = {
            #     "items": MarketingSeasonsSerializer(
            #         MarketingSeasons.objects.all(), many=True
            #     ).data
            # }
            marketing_data = marketing_seasons_payload()
            atomic_cache_set("vtf:catalog:marketing_seasons", marketing_data, TTL_7D)
            warmed += 1

            for season in MarketingSeasons.objects.all():
                env_data = {
                    "marketing_season_key": season.key,
                    "items": MarketingSeasonEnvironmentSerializer(
                        MarketingSeasonEnvironmentFilter(
                            {"marketing_season_key": season.key},
                            queryset=MarketingSeasonEnvironment.objects.all(),
                        ).qs,
                        many=True,
                    ).data,
                }
                atomic_cache_set(
                    f"vtf:catalog:environments:{season.key}",
                    env_data,
                    TTL_7D,
                )
                warmed += 1

        except Exception as exc:
            logger.warning("_warm_catalog error: %s", exc)

        return warmed

    @staticmethod
    def _warm_pricing() -> int:
        warmed = 0
        try:
            rules = PricingRules.objects.filter(is_active=True).first()
            if rules:
                atomic_cache_set(
                    "vtf:catalog:pricing_rules",
                    PricingRulesSerializer(rules).data,
                    TTL_24H,
                )
                warmed += 1

            seasons_rows = [{"key": k, "label": label} for k, label in Saison.choices]
            atomic_cache_set("vtf:catalog:seasons", seasons_rows, TTL_7D)
            warmed += 1

            atomic_cache_set(
                "vtf:catalog:promos_catalog",
                PromoSerializer(Promo.objects.all(), many=True).data,
                TTL_7D,
            )
            warmed += 1

            warmed += CacheOrchestrator._warm_season_dates()
        except Exception as exc:
            logger.warning("_warm_pricing error: %s", exc)
        return warmed

    @staticmethod
    def _warm_season_dates() -> int:
        """Pre-warm common ``GET /season?date=`` lookup keys (spec §5.1)."""
        warmed = 0
        try:
            for raw in SEASON_DATE_WARM_SAMPLES:
                d = date.fromisoformat(raw)
                atomic_cache_set(
                    f"vtf:catalog:season:date:{raw}",
                    {"saisonKey": saison_key(d), "saisonIdx": date_to_saison_idx(d)},
                    TTL_1H,
                )
                warmed += 1
        except Exception as exc:
            logger.warning("_warm_season_dates error: %s", exc)
        return warmed

    @staticmethod
    def _warm_recommendations() -> int:
        warmed = 0
        try:
            rows = VillagePopularityCache.objects.select_related("village").all()
            for row in rows:
                atomic_cache_set(
                    popularity_cache_key(row.village_id),
                    VillagePopularityCacheSerializer(row).data,
                    TTL_6H,
                )
                warmed += 1

            # Re-store CF model if it survived invalidation in another worker (best-effort).
            cf_model = cache.get("vtf:reco:cf_model")
            if cf_model is not None:
                atomic_cache_set("vtf:reco:cf_model", cf_model, TTL_7D)
                warmed += 1
        except Exception as exc:
            logger.warning("_warm_recommendations error: %s", exc)
        return warmed

    @staticmethod
    def _warm_booking_urls() -> int:
        warmed = 0
        try:
            now = timezone.now()
            tokens = BookingRedirectToken.objects.filter(expires_at__gt=now).only(
                "token", "payload", "target_url", "village_id", "session_id"
            )
            for row in tokens.iterator():
                atomic_cache_set(
                    booking_token_cache_key(row.token),
                    {
                        "villageId": row.village_id,
                        "sessionId": row.session_id,
                        "payload": row.payload,
                        "targetUrl": row.target_url,
                    },
                    TTL_72H,
                )
                warmed += 1
        except Exception as exc:
            logger.warning("_warm_booking_urls error: %s", exc)
        return warmed

    @staticmethod
    def _warm_village(village_id: str) -> int:
        try:
            village = Village.objects.prefetch_related("attractions").get(pk=village_id)
            atomic_cache_set(
                village_detail_cache_key(village_id),
                VillageDetailSerializer(village).data,
                TTL_24H,
            )
            return 1
        except Exception as exc:
            logger.warning("_warm_village(%s) error: %s", village_id, exc)
            return 0

    @staticmethod
    def _warm_region(region_key: str) -> int:
        warmed = 0
        try:
            for kind, season in ACTIVITY_CACHE_COMBOS:
                qs = ActivityFilter(
                    {"kind": kind, "season": season},
                    queryset=Activity.objects.filter(region=region_key),
                ).qs
                atomic_cache_set(
                    activities_cache_key(region_key, kind, season),
                    ActivitySerializer(qs, many=True).data,
                    TTL_24H,
                )
                warmed += 1
        except Exception as exc:
            logger.warning("_warm_region(%s) error: %s", region_key, exc)
        return warmed

    @staticmethod
    def _maybe_notify(summary: dict[str, Any]) -> None:
        if not getattr(settings, "CACHE_REBUILD_NOTIFY", False):
            return
        webhook = getattr(settings, "DISCORD_WEBHOOK", "")
        if not webhook:
            return
        try:
            fields = [
                {"name": "Scope", "value": str(summary.get("scope", "unknown")), "inline": True},
                {"name": "Keys Invalidated", "value": str(summary.get("keysInvalidated", 0)), "inline": True},
                {"name": "Keys Rebuilt", "value": str(summary.get("keysRebuilt", 0)), "inline": True},
                {"name": "Duration", "value": f"{summary.get('durationMs', 0)}ms", "inline": True},
                {"name": "Triggered By", "value": str(summary.get("triggeredBy", "system")), "inline": True},
            ]
            reason = summary.get("reason")
            if reason:
                fields.append({"name": "Reason", "value": str(reason), "inline": False})

            payload = {
                "embeds": [
                    {
                        "title": "✅ Cache Rebuild Completed",
                        "color": 0x57F287,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "fields": fields,
                        "footer": {"text": "VTF Cache Orchestrator"},
                    }
                ]
            }
            add_origin_to_embeds(payload)
            response = requests.post(webhook, json=payload, timeout=5)
            if response.status_code != 204:
                logger.warning(
                    "cache_rebuild_notify: discord webhook returned %s: %s",
                    response.status_code,
                    response.text[:200],
                )
        except Exception as exc:
            logger.warning("cache_rebuild_notify_failed: %s", exc)
