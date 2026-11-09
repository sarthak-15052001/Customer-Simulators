"""Catalog read-only views â Phase 1.

Every response uses CustomResponse.success() / CustomResponse.error() so all
responses share the same {success, message, data} envelope.

Caching: TTLs per spec Â§3.3.
    24h  = villages, regions/activities, pricing-rules
    7d   = meals, fuels, promos/catalog, animations, seasons
    1h   = season?date=

Rate limiting: CatalogIpThrottle (1 000 / hour / IP) on every view.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from django.db.models import Count
from django.utils.text import slugify
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import filters, serializers, viewsets
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.views import APIView

from apps.catalog.filters import (
    ActivityFilter,
    MarketingSeasonEnvironmentFilter,
    VillageFilter,
    LandingMapLanguageFilter,
)
from apps.catalog.services.marketing_seasons import marketing_seasons_payload
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
    Region,
    Saison,
    Village,
)
from common.enums import Region, Saison
from apps.catalog.serializers import (
    ActivitySerializer,
    AnimationSerializer,
    AttractionSerializer,
    FuelOptionSerializer,
    FormulaSerializer,
    LandingMapZoneSerializer,
    MarketingSeasonEnvironmentSerializer,
    MarketingSeasonsSerializer,
    MealSerializer,
    PricingRulesSerializer,
    PromoSerializer,
    RegionSummarySerializer,
    SeasonForDateSerializer,
    SeasonSerializer,
    SimulationPdfInputSerializer,
    VillageDetailSerializer,
    VillageListSerializer,
)
from apps.catalog.services.simulation_pdf import build_simulation_pdf
from apps.pricing.services.calendar import date_to_saison_idx, saison_key
from common.response import CustomResponse
from common.throttles import CatalogIpThrottle

logger = logging.getLogger(__name__)

# Cache TTLs
TTL_24H = 60 * 60 * 24
TTL_7D = 60 * 60 * 24 * 7
TTL_1H = 60 * 60


class _DefaultPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


class PdfRenderer(BaseRenderer):
    """Allow DRF content negotiation for endpoints that return raw PDF responses."""

    media_type = "application/pdf"
    format = "pdf"
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b""
        if isinstance(data, bytes):
            return data
        return JSONRenderer().render(data, accepted_media_type, renderer_context)# â”€â”€â”€ Villages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class VillageViewSet(viewsets.ReadOnlyModelViewSet):
    """`GET /api/v1/villages/` and `GET /api/v1/villages/{id}/`."""

    queryset = Village.objects.all().prefetch_related(
        "attractions",
        "infra",
        "clubs",
        "formula_objects",  # Village.formules is now a @property hitting this M2M
    )
    pagination_class = _DefaultPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = VillageFilter
    search_fields = ["nom", "nom2"]
    lookup_field = "id"
    lookup_value_regex = r"[a-z0-9-]+"
    throttle_classes = [CatalogIpThrottle]

    def get_serializer_class(self):
        if self.action == "list":
            return VillageListSerializer
        return VillageDetailSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search_value = self.request.query_params.get("search")
        if search_value:
            queryset = VillageFilter.filter_search(queryset, search_value)
        return queryset

    @extend_schema(
        parameters=[
            OpenApiParameter("region", str, description="Exact match (URL-encoded)."),
            OpenApiParameter(
                "env",
                str,
                description=(
                    "Funnel env: mer/montagne/campagne/ski/fond."
                ),
            ),
            OpenApiParameter("formule", str, description="PC | DP | LOC â€” selects which price perAdultBase reflects (default DP)."),
            OpenApiParameter("ski", bool),
            OpenApiParameter("openOn", str, description="ISO date â€” only villages open then"),
            OpenApiParameter("search", str, description="Substring match on nom/nom2"),
            OpenApiParameter("attractionId", str, description="Slugified attraction name, e.g. pays-basque"),
            OpenApiParameter("dateDebut", str, description="ISO date (YYYY-MM-DD) â€” arrival date; selects the season/week perAdultBase is priced for (default today). Separate from openOn."),
            OpenApiParameter("dateFin", str, description="ISO date (YYYY-MM-DD) â€” departure date; with ?dateDebut=, derives the stay length perAdultBase is priced for (default 7 nights if omitted)."),
        ]
    )
    def list(self, request, *args, **kwargs):
        # Cache disabled for /api/v1/villages/ only.
        # Build a cache key that includes all query params so filtered results
        # are cached separately from the unfiltered list.
        # params_str = "&".join(
        #     f"{k}={v}" for k, v in sorted(request.query_params.items())
        # )
        # cache_key = f"vtf:catalog:villages:list:{params_str}"
        # cached = cache.get(cache_key)
        # if cached is not None:
        #     return CustomResponse.success("Villages fetched successfully.", data=cached)

        logger.info("catalog_villages_list params=%s", dict(request.query_params))
        response = super().list(request, *args, **kwargs)
        # cache.set(cache_key, response.data, TTL_24H)
        count = len(response.data.get("results", [])) if isinstance(response.data, dict) else "unknown"
        logger.info("catalog_villages_list_done count=%s", count)
        return CustomResponse.success("Villages fetched successfully.", data=response.data)

    @extend_schema(
    parameters=[
        OpenApiParameter("formule", str, description="PC | DP | LOC â€” selects which price perAdultBase reflects (default DP)."),
        OpenApiParameter("dateDebut", str, description="ISO date (YYYY-MM-DD) â€” arrival date; selects the season perAdultBase is priced for (default today)."),
        OpenApiParameter("dateFin", str, description="ISO date (YYYY-MM-DD) â€” departure date; with ?dateDebut=, derives the stay length perAdultBase is priced for (default 7 nights if omitted)."),
    ]
)
    def retrieve(self, request, *args, **kwargs):
        village_id = kwargs.get("id", "")
        # IMPORTANT: perAdultBase depends on ?formule=/?dateDebut=/?dateFin=, so
        # the cache key must include them â€” a bare village_id key would silently
        # serve one query's price to every other combo for 24h.
        formule = request.query_params.get("formule", "")
        stay_date = request.query_params.get("dateDebut", "")
        date_fin = request.query_params.get("dateFin", "")
        cache_key = f"vtf:catalog:villages:{village_id}:detail:{formule}:{stay_date}:{date_fin}"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("catalog_village_detail_cache_hit village_id=%s", village_id)
            return CustomResponse.success("Village detail fetched.", data=cached)

        try:
            response = super().retrieve(request, *args, **kwargs)
        except Exception:
            logger.warning("catalog_village_detail_not_found village_id=%s", village_id)
            return CustomResponse.error(
                f"Village '{village_id}' not found.",
                status_code=404,
            )

        cache.set(cache_key, response.data, TTL_24H)
        logger.info("catalog_village_detail_done village_id=%s", village_id)
        return CustomResponse.success("Village detail fetched.", data=response.data)


# â”€â”€â”€ Regions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AttractionListView(APIView):
    """`GET /api/v1/attractions` â€” flat list for Par activitÃ© tiles."""
    throttle_classes = [CatalogIpThrottle]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "env",
                str,
                description=(
                    "Funnel env: mer/montagne/campagne/ski/fond."
                ),
            ),
        ],
        responses=inline_serializer(
            name="AttractionTile",
            fields={
                "id": serializers.CharField(),
                "nom": serializers.CharField(),
                "type": serializers.CharField(),
                "icon": serializers.CharField(),
                "minKm": serializers.IntegerField(),
                "villageIds": serializers.ListField(child=serializers.CharField()),
            },
        )
    )
    def get(self, request):
        env = request.query_params.get("env", "")
        cache_key = f"vtf:catalog:attractions:env={env}"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("catalog_attractions_cache_hit env=%s", env)
            return CustomResponse.success("Attractions fetched.", data=cached)

        grouped: dict[str, dict] = {}
        base_qs = Attraction.objects.order_by("nom", "village_id", "km")
        # Apply env filter when provided
        if env:
            from apps.catalog.filters import AttractionFilter

            qs = AttractionFilter(request.query_params, queryset=base_qs).qs
        else:
            qs = base_qs

        for attraction in qs:
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

        data = [
            {
                **item,
                "villageIds": sorted(item["villageIds"]),
            }
            for item in grouped.values()
        ]
        data.sort(key=lambda row: row["id"])

        cache.set(cache_key, data, TTL_24H)
        logger.info("catalog_attractions_done count=%d", len(data))
        return CustomResponse.success("Attractions fetched.", data=data)


class RegionListView(APIView):
    """`GET /api/v1/regions` â€” village/activity counts per region."""
    throttle_classes = [CatalogIpThrottle]

    @extend_schema(responses=RegionSummarySerializer(many=True))
    def get(self, request):
        cache_key = "vtf:catalog:regions:list"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("catalog_regions_cache_hit")
            return CustomResponse.success("Regions fetched.", data=cached)

        villages = dict(
            Village.objects.values("region").annotate(c=Count("id")).values_list("region", "c")
        )
        free = dict(
            Activity.objects.filter(kind="free")
            .values("region").annotate(c=Count("id")).values_list("region", "c")
        )
        paid = dict(
            Activity.objects.filter(kind="paid")
            .values("region").annotate(c=Count("id")).values_list("region", "c")
        )
        rows = [
            {
                "key": r,
                "villageCount": villages.get(r, 0),
                "freeActivityCount": free.get(r, 0),
                "paidActivityCount": paid.get(r, 0),
            }
            for r in Region.values
        ]
        cache.set(cache_key, rows, TTL_7D)
        logger.info("catalog_regions_done count=%d", len(rows))
        return CustomResponse.success("Regions fetched.", data=rows)


class RegionActivitiesView(APIView):
    """`GET /api/v1/regions/{region}/activities`."""
    throttle_classes = [CatalogIpThrottle]

    @extend_schema(
        parameters=[
            OpenApiParameter("kind", str, description="free | paid"),
            OpenApiParameter("season", str, description="hs | vs | ete | fetes"),
        ],
        responses=ActivitySerializer(many=True),
    )
    def get(self, request, region: str):
        if region not in Region.values:
            logger.warning("catalog_region_activities_invalid_region region=%s", region)
            return CustomResponse.error(
                f"Region '{region}' not found. Valid regions: {list(Region.values)}",
                status_code=404,
            )

        kind = request.query_params.get("kind", "")
        season = request.query_params.get("season", "")
        safe_region = region.replace(" ", "_").replace("/", "-")
        cache_key = f"vtf:catalog:regions:{safe_region}:activities:{kind}:{season}"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(
                "catalog_region_activities_cache_hit region=%s kind=%s season=%s",
                region,
                kind,
                season,
            )
            return CustomResponse.success("Activities fetched.", data=cached)

        qs = ActivityFilter(
            request.query_params,
            queryset=Activity.objects.filter(region=region),
        ).qs

        data = ActivitySerializer(qs, many=True).data
        cache.set(cache_key, data, TTL_24H)
        logger.info(
            "catalog_region_activities_done region=%s kind=%s season=%s count=%d",
            region,
            kind,
            season,
            len(data),
        )
        return CustomResponse.success("Activities fetched.", data=data)


# â”€â”€â”€ Seasons â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class SeasonListView(APIView):
    """`GET /api/v1/seasons` â€” four canonical season keys + labels."""
    throttle_classes = [CatalogIpThrottle]

    @extend_schema(responses=SeasonSerializer(many=True))
    def get(self, request):
        cache_key = "vtf:catalog:seasons"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("catalog_seasons_cache_hit")
            return CustomResponse.success("Seasons fetched.", data=cached)

        rows = [{"key": k, "label": label} for k, label in Saison.choices]
        cache.set(cache_key, rows, TTL_7D)
        logger.info("catalog_seasons_done count=%d", len(rows))
        return CustomResponse.success("Seasons fetched.", data=rows)


class SeasonForDateView(APIView):
    """`GET /api/v1/season?date=YYYY-MM-DD`."""
    throttle_classes = [CatalogIpThrottle]

    @extend_schema(
        parameters=[OpenApiParameter("date", str, required=True)],
        responses=SeasonForDateSerializer,
    )
    def get(self, request):
        raw = request.query_params.get("date")
        if not raw:
            logger.warning("catalog_season_for_date_missing_date")
            return CustomResponse.error(
                "Query parameter 'date' is required. Example: ?date=2026-07-15",
                status_code=400,
            )
        try:
            d = date.fromisoformat(raw)
        except ValueError:
            logger.warning("catalog_season_for_date_invalid_date raw=%s", raw)
            return CustomResponse.error(
                f"Invalid date '{raw}'. Use ISO format YYYY-MM-DD.",
                status_code=400,
            )

        cache_key = f"vtf:catalog:season:date:{raw}"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("catalog_season_for_date_cache_hit date=%s", raw)
            return CustomResponse.success("Season for date fetched.", data=cached)

        data = {"saisonKey": saison_key(d), "saisonIdx": date_to_saison_idx(d)}
        cache.set(cache_key, data, TTL_1H)
        logger.info(
            "catalog_season_for_date_done date=%s saison_key=%s saison_idx=%s",
            raw,
            data["saisonKey"],
            data["saisonIdx"],
        )
        return CustomResponse.success("Season for date fetched.", data=data)


# â”€â”€â”€ Reference data â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class MealListView(APIView):
    throttle_classes = [CatalogIpThrottle]

    @extend_schema(responses=MealSerializer(many=True))
    def get(self, request):
        cache_key = "vtf:catalog:meals"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("catalog_meals_cache_hit")
            return CustomResponse.success("Meals fetched.", data=cached)
        data = MealSerializer(Meal.objects.all(), many=True).data
        cache.set(cache_key, data, TTL_7D)
        logger.info("catalog_meals_done count=%d", len(data))
        return CustomResponse.success("Meals fetched.", data=data)


class FormulaListView(APIView):
    throttle_classes = [CatalogIpThrottle]

    @extend_schema(responses=FormulaSerializer(many=True))
    def get(self, request):
        cache_key = "vtf:catalog:formules"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("catalog_formules_cache_hit")
            return CustomResponse.success("Formules fetched.", data=cached)
        data = FormulaSerializer(Formula.objects.all(), many=True).data
        cache.set(cache_key, data, TTL_7D)
        logger.info("catalog_formules_done count=%d", len(data))
        return CustomResponse.success("Formules fetched.", data=data)


class LandingMapView(APIView):
    """`GET /api/v1/landing/map` â dynamic France index map data with language filtering."""

    throttle_classes = [CatalogIpThrottle]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "lang",
                str,
                description="Language code: FR (default), GB, ES, NL. ES/NL redirect to FR.",
            ),
        ],
        responses=inline_serializer(
            name="LandingMapResponse",
            fields={
                "regions": LandingMapZoneSerializer(many=True),
                "villages": serializers.ListField(child=serializers.DictField()),
            },
        )
    )
    def get(self, request):
        # Get language parameter from query string (default: FR)
        language = request.query_params.get("lang", "FR")

        # Include language in cache key to separate results by language
        cache_key = f"vtf:catalog:landing_map:{language.upper()}"
        cached = cache.get(cache_key)
        if cached is not None and (cached.get("regions") or cached.get("villages")):
            logger.info(
                "catalog_landing_map_cache_hit lang=%s regions=%d villages=%d",
                language,
                len(cached.get("regions") or []),
                len(cached.get("villages") or []),
            )
            return CustomResponse.success("Landing map fetched.", data=cached)

        zones = list(LandingMapZone.objects.all())
        villages = []
        for zone in zones:
            for marker in zone.villages:
                villages.append({**marker, "zoneId": zone.id})

        regions_data = LandingMapZoneSerializer(zones, many=True).data
        
        # Apply language-based filtering
        regions_data, villages = LandingMapLanguageFilter(language).apply(
            regions_data, villages
        )

        data = {
            "regions": regions_data,
            "villages": villages,
        }
        if data["regions"] or data["villages"]:
            cache.set(cache_key, data, TTL_7D)
        logger.info(
            "catalog_landing_map_done lang=%s regions=%d villages=%d",
            language,
            len(data["regions"]),
            len(data["villages"]),
        )
        return CustomResponse.success("Landing map fetched.", data=data)



class FuelListView(APIView):
    throttle_classes = [CatalogIpThrottle]

    @extend_schema(responses=FuelOptionSerializer(many=True))
    def get(self, request):
        cache_key = "vtf:catalog:fuels"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("catalog_fuels_cache_hit")
            return CustomResponse.success("Fuels fetched.", data=cached)
        data = FuelOptionSerializer(FuelOption.objects.all(), many=True).data
        cache.set(cache_key, data, TTL_7D)
        logger.info("catalog_fuels_done count=%d", len(data))
        return CustomResponse.success("Fuels fetched.", data=data)


class PromoCatalogView(APIView):
    throttle_classes = [CatalogIpThrottle]

    @extend_schema(responses=PromoSerializer(many=True))
    def get(self, request):
        cache_key = "vtf:catalog:promos_catalog"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("catalog_promos_cache_hit")
            return CustomResponse.success("Promos fetched.", data=cached)
        data = PromoSerializer(Promo.objects.all(), many=True).data
        cache.set(cache_key, data, TTL_7D)
        logger.info("catalog_promos_done count=%d", len(data))
        return CustomResponse.success("Promos fetched.", data=data)


class AnimationListView(APIView):
    throttle_classes = [CatalogIpThrottle]

    @extend_schema(responses=AnimationSerializer(many=True))
    def get(self, request):
        cache_key = "vtf:catalog:animations"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("catalog_animations_cache_hit")
            return CustomResponse.success("Animations fetched.", data=cached)
        data = AnimationSerializer(Animation.objects.all(), many=True).data
        cache.set(cache_key, data, TTL_7D)
        logger.info("catalog_animations_done count=%d", len(data))
        return CustomResponse.success("Animations fetched.", data=data)


# class MarketingSeasonsView(APIView):
#     """`GET /api/v1/marketing-seasons` â marketing seasons with no pagination."""
#     throttle_classes = [CatalogIpThrottle]

#     @extend_schema(
#         responses=inline_serializer(
#             name="MarketingSeasonsResponse",
#             fields={
#                 "items": MarketingSeasonsSerializer(many=True),
#             },
#         )
#     )
#     def get(self, request):
#         cache_key = "vtf:catalog:marketing_seasons"
#         cached = cache.get(cache_key)
#         if cached is not None:
#             logger.info("catalog_marketing_seasons_cache_hit")
#             return CustomResponse.success("Marketing seasons fetched.", data=cached)

#         data = {
#             "items": MarketingSeasonsSerializer(
#                 MarketingSeasons.objects.all(), many=True
#             ).data
#         }
#         # Normalize season dates to the next upcoming occurrence (dynamic years)
#         # and compute a default date that is a Saturday (frontend expects weekend start).
#         today = date.today()
#         def _next_weekend_within(start_d: date, end_d: date, after: date) -> tuple[date, date]:
#             """Return (saturday, sunday) where saturday is the first Saturday >= max(after, start_d)
#             and both days are within [start_d, end_d]. If no Saturday fits, return (start_d, start_d+1).
#             """
#             cur = max(after, start_d)
#             for i in range(0, 366):
#                 cand = cur + timedelta(days=i)
#                 if cand.weekday() == 5 and cand <= end_d:
#                     sat = cand
#                     sun = sat + timedelta(days=1)
#                     # ensure sunday within window; if not, clamp to end_d
#                     if sun > end_d:
#                         sun = end_d
#                     return sat, sun
#             # fallback: clamp to start of the season window
#             sat = start_d
#             sun = min(start_d + timedelta(days=1), end_d)
#             return sat, sun

#         for item in data["items"]:
#             try:
#                 # serializer uses camelCase keys
#                 orig_start = date.fromisoformat(item.get("startDate"))
#                 orig_end = date.fromisoformat(item.get("endDate"))
#             except Exception:
#                 continue
#             # shift years so the resulting end_date is >= today when possible
#             year_offset = today.year - orig_end.year
#             cand_start = orig_start.replace(year=orig_start.year + year_offset)
#             cand_end = orig_end.replace(year=orig_end.year + year_offset)
#             if cand_end < today:
#                 cand_start = cand_start.replace(year=cand_start.year + 1)
#                 cand_end = cand_end.replace(year=cand_end.year + 1)

#             # compute default weekend start (Saturday) and default end (Saturday+7 days)
#             default_sat, _ = _next_weekend_within(cand_start, cand_end, today)
#             default_end = default_sat + timedelta(days=7)
#             if default_end > cand_end:
#                 # clamp to season end if full week doesn't fit
#                 default_end = cand_end

#             item["startDate"] = cand_start.isoformat()
#             item["endDate"] = cand_end.isoformat()
#             item["defaultDate"] = default_sat.isoformat()
#             # item["defaultStartDate"] = default_sat.isoformat()
#             # item["defaultEndDate"] = default_end.isoformat()

#             # For winter, include sales opening date (10 June of current year)
#             try:
#                 key = item.get("key")
#                 if key == "hiver":
#                     sales_open = date(today.year, 6, 10)
#                     item["salesOpenDate"] = sales_open.isoformat()
#             except Exception:
#                 pass
#             # Mark whether this season is the current sales season (today within season window)
#             try:
#                 item["currentSalesSeason"] = cand_start <= today <= cand_end
#             except Exception:
#                 item["currentSalesSeason"] = False
#         cache.set(cache_key, data, TTL_7D)
#         logger.info("catalog_marketing_seasons_done count=%d", len(data["items"]))
#         return CustomResponse.success("Marketing seasons fetched.", data=data)


class MarketingSeasonsView(APIView):
    """`GET /api/v1/marketing-seasons` â marketing seasons with no pagination."""
    throttle_classes = [CatalogIpThrottle]
 
    @extend_schema(
        responses=inline_serializer(
            name="MarketingSeasonsResponse",
            fields={
                "items": MarketingSeasonsSerializer(many=True),
            },
        )
    )
    def get(self, request):
        cache_key = "vtf:catalog:marketing_seasons"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info("catalog_marketing_seasons_cache_hit")
            return CustomResponse.success("Marketing seasons fetched.", data=cached)
 
        # marketing_seasons_payload() reads the DB fresh and rolls each
        # season's dates to the current real-world year on every call â
        # this works whether or not load_vtf_mocks has been re-run since
        # a year boundary passed, and whether the DB rows still carry the
        # fixture's anchor year or already-current dates.
        data = marketing_seasons_payload()
 
        cache.set(cache_key, data, TTL_7D)
        logger.info("catalog_marketing_seasons_done count=%d", len(data["items"]))
        return CustomResponse.success("Marketing seasons fetched.", data=data)


class EnvironmentsBySeasonView(APIView):
    """`GET /api/v1/environments?marketing_season_key={key}` â funnel environments by season."""
    throttle_classes = [CatalogIpThrottle]

    @extend_schema(
        parameters=[
            OpenApiParameter("marketing_season_key", str, required=True, description="Season key: ete, hiver, printemps, automne"),
        ],
        responses=inline_serializer(
            name="EnvironmentsBySeasonResponse",
            fields={
                "marketing_season_key": serializers.CharField(),
                "items": serializers.ListField(
                    child=inline_serializer(
                        name="EnvironmentBySeasonItem",
                        fields={
                            "key": serializers.CharField(),
                            "icon": serializers.CharField(),
                            "label": serializers.CharField(),
                            "sub": serializers.CharField(),
                        },
                    )
                ),
            },
        ),
    )
    def get(self, request):
        marketing_season_key = request.query_params.get("marketing_season_key")
        
        # Validate required parameter
        if not marketing_season_key:
            logger.warning("catalog_environments_missing_marketing_season_key")
            return CustomResponse.error(
                "Query parameter 'marketing_season_key' is required. Valid values: ete, hiver, printemps, automne",
                status_code=400,
            )

        # Check if season exists
        if not MarketingSeasons.objects.filter(key=marketing_season_key).exists():
            logger.warning(
                "catalog_environments_invalid_marketing_season key=%s",
                marketing_season_key,
            )
            return CustomResponse.error(
                f"Marketing season '{marketing_season_key}' not found. Valid values: ete, hiver, printemps, automne",
                status_code=404,
            )

        # Build cache key
        cache_key = f"vtf:catalog:environments:{marketing_season_key}"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(
                "catalog_environments_cache_hit marketing_season_key=%s",
                marketing_season_key,
            )
            return CustomResponse.success("Environments fetched.", data=cached)

        data = {
            "marketing_season_key": marketing_season_key,
            "items": MarketingSeasonEnvironmentSerializer(
                MarketingSeasonEnvironmentFilter(
                    request.query_params,
                    queryset=MarketingSeasonEnvironment.objects.all(),
                ).qs,
                many=True,
            ).data,
        }
        
        cache.set(cache_key, data, TTL_7D)
        logger.info(
            "catalog_environments_done marketing_season_key=%s count=%d",
            marketing_season_key,
            len(data["items"]),
        )
        return CustomResponse.success("Environments fetched.", data=data)


class PricingRulesView(APIView): 
    throttle_classes = [CatalogIpThrottle]

    @extend_schema(responses=PricingRulesSerializer)
    def get(self, request):  
        cache_key = "vtf:catalog:pricing_rules"  
        cached = cache.get(cache_key) 
        if cached is not None:  
            logger.info("catalog_pricing_rules_cache_hit")
            return CustomResponse.success("Pricing rules fetched.", data=cached)

        rules = PricingRules.objects.filter(is_active=True).first()
        if rules is None: 
            logger.warning("catalog_pricing_rules_missing_active")
            return CustomResponse.error(
                "No active pricing rules found. Please run load_vtf_mocks.",
                status_code=503, 
            )
        data = PricingRulesSerializer(rules).data 
        cache.set(cache_key, data, TTL_24H)  
        logger.info("catalog_pricing_rules_done rules_id=%s", rules.pk)
        return CustomResponse.success("Pricing rules fetched.", data=data)  


# âââ Health âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

@extend_schema(
    responses=inline_serializer(
        name="HealthResponse",
        fields={
            "status": serializers.CharField(),
            "version": serializers.CharField(),
            "dataVersion": serializers.CharField(allow_null=True),
            "villageCount": serializers.IntegerField(),
            "cache": serializers.DictField(),
        },
    ),
)
@api_view(["GET"])
@throttle_classes([CatalogIpThrottle])
def health_view(request):
    """`GET /api/v1/health` â version + data freshness."""
    rules = PricingRules.objects.filter(is_active=True).first()
    villages_count = Village.objects.count()

    try:
        from apps.cache_orchestrator.cache_ops import collect_cache_health_stats
        from apps.cache_orchestrator.models import CacheRebuildLog

        cache_info = collect_cache_health_stats()
        last_rebuild = CacheRebuildLog.objects.order_by("-created_at").first()
        if last_rebuild:
            cache_info["lastRebuild"] = last_rebuild.created_at.isoformat()
            cache_info["lastRebuildScope"] = last_rebuild.scope
            cache_info["lastRebuildDurationMs"] = last_rebuild.duration_ms
    except Exception:
        backend = cache.__class__.__name__
        cache_info = {
            "backend": "redis" if "Redis" in backend else "locmem",
            "connected": False,
        }
        logger.debug("catalog_health_cache_check_failed", exc_info=True)

    data = {
        "status": "ok",
        "version": "0.1.0",
        "dataVersion": rules.updated_at.isoformat() if rules else None,
        "villageCount": villages_count,
        "cache": cache_info,
    }
    logger.info(
        "catalog_health_done village_count=%d cache_backend=%s cache_connected=%s",
        villages_count,
        cache_info["backend"],
        cache_info["connected"],
    )
    return CustomResponse.success("API is healthy.", data=data)



# âââ Simulation PDF ââââââââââââââââââââââââââââââââââââââââââââââââââ

class SimulationPdfView(APIView):
    """`POST /api/v1/simulations/pdf/` â generate a simulation PDF."""

    # PDF-only: avoid DRF advertising multiple formats (Swagger "format" dropdown).
    renderer_classes = [PdfRenderer]

    @extend_schema(
        tags=["PDF"],
        request=SimulationPdfInputSerializer,
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    def post(self, request):
        serializer = SimulationPdfInputSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                "catalog_simulation_pdf_invalid_payload errors=%s",
                serializer.errors,
            )
            return HttpResponse(
                JSONRenderer().render(
                    {
                        "success": False,
                        "message": "Invalid simulation PDF payload.",
                        "data": None,
                        "errors": serializer.errors,
                    }
                ),
                status=400,
                content_type="application/json",
            )

        pdf = build_simulation_pdf(serializer.validated_data)
        response = HttpResponse(pdf.content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{pdf.filename}"'
        logger.info(
            "catalog_simulation_pdf_done filename=%s bytes=%d",
            pdf.filename,
            len(pdf.content),
        )
        return response
