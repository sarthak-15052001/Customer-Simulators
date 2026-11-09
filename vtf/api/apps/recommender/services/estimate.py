"""Lightweight stay estimate for recommendation scoring.

Runs a simplified estimate (skip transport/resto) to produce an estimated
total per village quickly. Used by the recommendation engine to score
all 32 villages in < 500ms. Spec §US-4.1 AC: estimatedTotal within ±5%.

DEPLOYMENT: copy to  apps/recommender/services/estimate.py
"""
from __future__ import annotations

from datetime import date

from apps.catalog.models import PricingRules, Village
from apps.pricing.services.stay_estimate import estimate_sejour_total


def lightweight_estimate(
    village: Village,
    family: dict,
    preferences: dict,
) -> int | None:
    """Run a stripped-down estimate — no transport, no resto, no activities.

    Returns integer euros or None on failure.
    """
    rules = PricingRules.active()
    if not rules:
        return None

    dates = preferences.get("dates") or {}
    debut = dates.get("debut")
    fin = dates.get("fin")
    if not debut or not fin:
        return None

    # Ensure dates are strings (ISO format)
    debut_str = debut.isoformat() if isinstance(debut, date) else str(debut)
    fin_str = fin.isoformat() if isinstance(fin, date) else str(fin)

    formule = preferences.get("formule") or (village.formules[0] if village.formules else "PC")
    if formule not in (village.formules or []):
        formule = village.formules[0] if village.formules else "PC"

    sejour = {
        "dateDebut": debut_str,
        "dateFin": fin_str,
        "formule": formule,
        "fNuits": None,
        "activities": {"outings": 0, "priceAdult": 0, "priceChild": 0},
        "resto": {"qtyByMealId": {}},
        "transport": {"mode": "none"},
        "promos": {
            "promoSejourRate": 0.0,
            "quinzaineFutee": False,
        },
    }

    village_dict = {
        "id": village.id,
        "nom": village.nom,
        "region": village.region,
        "env": village.env_emoji,
        "envCode": village.env_code,
        "formules": village.formules,
        "hasLoc": village.has_loc,
        "ski": village.ski,
        "ouverture": village.ouverture,
        "tarifs": village.tarifs,
        "bebeClub": village.bebe_club,
        "forfaitRM": village.forfait_rm,
        "qfExc": village.qf_exc,
        "enfSoloHalf": village.enf_solo_half,
    }

    try:
        est = estimate_sejour_total(
            family=family,
            sejour=sejour,
            village=village_dict,
            pricing_rules=rules,
            activities_by_region={},
            meals_catalog=[],
        )
        return est.total if est else None
    except Exception:
        return None


def bulk_estimate(
    villages: list[Village],
    family: dict,
    preferences: dict,
) -> dict[str, int | None]:
    """Run lightweight estimates for a list of villages.

    Returns dict: village_id -> estimated_total (or None on failure).
    """
    return {
        v.id: lightweight_estimate(v, family, preferences)
        for v in villages
    }
