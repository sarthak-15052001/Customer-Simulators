"""Content-based scoring strategy — spec §4.4 Strategy 1.

Scores every village (0.0–1.0) against the user's family profile +
preferences. No village is excluded — mustHave features reduce the score
to 0.05 instead of removing the village entirely so the waterfall can
still return a result.
"""
from __future__ import annotations

from datetime import date

from apps.catalog.models import EnvCode, Village
from apps.pricing.services.calendar import is_village_ouvert

# ─── Budget sigmoid ───────────────────────────────────────────────────────

def _budget_score(estimated_total: int | None, budget: int | None) -> float:
    """Sigmoid decay: 1.0 at/under budget, smooth decay above. Spec §4.4."""
    if not budget or budget <= 0:
        return 0.5
    if estimated_total is None:
        return 0.5
    ratio = estimated_total / budget
    if ratio <= 1.0:
        return 1.0
    # 10% over → 0.8, 25% over → 0.5, 50% over → 0.0
    return max(0.0, 1.0 - (ratio - 1.0) * 2)


# ─── Family fitness ───────────────────────────────────────────────────────

def _family_score(village: Village, family: dict, preferences: dict) -> float:
    """Composite family fit score (0.0–1.0)."""
    enfants = family.get("enfants") or []
    adultes = family.get("adultes", 2)
    ages = [c.get("age", 5) for c in enfants]
    # Spec: isSoloParent belongs to `family`. We also infer it as a fallback.
    is_solo_parent = bool(family.get("isSoloParent")) or (adultes == 1 and len(enfants) >= 1)

    score = 0.0
    bonus_pool = 0.0

    # Baby club: big deal if a child <3
    if village.bebe_club:
        if any(a < 3 for a in ages):
            score += 0.3
        bonus_pool += 0.3
    else:
        if any(a < 3 for a in ages):
            score -= 0.1  # small penalty: they probably need bebeClub

    # Ski: attractive for families with teens (10+)
    if village.ski and any(a >= 10 for a in ages):
        score += 0.2
    bonus_pool += 0.2

    # Solo parent half discount
    if is_solo_parent and village.enf_solo_half:
        score += 0.2
    bonus_pool += 0.2

    # QF eligibility
    qf_val = family.get("qfVal")
    if qf_val is not None and qf_val < 1350 and village.qf_exc:
        score += 0.15
    bonus_pool += 0.15

    # Normalize to 0–1
    if bonus_pool <= 0:
        return 0.5
    normalized = 0.5 + (score / bonus_pool) * 0.5
    return max(0.0, min(1.0, normalized))


# ─── Season availability ──────────────────────────────────────────────────

def _season_score(village: Village, debut: date | None) -> float:
    if debut is None:
        return 0.5
    return 1.0 if is_village_ouvert(village.ouverture, debut) else 0.05


# ─── Environment match ────────────────────────────────────────────────────

def _env_score(village: Village, preferred_envs: list[str]) -> float:
    if not preferred_envs:
        return 0.5
    return 1.0 if village.env_code in preferred_envs else 0.2


# ─── Extras match ─────────────────────────────────────────────────────────

def _extras_score(village: Village, preferences: dict) -> float:
    formule = preferences.get("formule")
    formules = village.formules or []
    if formule and formule not in formules:
        return 0.1  # formule unavailable → very low
    score = 0.6  # base: formule available (or no preference)
    if formule:
        score = 1.0
    return min(1.0, score)


# ─── Reason generation (French) ───────────────────────────────────────────

def _build_reasons(
    village: Village,
    family: dict,
    preferences: dict,
    estimated_total: int | None,
) -> tuple[list[str], list[str]]:
    reasons: list[str] = []
    warnings: list[str] = []

    enfants = family.get("enfants") or []
    ages = [c.get("age", 5) for c in enfants]
    adultes = family.get("adultes", 2)
    # Spec: isSoloParent belongs to `family`. We also infer it as a fallback.
    is_solo = bool(family.get("isSoloParent")) or (adultes == 1 and len(enfants) >= 1)

    # Environment
    preferred_envs = preferences.get("envs") or []
    if preferred_envs and village.env_code in preferred_envs:
        try:
            label = EnvCode(village.env_code).label
        except Exception:
            label = village.env_code
        reasons.append(f"{label} — environnement souhaité")

    # Baby club
    if village.bebe_club and any(a < 3 for a in ages):
        youngest = min((a for a in ages), default=0)
        reasons.append(f"Club bébé dès 4 mois — idéal pour votre enfant de {youngest} an(s)")
    elif any(a < 3 for a in ages) and not village.bebe_club:
        warnings.append("Pas de club bébé dans ce village")

    # QF
    qf_val = family.get("qfVal")
    if qf_val is not None and qf_val < 880:
        reasons.append("Éligible quotient familial (-17%)")
    elif qf_val is not None and qf_val < 1350:
        reasons.append("Éligible quotient familial (-10%)")

    # Budget
    budget = preferences.get("budget")
    if estimated_total is not None and budget:
        if estimated_total <= budget:
            reasons.append(f"Dans votre budget (estimé ~{estimated_total:,}€)")
        else:
            over_pct = round((estimated_total / budget - 1) * 100)
            warnings.append(f"Légèrement au-dessus du budget (+{over_pct}%, estimé ~{estimated_total:,}€)")

    # Solo parent
    if is_solo and village.enf_solo_half:
        reasons.append("Tarif parent solo — 50% pour les enfants")

    # Ski
    if village.ski and any(a >= 10 for a in ages):
        reasons.append("Station ski — idéal pour les ados")

    # Formule
    formule = preferences.get("formule")
    if formule and formule not in (village.formules or []):
        warnings.append(f"Formule {formule} non disponible dans ce village")

    return reasons, warnings


# ─── Main scoring function ────────────────────────────────────────────────

def score_all_villages(
    family: dict,
    preferences: dict,
    estimated_totals: dict[str, int] | None = None,
    interaction_boosts: dict[str, float] | None = None,
    weights: dict | None = None,
    villages: list[Village] | None = None,
) -> list[dict]:
    """Score all 32 villages and return sorted list (highest first).

    Args:
        family: {adultes, enfants, qfVal, isSoloParent}
        preferences: {envs, formule, budget, dates, mustHave, avoidSki}
        estimated_totals: village_id → estimated total (from lightweight estimate)
        interaction_boosts: village_id → boost factor (0.05 default weight)
        weights: override RecoWeights payload

    Returns:
        List of dicts with keys: village_id, village, score, reasons, warnings,
        estimated_total — sorted descending by score.
    """
    if weights is None:
        weights = {
            "budget_fit": 0.30,
            "env_match": 0.25,
            "family_fit": 0.20,
            "season_availability": 0.15,
            "extras_match": 0.10,
            "popularity_boost": 0.05,
            "interaction_boost": 0.05,
        }

    estimated_totals = estimated_totals or {}
    interaction_boosts = interaction_boosts or {}
    preferred_envs = preferences.get("envs") or []
    must_have: list[str] = preferences.get("mustHave") or []
    avoid_ski: bool = bool(preferences.get("avoidSki"))
    budget = preferences.get("budget")
    dates = preferences.get("dates") or {}
    debut_str = dates.get("debut")
    debut: date | None = None
    if debut_str:
        try:
            debut = date.fromisoformat(str(debut_str))
        except Exception:
            debut = None

    # Allow caller to pass pre-fetched villages to avoid repeated DB queries
    # in the waterfall tiers.
    if villages is None:
        villages = list(Village.objects.select_related("popularity_cache").all())
    results: list[dict] = []

    for v in villages:
        estimated_total = estimated_totals.get(v.id)
        must_have_penalty = False

        # Hard mustHave check → score floor 0.05
        for feature in must_have:
            feature_map = {
                "bebeClub": v.bebe_club,
                "ski": v.ski,
                "forfaitRM": v.forfait_rm,
                "enfSoloHalf": v.enf_solo_half,
                "qfExc": v.qf_exc,
                "hasLoc": v.has_loc,
            }
            if feature in feature_map and not feature_map[feature]:
                must_have_penalty = True
                break

        # avoidSki hard filter
        if avoid_ski and v.ski:
            must_have_penalty = True

        budget_s = _budget_score(estimated_total, budget)
        env_s = _env_score(v, preferred_envs)
        family_s = _family_score(v, family, preferences)
        season_s = _season_score(v, debut)
        extras_s = _extras_score(v, preferences)

        # Popularity boost from cache
        pop_score = 0.5
        try:
            pop_score = min(1.0, v.popularity_cache.score / 100.0)
        except Exception:
            pass

        # Interaction boost (session history)
        inter_boost = interaction_boosts.get(v.id, 0.0)

        raw_score = (
            weights["budget_fit"] * budget_s
            + weights["env_match"] * env_s
            + weights["family_fit"] * family_s
            + weights["season_availability"] * season_s
            + weights["extras_match"] * extras_s
            + weights["popularity_boost"] * pop_score
            + weights["interaction_boost"] * min(1.0, inter_boost)
        )

        if must_have_penalty:
            final_score = min(0.05, raw_score)
        else:
            final_score = round(raw_score, 4)

        reasons, warnings = _build_reasons(v, family, preferences, estimated_total)

        results.append({
            "village_id": v.id,
            "village": v,
            "score": final_score,
            "reasons": reasons,
            "warnings": warnings,
            "estimated_total": estimated_total,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
