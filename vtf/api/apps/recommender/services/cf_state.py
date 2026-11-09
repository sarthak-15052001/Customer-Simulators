"""DB/cache state helpers for collaborative filtering readiness and training."""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

from apps.pricing.models import SimulationLog
from apps.recommender.models import RecommendationSystemState, VillageInteraction

CF_MODEL_READY_KEY = "cf_model_ready"
CF_MODEL_TRAINING_KEY = "cf_model_training"
CF_MODEL_CACHE_KEY = "vtf:reco:cf_model"
CF_READY_CACHE_TIMEOUT = 86400
CF_MODEL_CACHE_TIMEOUT = 60 * 60 * 25


def cf_thresholds() -> dict[str, int]:
    min_sims = int(getattr(settings, "RECO_MIN_CF_INTERACTIONS", 500))
    return {
        "min_simulations": min_sims,
        "min_sessions": 100,
        "min_multi_village_sessions": 50,
        "min_villages_with_sims": 20,
        "min_sims_per_village": 10,
    }


def evaluate_cf_readiness(thresholds: dict[str, int] | None = None) -> dict[str, Any]:
    """Evaluate current CF thresholds and return ready/count metadata."""
    th = thresholds or cf_thresholds()

    total_sims = SimulationLog.objects.count()
    unique_sessions = SimulationLog.objects.values("session_id").distinct().count()
    multi_village = (
        SimulationLog.objects.values("session_id")
        .annotate(n=Count("village_id", distinct=True))
        .filter(n__gte=2)
        .count()
    )
    villages_with_enough = (
        SimulationLog.objects.values("village_id")
        .annotate(n=Count("id"))
        .filter(n__gte=th["min_sims_per_village"])
        .count()
    )

    village_interactions = VillageInteraction.objects.count()
    interaction_sessions = (
        VillageInteraction.objects.values("session_id").distinct().count()
    )
    interaction_villages = (
        VillageInteraction.objects.values("village_id").distinct().count()
    )
    simulation_pairs = (
        SimulationLog.objects.values("session_id", "village_id").distinct().count()
    )
    village_interaction_pairs = (
        VillageInteraction.objects.values("session_id", "village_id")
        .distinct()
        .count()
    )

    checks = {
        "min_simulations": total_sims >= th["min_simulations"],
        "min_sessions": unique_sessions >= th["min_sessions"],
        "min_multi_village_sessions": (
            multi_village >= th["min_multi_village_sessions"]
        ),
        "min_villages_with_sims": (
            villages_with_enough >= th["min_villages_with_sims"]
        ),
    }
    ready = all(checks.values())

    metadata = {
        "checked_at": timezone.now().isoformat(),
        "source": "check_cf_readiness",
        "ready": ready,
        "counts": {
            "simulation_logs": total_sims,
            "village_interactions": village_interactions,
            "unique_sessions": unique_sessions,
            "unique_villages": (
                SimulationLog.objects.values("village_id").distinct().count()
            ),
            "interaction_unique_sessions": interaction_sessions,
            "interaction_unique_villages": interaction_villages,
            "multi_village_sessions": multi_village,
            "villages_with_enough_sims": villages_with_enough,
            "simulation_pairs": simulation_pairs,
            "village_interaction_pairs": village_interaction_pairs,
        },
        "thresholds": th,
        "failed_checks": [key for key, passed in checks.items() if not passed],
    }
    return {"ready": ready, "counts": metadata["counts"], "thresholds": th, "metadata": metadata}


def save_cf_readiness_state(
    *,
    ready: bool,
    metadata: dict[str, Any],
    cache_timeout: int = CF_READY_CACHE_TIMEOUT,
):
    """Persist cf_model_ready in DB and keep the existing cache key fresh."""
    cache.set(CF_MODEL_READY_KEY, ready, timeout=cache_timeout)
    row, _ = RecommendationSystemState.objects.update_or_create(
        key=CF_MODEL_READY_KEY,
        defaults={"value_bool": ready, "metadata": metadata},
    )
    return row


def get_cf_model_ready(default: bool | None = False) -> bool | None:
    """Read readiness from cache first, then DB as the durable fallback."""
    cached = cache.get(CF_MODEL_READY_KEY)
    if cached is not None:
        return bool(cached)

    ready = (
        RecommendationSystemState.objects.filter(key=CF_MODEL_READY_KEY)
        .values_list("value_bool", flat=True)
        .first()
    )
    if ready is None:
        return default
    cache.set(CF_MODEL_READY_KEY, bool(ready), timeout=CF_READY_CACHE_TIMEOUT)
    return bool(ready)


def save_cf_training_state(
    *,
    status: str,
    value_bool: bool | None,
    metadata: dict[str, Any] | None = None,
):
    """Persist the latest SVD training outcome."""
    payload = {
        "status": status,
        "updated_at": timezone.now().isoformat(),
        **(metadata or {}),
    }
    row, _ = RecommendationSystemState.objects.update_or_create(
        key=CF_MODEL_TRAINING_KEY,
        defaults={"value_bool": value_bool, "metadata": payload},
    )
    return row
