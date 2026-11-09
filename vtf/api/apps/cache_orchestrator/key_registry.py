"""Central registry of Redis cache key patterns and TTLs.

Key naming convention (Redis pattern -> endpoint):
    vtf:catalog:villages:list           → GET /api/v1/villages/               # Village list caching is disabled
    vtf:catalog:villages:{id}:detail     -> GET /api/v1/villages/{id}/
    vtf:catalog:regions:list             -> GET /api/v1/regions
    vtf:catalog:regions:{key}:activities -> GET /api/v1/regions/{key}/activities
    vtf:catalog:pricing_rules            -> GET /api/v1/pricing-rules
    vtf:catalog:seasons                  -> GET /api/v1/seasons
    vtf:catalog:meals                    -> GET /api/v1/meals
    vtf:catalog:fuels                    -> GET /api/v1/fuels
    vtf:catalog:promos_catalog           -> GET /api/v1/promos/catalog
    vtf:catalog:animations               -> GET /api/v1/animations
    vtf:reco:popularity:{id}             -> popularity score cache
    vtf:booking:token:{token}            -> redirect token payload

TTLs (seconds):
    24h = 86400
    7d  = 604800
    1h  = 3600
"""
from __future__ import annotations

from dataclasses import dataclass

# TTLs (seconds)
TTL_1H = 60 * 60
TTL_24H = 60 * 60 * 24
TTL_7D = 60 * 60 * 24 * 7
TTL_6H = 60 * 60 * 6
TTL_72H = 60 * 60 * 72

# Activity list query combos warmed for each region (kind, season).
ACTIVITY_CACHE_COMBOS: tuple[tuple[str, str], ...] = (
    ("", ""),
    ("free", ""),
    ("paid", ""),
    ("", "ete"),
    ("paid", "ete"),
)

# Representative dates warmed on pricing-scope rebuild (one per saison + common picks).
SEASON_DATE_WARM_SAMPLES: tuple[str, ...] = (
    "2026-07-15",  # ete
    "2026-02-15",  # vs (ski window)
    "2026-12-25",  # fetes
    "2026-05-01",  # hs
    "2026-04-10",  # vs (Easter)
    "2026-08-01",  # ete
    "2026-01-15",  # vs
    "2026-10-20",  # vs (Toussaint)
)


@dataclass(frozen=True)
class CacheKey:
    pattern: str
    ttl_seconds: int
    description: str


REGISTRY: dict[str, CacheKey] = {
    # Village list caching is intentionally disabled (client request) — not warmed.
    "vtf:catalog:villages:{id}:detail": CacheKey(
        "vtf:catalog:villages:*:detail", TTL_24H, "Single village + relations"
    ),
    "vtf:catalog:attractions": CacheKey(
        "vtf:catalog:attractions", TTL_24H, "Attraction tiles"
    ),
    "vtf:catalog:regions:list": CacheKey(
        "vtf:catalog:regions:list", TTL_7D, "Regions list"
    ),
    "vtf:catalog:regions:{key}:activities": CacheKey(
        "vtf:catalog:regions:*:activities:*", TTL_24H, "Activities by region"
    ),
    "vtf:catalog:pricing_rules": CacheKey(
        "vtf:catalog:pricing_rules", TTL_24H, "Active pricing rules"
    ),
    "vtf:catalog:seasons": CacheKey(
        "vtf:catalog:seasons", TTL_7D, "Season calendar"
    ),
    "vtf:catalog:season:date:{date}": CacheKey(
        "vtf:catalog:season:date:*", TTL_1H, "Season lookup by date"
    ),
    "vtf:catalog:meals": CacheKey("vtf:catalog:meals", TTL_7D, "Meals reference"),
    "vtf:catalog:formules": CacheKey("vtf:catalog:formules", TTL_7D, "Formulas"),
    "vtf:catalog:fuels": CacheKey("vtf:catalog:fuels", TTL_7D, "Fuels reference"),
    "vtf:catalog:promos_catalog": CacheKey(
        "vtf:catalog:promos_catalog", TTL_7D, "Promo catalog"
    ),
    "vtf:catalog:animations": CacheKey(
        "vtf:catalog:animations", TTL_7D, "Animations"
    ),
    "vtf:catalog:landing_map": CacheKey(
        "vtf:catalog:landing_map", TTL_7D, "Landing map"
    ),
    "vtf:catalog:marketing_seasons": CacheKey(
        "vtf:catalog:marketing_seasons", TTL_7D, "Marketing seasons"
    ),
    "vtf:catalog:environments:{key}": CacheKey(
        "vtf:catalog:environments:*", TTL_7D, "Funnel environments"
    ),
    "vtf:reco:popularity:{id}": CacheKey(
        "vtf:reco:popularity:*", TTL_6H, "Per-village popularity"
    ),
    "vtf:reco:cf_model": CacheKey(
        "vtf:reco:cf_model", TTL_7D, "Trained SVD model"
    ),
    "vtf:booking:token:{token}": CacheKey(
        "vtf:booking:token:*", TTL_72H, "Redirect token payload"
    ),
}

SCOPE_PATTERNS: dict[str, list[str]] = {
    "all": ["vtf:*"],
    "catalog": ["vtf:catalog:*"],
    "pricing": [
        "vtf:catalog:pricing_rules",
        "vtf:catalog:seasons",
        "vtf:catalog:season:date:*",
        "vtf:catalog:promos_catalog",
    ],
    "recommendations": ["vtf:reco:*"],
    "booking_urls": ["vtf:booking:*"],
}


def region_cache_slug(region_key: str) -> str:
    """Match ``RegionActivitiesView`` cache key segment."""
    return region_key.replace(" ", "_").replace("/", "-")


def activities_cache_key(region_key: str, kind: str = "", season: str = "") -> str:
    return (
        f"vtf:catalog:regions:{region_cache_slug(region_key)}"
        f":activities:{kind}:{season}"
    )


def village_detail_cache_key(village_id: str) -> str:
    return f"vtf:catalog:villages:{village_id}:detail"


def popularity_cache_key(village_id: str) -> str:
    return f"vtf:reco:popularity:{village_id}"


def booking_token_cache_key(token: str) -> str:
    return f"vtf:booking:token:{token}"
