"""django-filter FilterSets for catalog endpoints."""
from __future__ import annotations

from datetime import date

import django_filters
from django.db.models import Q
from django.utils.text import slugify
from urllib.parse import urlparse

from apps.catalog.models import (
    Activity,
    Attraction,
    LandingMapZone,
    MarketingSeasonEnvironment,
    MarketingSeasons,
    Village,
)
from apps.pricing.services.calendar import is_village_ouvert


def _truthy(value: str | bool | None) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    return value.lower() in {"1", "true", "yes", "y", "on"}


class VillageFilter(django_filters.FilterSet):
    region = django_filters.CharFilter(method="filter_region")
    env = django_filters.CharFilter(method="filter_env")
    formule = django_filters.CharFilter(method="filter_formule")
    ski = django_filters.CharFilter(method="filter_ski")
    openOn = django_filters.CharFilter(method="filter_open_on")
    attractionId = django_filters.CharFilter(method="filter_attraction_id")

    # Funnel keywords that "search" should also recognize, mapped onto env_code/ski
    ENV_KEYWORDS = {
        "mer": Q(env_code="sea"),
        "montagne": (
            (Q(env_code__in=["mountain", "forest"]) & Q(ski=False))
            | (Q(env_code="forest") & Q(ski=True))
            | (Q(env_code="mountain") & Q(ski=True))
        ),
        "campagne": (
            Q(env_code="countryside")
            | (Q(ski=False) & ~Q(env_code__in=["sea", "mountain"]))
        ),
        "ski": Q(ski=True),
        "fond": (
            Q(env_code="forest")
            | (
                Q(ski=False)
                & Q(env_code="mountain")
                & Q(id__in=["savines", "talloires", "areches"])
            )
        ),
    }

    class Meta:
        model = Village
        fields = []

    def filter_region(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(region=value)

    def filter_env(self, queryset, name, value):
        if not value:
            return queryset

        env = value.lower()
        if env == "mer":
            return queryset.filter(env_code="sea")
        # if env == "montagne":
        #     # Include regular montagne (mountain/forest + ski=False) and nordic resorts (forest + ski=True)
        #     return queryset.filter(
        #         (Q(env_code__in=["mountain", "forest"]) & Q(ski=False))
        #         | (Q(env_code="forest") & Q(ski=True))
        #     )
        if env == "montagne":
            # Mountain/forest villages regardless of ski flag — env=montagne is sent for
            # Printemps/Été/Automne (never Hiver), so summer-open ski villages like
            # Arvieux (mountain+ski) and Font d'Urle (forest+ski) must be included.
            return queryset.filter(
                (Q(env_code__in=["mountain", "forest"]) & Q(ski=False))
                | (Q(env_code="forest") & Q(ski=True))
                | (Q(env_code="mountain") & Q(ski=True))
            )
        
        if env == "campagne":
            return queryset.filter(
                Q(env_code="countryside")
                | (Q(ski=False) & ~Q(env_code__in=["sea", "mountain"]))
            )
        if env == "ski":
            return queryset.filter(ski=True)
        if env == "fond":
            return queryset.filter(
                Q(env_code="forest")
                | (
                    Q(ski=False)
                    & Q(env_code="mountain")
                    & Q(id__in=["savines", "talloires", "areches"])
                )
            )
        return queryset.none()

    def filter_formule(self, queryset, name, value):
        if not value:
            return queryset

        # SQLite-safe JSON containment fallback.
        # matching_ids = [v.id for v in queryset if value in (v.formules or [])]
        # return queryset.filter(id__in=matching_ids)

        return queryset.filter(formula_objects__code=value).distinct()

    def filter_ski(self, queryset, name, value):
        ski = _truthy(value)
        if ski is None:
            return queryset
        return queryset.filter(ski=ski)

    def filter_open_on(self, queryset, name, value):
        if not value:
            return queryset

        try:
            open_on = date.fromisoformat(value)
        except ValueError:
            return queryset.none()

        matching_ids = [
            village.id
            for village in queryset
            if is_village_ouvert(village.ouverture, open_on)
        ]
        return queryset.filter(id__in=matching_ids)

    def filter_attraction_id(self, queryset, name, value):
        if not value:
            return queryset

        matching_village_ids = [
            attraction.village_id
            for attraction in Attraction.objects.all()
            if slugify(attraction.nom) == value
        ]
        return queryset.filter(id__in=matching_village_ids)
    
    def filter_queryset(self, queryset):
        """Override to extend SearchFilter's plain nom/nom2 match with region/env keywords.

        DRF's SearchFilter runs as a separate filter_backend (not part of this FilterSet),
        so it can't be overridden here directly. Instead, the view's `search` param is
        intercepted in VillageViewSet.list/get_queryset and combined with this method —
        see filter_search below, called explicitly from the view.
        """
        return super().filter_queryset(queryset)
    
    @classmethod
    def filter_search(cls, queryset, value):
        """Extend search to also match against region (substring) and env funnel keywords.

        Called explicitly from the view alongside DRF's SearchFilter, since SearchFilter
        only knows about `search_fields = ["nom", "nom2"]` and has no knowledge of region/env.
        """
        if not value:
            return queryset

        keyword = value.strip().lower()
        extra_q = Q(region__icontains=value) | Q(nom__icontains=value) | Q(nom2__icontains=value)

        env_q = cls.ENV_KEYWORDS.get(keyword)
        if env_q is not None:
            extra_q |= env_q

        # If the search term is a marketing season (key or label), include
        # villages matching any environment available for that season
        try:
            season_qs = MarketingSeasons.objects.filter(key__iexact=keyword) | MarketingSeasons.objects.filter(label__icontains=value)
            if season_qs.exists():
                season = season_qs.first()
                env_keys = list(season.environments.values_list("key", flat=True))
                season_env_q = None
                for k in env_keys:
                    eq = cls.ENV_KEYWORDS.get(k)
                    if eq is not None:
                        season_env_q = eq if season_env_q is None else (season_env_q | eq)
                # If we have environment Q, narrow to villages matching those
                # environments AND that are open on the season's default date.
                if season_env_q is not None:
                    # Collect candidate village ids from the provided queryset
                    candidate_qs = queryset.filter(season_env_q)
                    try:
                        default_date = season.default_date
                        matching_ids = [v.id for v in candidate_qs if is_village_ouvert(v.ouverture, default_date)]
                    except Exception:
                        matching_ids = list(candidate_qs.values_list("id", flat=True))
                    if matching_ids:
                        extra_q |= Q(id__in=matching_ids)
        except Exception:
            # Non-fatal: don't break search if DB/model not available
            pass

        # Also include villages referenced by landing map zones whose name
        # matches the search term (e.g. searching "Occitanie" should include
        # villages listed in the Occitanie landing map zone even if their
        # `region` field doesn't match exactly).
        try:
            zone_qs = LandingMapZone.objects.filter(name__icontains=value)
            zone_village_ids: list[str] = []
            for zone in zone_qs:
                for item in getattr(zone, "villages", []) or []:
                    vid = item.get("villageId")
                    if vid:
                        zone_village_ids.append(vid)
            if zone_village_ids:
                extra_q |= Q(id__in=zone_village_ids)
        except Exception:
            # Don't fail search if LandingMapZone isn't available or DB issue;
            # keep original behaviour.
            pass

        return queryset.filter(extra_q).distinct()


class ActivityFilter(django_filters.FilterSet):
    kind = django_filters.CharFilter(method="filter_kind")
    season = django_filters.CharFilter(method="filter_season")

    class Meta:
        model = Activity
        fields = []

    def filter_kind(self, queryset, name, value):
        if value in {Activity.KIND_FREE, Activity.KIND_PAID}:
            return queryset.filter(kind=value)
        return queryset

    def filter_season(self, queryset, name, value):
        if not value:
            return queryset

        # SQLite-safe JSON containment fallback. Empty saisons means all seasons.
        matching_ids = [
            activity.id
            for activity in queryset
            if not activity.saisons or value in activity.saisons
        ]
        return queryset.filter(id__in=matching_ids)


class MarketingSeasonEnvironmentFilter(django_filters.FilterSet):
    marketing_season_key = django_filters.CharFilter(
        field_name="marketing_season_id",
        lookup_expr="exact",
    )

    class Meta:
        model = MarketingSeasonEnvironment
        fields = []


class AttractionFilter(django_filters.FilterSet):
    env = django_filters.CharFilter(method="filter_env")

    class Meta:
        model = Attraction
        fields = []

    def filter_env(self, queryset, name, value):
        if not value:
            return queryset

        env = value.lower()
        if env == "mer":
            return queryset.filter(village__env_code="sea")
        if env == "montagne":
            return queryset.filter(village__env_code__in=["mountain", "forest"], village__ski=False)
        if env == "campagne":
            return queryset.filter(
                Q(village__env_code="countryside")
                | (Q(village__ski=False) & ~Q(village__env_code__in=["sea", "mountain"]))
            )
        if env == "ski":
            return queryset.filter(village__ski=True)
        if env == "fond":
            return queryset.filter(
                Q(village__env_code="forest")
                | (
                    Q(village__ski=False)
                    & Q(village__env_code="mountain")
                    & Q(village__id__in=["savines", "talloires", "areches"])
                )
            )
        return queryset.none()


# ─── Language Filter for Landing Map ──────────────────────────────────────


class LandingMapLanguageFilter:
    """Applies language filtering to landing map data.

    Language Behavior:
        - FR (default): Return France data as-is.
        - GB: Transform href from /fr_FR/ to /en_GB/, show English site.
        - ES, NL: Return France data (redirect to French site).
    """

    DEFAULT_LANGUAGE = "FR"
    SUPPORTED_LANGUAGES = {"FR", "GB", "ES", "NL"}
    FR_PATH_SEGMENT = "/fr_FR/"
    GB_PATH_SEGMENT = "/en_GB/"

    def __init__(self, language: str | None = None):
        self.language = (language or self.DEFAULT_LANGUAGE).upper().strip()

    def apply(self, zones_data: list, villages_data: list) -> tuple[list, list]:
        """Apply language filtering to landing map data.

        Args:
            zones_data: List of serialized zone objects.
            villages_data: List of village marker objects.

        Returns:
            Tuple of (filtered_zones_data, filtered_villages_data).
        """
        if self.language == "GB":
            return zones_data, self._transform_villages_to_gb(villages_data)

        # ES, NL, FR, or unknown → return data as-is (French/default)
        return zones_data, villages_data

    # Some VTF cities have a shorter name in the en_GB final-slug prefix than
    # the city path segment.  Map: fr_city_segment → en_GB_slug_prefix.
    # Only add entries here when the real en_GB URL on vtf-vacances.com differs
    # from the auto-constructed "{city}-{slug}-vtf-holiday-village" pattern.
    GB_CITY_SLUG_PREFIX_OVERRIDES: dict[str, str] = {
        "saint-sauves-d-auvergne": "saint-sauves",
    }

    # ROOT CAUSE of the broken GB links: the code below reconstructs an
    # en_GB URL purely by string-munging the FR path (same department
    # segment, same city segment, same season, city+slug then hardcoded
    # "-vtf-holiday-village" suffix). That reconstruction is wrong whenever
    # the real vtf-vacances.com English page differs from the FR page in
    # ANY of those parts, which turns out to happen a lot. Confirmed by
    # fetching the live en_GB site for all 16 villages the user reported
    # as broken; every one differs from the auto-construction in at least
    # one of these ways:
    #   - suffix isn't "-vtf-holiday-village": montgenevre/praloup/bandol
    #     use "-vtf-hotel"; sainte-maxime uses "-vtf-vvf-holiday-village"
    #   - department segment is translated, not just re-cased: "savoie"
    #     (FR) -> "savoy" (GB); "manche" -> "channel"
    #   - city segment differs from the FR one: montricher-albanne's real
    #     GB city segment is "montricher-albanne" but the slug is built
    #     from "karellis"; doucy's GB city segment is
    #     "doucy-combelouviere", not the FR "doucy-combebouviere"
    #   - slug drops the French definite article "le/la/les": cereste and
    #     agde's real slugs omit the leading "le-"/"domaine" article that
    #     the FR path has, and le-sauze's city prefix is shortened
    #   - the season differs: alpe-dhuez and font-durle are under
    #     /winter/ on the real English site even though the FR fixture
    #     href uses /summer/
    # Because the wrong part varies per-village, there's no reliable
    # partial fix (translating just the department, or just the suffix,
    # still leaves other villages broken). Instead this maps villageId
    # straight to the full, verified-correct en_GB URL.
    GB_FULL_HREF_OVERRIDES: dict[str, str] = {
        "montgenevre": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/hautes-alpes/montgenevre/montgenevre-le-grand-hotel-vtf-hotel",
        "doucy": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/savoy/doucy-combelouviere/doucy-valmorel-les-carlines-vtf-holiday-village",
        "la-plagne": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/savoy/la-plagne-montalbert/plagne-montalbert-le-dou-de-la-ramaz-vtf-holiday-village",
        "alpe-dhuez": "https://www.vtf-vacances.com/en_GB/winter/holiday-resort/isere/alpe-d-huez/le-balcon-de-l-alpe-vtf-holiday-village",
        "montricher-albanne": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/savoy/montricher-albanne/karellis-balcons-de-maurienne-vtf-holiday-village",
        "font-durle": "https://www.vtf-vacances.com/en_GB/winter/holiday-resort/drome/bouvante/font-urle-vtf-holiday-village",
        "saint-cast": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/cotes-d-armor/saint-cast-le-guildo/saint-cast-le-guildo-l-hotel-des-bains-vtf-hotel",
        "riec": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/finistere/riec-sur-belon/riec-sur-belon-ker-belen-le-pigneroux-vtf-holiday-village",
        "blainville": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/channel/blainville-sur-mer/blainville-le-senequet-vtf-holiday-village",
        "lacanau": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/gironde/lacanau/lacanau-ocean-la-forestiere-vtf-holiday-village",
        "agde": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/herault/agde/domaine-d-agde-vtf-holiday-village",
        "praloup": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/alpes-de-haute-provence/uvernet-fours/praloup-l-ouka-vtf-hotel",
        "cereste": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/alpes-de-haute-provence/cereste/cereste-domaine-du-grand-luberon-vtf-holiday-village",
        "le-sauze": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/alpes-de-haute-provence/le-sauze-barcelonnette/le-sauze-les-balcons-du-sauze-vtf-holiday-village",
        "bandol": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/var/bandol/bandol-clairefont-vtf-hotel",
        "sainte-maxime": "https://www.vtf-vacances.com/en_GB/summer/holiday-resort/var/sainte-maxime/sainte-maxime-golfe-de-saint-tropez-vtf-vvf-holiday-village",
    }

    def _transform_villages_to_gb(self, villages_data: list) -> list:
        """Build an English site URL for each village.

        Strategy (best-effort): parse the FR href path and reconstruct an
        English-style URL of the form:

        https://www.vtf-vacances.com/en_GB/{season}/holiday-resort/{department}/{city}/{city_prefix}-{slug}-vtf-holiday-village

        ``city_prefix`` defaults to ``city`` but can be overridden per-village
        via ``GB_CITY_SLUG_PREFIX_OVERRIDES`` for the rare cases where the
        English site uses a shorter form in the slug (e.g. saint-sauves).
        """
        transformed_villages = []
        for village in villages_data:
            village_copy = dict(village)
            href = village_copy.get("href")
            if not isinstance(href, str):
                transformed_villages.append(village_copy)
                continue

            # Known-broken villages: use the verified real en_GB URL
            # directly and skip the guess-based reconstruction below
            # entirely (see GB_FULL_HREF_OVERRIDES for why the guess
            # can't be trusted for these).
            village_id = village_copy.get("villageId")
            if village_id and village_id in self.GB_FULL_HREF_OVERRIDES:
                village_copy["href"] = self.GB_FULL_HREF_OVERRIDES[village_id]
                transformed_villages.append(village_copy)
                continue

            # parse URL (handles both absolute and relative hrefs)
            parsed = urlparse(href)
            path = parsed.path or href
            # Ensure we operate on the FR path segment
            if self.FR_PATH_SEGMENT not in path:
                # fallback: naive replace of first /fr_FR/ occurrence
                new_path = path.replace(self.FR_PATH_SEGMENT, self.GB_PATH_SEGMENT)
                village_copy["href"] = f"https://www.vtf-vacances.com{new_path}"
                transformed_villages.append(village_copy)
                continue

            # split the path into components: ['', 'fr_FR', 'season', 'village-vacances', 'dept', 'city', 'slug']
            parts = path.split("/")
            try:
                # expect parts[1] == 'fr_FR', parts[2] == season
                season = parts[2]
                # department and city usually at positions 4 and 5
                dept = parts[4] if len(parts) > 4 else ""
                city = parts[5] if len(parts) > 5 else ""
                last = parts[6] if len(parts) > 6 else parts[-1] if len(parts) > 1 else ""
                # Some cities use a shorter prefix in the en_GB final slug
                city_prefix = self.GB_CITY_SLUG_PREFIX_OVERRIDES.get(city, city)
                # construct english-style final slug (best-effort guess —
                # only reached for villages NOT in GB_FULL_HREF_OVERRIDES
                # above, i.e. ones already confirmed working)
                final_slug = "-".join(filter(None, [city_prefix, last])) + "-vtf-holiday-village"
                gb_path = f"{self.GB_PATH_SEGMENT}{season}/holiday-resort/{dept}/{city}/{final_slug}"
                village_copy["href"] = f"https://www.vtf-vacances.com{gb_path}"
            except Exception:
                # fallback to simple replace
                village_copy["href"] = href.replace(self.FR_PATH_SEGMENT, self.GB_PATH_SEGMENT)

            transformed_villages.append(village_copy)
        return transformed_villages