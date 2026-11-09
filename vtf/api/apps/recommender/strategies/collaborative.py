"""Collaborative filtering strategy — spec §4.4 Strategy 3 + addendum §3."""
from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count

from apps.pricing.models import SimulationLog
from apps.recommender.models import VillageInteraction
from apps.recommender.services.cf_state import (
    CF_MODEL_CACHE_KEY,
    get_cf_model_ready,
    save_cf_training_state,
)


def _thresholds() -> dict:
    min_sims = int(getattr(settings, "RECO_MIN_CF_INTERACTIONS", 500))
    return {
        "min_simulations": min_sims,
        "min_sessions": 100,
        "min_multi_village_sessions": 50,
        "min_villages_with_sims": 20,
        "min_sims_per_village": 10,
    }


def session_has_history(session_id: str, min_interactions: int = 2) -> bool:
    """Warm session: enough signals to apply CF re-ranking (addendum §3.3)."""
    if not session_id:
        return False

    try:
        n_interactions = VillageInteraction.objects.filter(session_id=session_id).count()
        n_sims = SimulationLog.objects.filter(session_id=session_id).count()
        return (n_interactions + n_sims) >= min_interactions
    except Exception:
        return False


def has_enough_data() -> bool:
    """Check if SVD thresholds are met. Spec §3.1 addendum + AC-2.11."""
    ready = get_cf_model_ready(default=None)
    if ready is not None:
        return bool(ready)
    return _check_thresholds()


def _check_thresholds() -> bool:
    th = _thresholds()
    try:
        total = SimulationLog.objects.count()
        if total < th["min_simulations"]:
            return False

        unique_sessions = SimulationLog.objects.values("session_id").distinct().count()
        if unique_sessions < th["min_sessions"]:
            return False

        multi_village = (
            SimulationLog.objects.values("session_id")
            .annotate(n=Count("village_id", distinct=True))
            .filter(n__gte=2)
            .count()
        )
        if multi_village < th["min_multi_village_sessions"]:
            return False

        villages_with_enough = (
            SimulationLog.objects.values("village_id")
            .annotate(n=Count("id"))
            .filter(n__gte=th["min_sims_per_village"])
            .count()
        )
        return villages_with_enough >= th["min_villages_with_sims"]
    except Exception:
        return False


def cf_rerank(
    content_scored: list,
    session_id: str,
    *,
    explain: bool = False,
) -> tuple[list, bool, str | None]:
    """Re-rank content-based results using collaborative signals.

    Returns (scored_list, cf_applied, ab_group).
  50/50 A/B: CF blend only on even hash buckets (addendum §3.5).
    """
    if not session_id or not has_enough_data() or not session_has_history(session_id):
        return content_scored, False, None

    ab_group = "cf" if hash(session_id) % 2 == 0 else "control"
    if ab_group == "control":
        return content_scored, False, ab_group

    try:
        model = _get_or_train_model()
        if model is None:
            return content_scored, False, ab_group

        all_village_ids = [item["village_id"] for item in content_scored]
        cf_predictions = _predict_for_session(model, session_id, all_village_ids)

        for item in content_scored:
            cf_score = cf_predictions.get(item["village_id"], 2.5) / 5.0
            item["score"] = round(item["score"] * 0.70 + cf_score * 0.30, 4)
            if explain:
                reasons = item.get("reasons")
                if reasons is None:
                    item["reasons"] = []
                item["reasons"].append(f"Affinité collaborative: {cf_score:.0%}")

        content_scored.sort(key=lambda x: x["score"], reverse=True)
        return content_scored, True, ab_group
    except Exception:
        return content_scored, False, ab_group


def _get_or_train_model():
    model = cache.get(CF_MODEL_CACHE_KEY)
    if model is None:
        save_cf_training_state(
            status="model_missing_or_expired",
            value_bool=False,
            metadata={
                "reason": "Cached SVD model is missing or expired",
                "model_key": CF_MODEL_CACHE_KEY,
            },
        )
    return model


def _predict_for_session(model, session_id: str, all_village_ids: list[str]) -> dict:
    try:
        predictions = {}
        for vid in all_village_ids:
            pred = model.predict(session_id, vid)
            predictions[vid] = pred.est
        return predictions
    except Exception:
        return {}
