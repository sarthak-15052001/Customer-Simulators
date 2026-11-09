"""Popularity-based fallback strategy — spec §4.4 Strategy 2.

Uses VillagePopularityCache for Tier 4 fallback.
Falls back to SEED_RANKING on day-1 when cache is empty.
"""
from __future__ import annotations

from apps.catalog.models import Village
from apps.recommender.models import VillagePopularityCache

# Hardcoded seed ranking — Tier 5 nuclear fallback (spec §4.3)
SEED_RANKING: list[str] = [
    "biarritz",
    "chamonix",
    "bandol",
    "lacanau",
    "saint-cast",
    "bedoin",
]


def popular_villages(limit: int = 6) -> list[dict]:
    """Return top villages by popularity score.

    Falls back to SEED_RANKING when VillagePopularityCache is empty.
    Returns list of dicts: {village_id, village, score, reasons, warnings, estimated_total}
    """
    qs = (
        VillagePopularityCache.objects
        .select_related("village")
        .order_by("-score")[:limit]
    )
    rows = list(qs)

    if rows:
        return [
            {
                "village_id": row.village.id,
                "village": row.village,
                "score": round(min(1.0, row.score / 100.0), 4),
                "reasons": ["Village populaire auprès des familles VTF"],
                "warnings": [],
                "estimated_total": None,
            }
            for row in rows
        ]

    # Cache empty — use hardcoded seed ranking
    village_map: dict[str, Village] = {
        v.id: v for v in Village.objects.filter(id__in=SEED_RANKING)
    }
    result = []
    for vid in SEED_RANKING[:limit]:
        v = village_map.get(vid)
        if v:
            result.append({
                "village_id": vid,
                "village": v,
                "score": 0.5,
                "reasons": ["Village recommandé par VTF"],
                "warnings": [],
                "estimated_total": None,
            })
    return result


def seed_villages(limit: int = 6) -> list[dict]:
    """Nuclear fallback — works even with empty DB (Tier 5). Spec §4.3."""
    village_map: dict[str, Village] = {
        v.id: v for v in Village.objects.filter(id__in=SEED_RANKING)
    }
    result = []
    for vid in SEED_RANKING[:limit]:
        v = village_map.get(vid)
        if v:
            result.append({
                "village_id": vid,
                "village": v,
                "score": 0.05,
                "reasons": ["Village de référence VTF"],
                "warnings": [],
                "estimated_total": None,
            })

    # If DB completely empty, return dicts without Village ORM objects
    if not result:
        for i, vid in enumerate(SEED_RANKING[:limit]):
            result.append({
                "village_id": vid,
                "village": None,
                "score": 0.05,
                "reasons": ["Village de référence VTF"],
                "warnings": [],
                "estimated_total": None,
            })
    return result
