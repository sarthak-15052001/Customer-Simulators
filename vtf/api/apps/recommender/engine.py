"""Recommendation engine — 5-tier waterfall orchestrator.

Spec §US-4.3 — ALWAYS returns ≥1 village. HTTP 200 always. Never empty.

Waterfall tiers:
  Tier 1: Personalized content-based scoring (score > 0.3, ≥3 results)
  Tier 2: Relaxed constraints (drop budget filter)
  Tier 3: Region + season only (broadest content filter)
  Tier 4: Popularity fallback (most interacted villages)
  Tier 5: Hardcoded safety net — works even with empty DB
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.conf import settings

from apps.catalog.models import Village
from apps.pricing.services.booking_redirect import BookingRedirectService
from apps.recommender.models import RecoWeights, VillageInteraction
from apps.recommender.services.estimate import bulk_estimate
from apps.recommender.strategies import content_based, popularity
from apps.recommender.strategies.collaborative import cf_rerank

logger = logging.getLogger(__name__)


@dataclass
class RecoResult:
    villages: list[dict] = field(default_factory=list)
    strategy: str = "personalized"
    confidence: float = 0.5
    total_scored: int = 0
    relaxed_filters: list[str] = field(default_factory=list)
    fallback_used: bool = False
    ab_group: str | None = None


def preferences_empty(preferences: dict | None) -> bool:
    """True when the user has not entered meaningful preferences (spec §US-4.2)."""
    if not preferences:
        return True
    return not any(
        [
            preferences.get("envs"),
            preferences.get("formule"),
            preferences.get("budget"),
            preferences.get("dates"),
            preferences.get("mustHave"),
            preferences.get("avoidSki"),
        ]
    )


def recommend(
    *,
    family: dict,
    preferences: dict,
    session_id: str | None = None,
    limit: int = 6,
    explain: bool = False,
    weights: dict | None = None,
) -> RecoResult:
    """Run the recommendation waterfall and return a guaranteed non-empty result.

    Args:
        family: {adultes, enfants, qfVal, isSoloParent, maxiFamily}
        preferences: {envs, formule, budget, dates, mustHave, avoidSki}
        session_id: frontend UUID for interaction boost + CF
        limit: number of results (default 6)
        explain: include French reasons/warnings per village
        weights: override RecoWeights payload (for admin tuning)

    Returns:
        RecoResult — always with len(villages) >= 1
    """
    if weights is None:
        weights = RecoWeights.active()

    all_villages = list(Village.objects.select_related("popularity_cache").all())
    total_scored = len(all_villages)

    # ── Zero preferences → popularity fallback (spec §US-4.2) ─────────────
    if preferences_empty(preferences):
        pop_results = popularity.popular_villages(limit=limit)
        used_seed = False
        if not pop_results:
            pop_results = popularity.seed_villages(limit=limit)
            used_seed = True
        return _build_result(
            pop_results,
            "popular_fallback",
            0.05 if used_seed else 0.1,
            total_scored,
            relaxed_filters=["all_filters"] if used_seed else [],
            fallback_used=True,
            explain=explain,
            estimated_totals={},
            session_id=session_id,
            family=family,
            preferences={},
            ab_group=None,
        )

    # ── Build interaction boost map for session ────────────────────────────
    interaction_boosts: dict[str, float] = {}
    if session_id:
        try:
            interactions = (
                VillageInteraction.objects
                .filter(session_id=session_id)
                .values("village_id", "kind", "value")
            )
            kind_weight = {"view": 0.5, "simulate": 1.0, "bookmark": 2.0, "rate": 1.5, "click_cta": 2.5}
            for inter in interactions:
                vid = inter["village_id"]
                w = kind_weight.get(inter["kind"], 0.5)
                interaction_boosts[vid] = interaction_boosts.get(vid, 0.0) + w
        except Exception:
            logger.warning(
                "interaction_boost_failed",
                extra={"session_id": session_id},
                exc_info=True,
            )

    # ── Lightweight estimates for all villages ─────────────────────────────
    estimated_totals: dict[str, int | None] = {}
    try:
        estimated_totals = bulk_estimate(all_villages, family, preferences)
    except Exception:
        logger.warning("bulk_estimate_failed", exc_info=True)

    # ── Tier 1: Full personalized content-based ───────────────────────────
    scored = content_based.score_all_villages(
        family=family,
        preferences=preferences,
        estimated_totals=estimated_totals,
        interaction_boosts=interaction_boosts,
        weights=weights,
        villages=all_villages,
    )

    # CF re-ranking (when thresholds + session history + A/B arm allow)
    cf_used = False
    ab_group: str | None = None
    if session_id:
        scored, cf_used, ab_group = cf_rerank(
            scored, session_id, explain=explain
        )

    tier1_results = [s for s in scored if s["score"] > 0.3]
    if len(tier1_results) >= 3:
        villages_out = tier1_results[:limit]
        strategy = "personalized_cf" if cf_used else "personalized"
        confidence = _avg_confidence(villages_out, 0.85, 0.95)
        return _build_result(
            villages_out, strategy, confidence, total_scored,
            relaxed_filters=[], fallback_used=False, explain=explain,
            estimated_totals=estimated_totals, session_id=session_id,
            family=family, preferences=preferences,
            ab_group=ab_group,
        )

    # ── Tier 2: Relax budget filter ───────────────────────────────────────
    prefs_no_budget = {**preferences, "budget": None}
    scored_t2 = content_based.score_all_villages(
        family=family,
        preferences=prefs_no_budget,
        estimated_totals=estimated_totals,
        interaction_boosts=interaction_boosts,
        weights=weights,
        villages=all_villages,
    )
    tier2_results = [s for s in scored_t2 if s["score"] > 0.2]
    if len(tier2_results) >= 3:
        villages_out = tier2_results[:limit]
        confidence = _avg_confidence(villages_out, 0.5, 0.7)
        return _build_result(
            villages_out, "personalized", confidence, total_scored,
            relaxed_filters=["budget"], fallback_used=False, explain=explain,
            estimated_totals=estimated_totals, session_id=session_id,
            family=family, preferences=prefs_no_budget,
            ab_group=ab_group,
        )

    # ── Tier 3: Region + season only ─────────────────────────────────────
    prefs_minimal = {
        "envs": preferences.get("envs") or [],
        "formule": None,
        "budget": None,
        "dates": preferences.get("dates"),
        "mustHave": [],
        "avoidSki": False,
    }
    scored_t3 = content_based.score_all_villages(
        family=family,
        preferences=prefs_minimal,
        estimated_totals=estimated_totals,
        interaction_boosts=interaction_boosts,
        weights=weights,
        villages=all_villages,
    )
    tier3_results = [s for s in scored_t3 if s["score"] > 0.1]
    if tier3_results:
        villages_out = tier3_results[:limit]
        confidence = _avg_confidence(villages_out, 0.3, 0.5)
        relaxed = ["budget", "formule", "mustHave", "avoidSki"]
        return _build_result(
            villages_out, "popular_fallback", confidence, total_scored,
            relaxed_filters=relaxed, fallback_used=False, explain=explain,
            estimated_totals=estimated_totals, session_id=session_id,
            family=family, preferences=prefs_minimal,
            ab_group=ab_group,
        )

    # ── Tier 4: Popularity fallback ───────────────────────────────────────
    pop_results = popularity.popular_villages(limit=limit)
    if pop_results:
        confidence = _avg_confidence(pop_results, 0.1, 0.2)
        return _build_result(
            pop_results, "popular_fallback", confidence, total_scored,
            relaxed_filters=["all_filters"], fallback_used=True, explain=explain,
            estimated_totals=estimated_totals, session_id=session_id,
            family=family, preferences={},
            ab_group=ab_group,
        )

    # ── Tier 5: Nuclear hardcoded safety net ─────────────────────────────
    seed_results = popularity.seed_villages(limit=limit)
    # Filter out None villages (totally empty DB)
    seed_results = [r for r in seed_results if r.get("village") is not None] or seed_results
    return _build_result(
        seed_results, "popular_fallback", 0.05, total_scored,
        relaxed_filters=["all_filters"], fallback_used=True, explain=explain,
        estimated_totals=estimated_totals, session_id=session_id,
        family=family, preferences={},
        ab_group=ab_group,
    )


def _avg_confidence(villages: list[dict], lo: float, hi: float) -> float:
    if not villages:
        return lo
    avg = sum(v["score"] for v in villages) / len(villages)
    return round(lo + (hi - lo) * min(1.0, avg), 3)


def _build_result(
    villages_raw: list[dict],
    strategy: str,
    confidence: float,
    total_scored: int,
    *,
    relaxed_filters: list[str],
    fallback_used: bool,
    explain: bool,
    estimated_totals: dict,
    session_id: str | None,
    family: dict,
    preferences: dict,
    ab_group: str | None = None,
) -> RecoResult:
    """Attach rank, bookingUrl, and prune explain fields if not requested."""
    villages_out = []
    dates = preferences.get("dates") or {}
    debut = dates.get("debut")
    fin = dates.get("fin")

    for rank, item in enumerate(villages_raw, start=1):
        v = item.get("village")
        if v is None:
            vid = item.get("village_id")
            if not vid:
                continue
            v = {
                "id": vid,
                "nom": vid.replace("-", " ").title(),
                "nom2": "",
                "region": "",
                "env": "",
                "env_code": "",
                "env_emoji": "",
                "formules": [],
                "ski": False,
                "bebe_club": False,
                "qf_exc": False,
                "enf_solo_half": False,
                "has_loc": False,
            }

        # Estimated total from map or item
        vid = v.id if isinstance(v, Village) else (v.get("id") if isinstance(v, dict) else None)
        est_total = estimated_totals.get(vid) if vid else None
        if est_total is None:
            est_total = item.get("estimated_total")

        # Build booking URL
        booking_url = ""
        try:
            if isinstance(v, Village) and debut and fin:
                debut_str = debut.isoformat() if hasattr(debut, "isoformat") else str(debut)
                fin_str = fin.isoformat() if hasattr(fin, "isoformat") else str(fin)
                token, _row, _params = BookingRedirectService.create_token(
                    village=v,
                    session_id=session_id or "anon",
                    family=family,
                    dates={"debut": debut_str, "fin": fin_str},
                    context={
                        "source": "recommendation",
                        "estimatedTotal": est_total,
                        "recoStrategy": strategy,
                        "recoScore": item["score"],
                        "recoRank": rank,
                    },
                )
                booking_url = f"{settings.API_BASE_URL}/api/v1/go/{token}"
        except Exception:
            logger.warning(
                "booking_url_build_failed",
                extra={"session_id": session_id, "strategy": strategy},
                exc_info=True,
            )

        entry = {
            "village": v,
            "score": item["score"],
            "estimated_total": est_total,
            "booking_url": booking_url,
            "rank": rank,
        }
        if explain:
            entry["reasons"] = item.get("reasons") or []
            entry["warnings"] = item.get("warnings") or []
        else:
            entry["reasons"] = []
            entry["warnings"] = []

        villages_out.append(entry)

    if not villages_out:
        logger.error(
            "recommendation_empty_villages",
            extra={"strategy": strategy, "session_id": session_id},
        )

    return RecoResult(
        villages=villages_out,
        strategy=strategy,
        confidence=round(confidence, 3),
        total_scored=total_scored,
        relaxed_filters=relaxed_filters,
        fallback_used=fallback_used,
        ab_group=ab_group,
    )
