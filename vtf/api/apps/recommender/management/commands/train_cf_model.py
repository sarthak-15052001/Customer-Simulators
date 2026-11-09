"""Management command: train_cf_model.

Builds the (session × village) implicit-rating matrix from SimulationLog
and VillageInteraction, trains a Surprise SVD model, and stores the result
in Redis cache as `vtf:reco:cf_model`.

Run daily via cron at 3:00 AM (after check_cf_readiness at 2:50 AM):
  python manage.py train_cf_model

Only trains when the `cf_model_ready` flag is True (set by check_cf_readiness).
Pass --force to train regardless of the flag.

Requires: scikit-surprise, pandas  (see requirements.txt)
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db.models import Count, Max

from apps.pricing.models import SimulationLog
from apps.recommender.models import VillageInteraction
from apps.recommender.services.cf_state import (
    CF_MODEL_CACHE_KEY,
    CF_MODEL_CACHE_TIMEOUT,
    get_cf_model_ready,
    save_cf_training_state,
)

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from surprise import SVD, Dataset, Reader
except ImportError:
    Dataset = Reader = SVD = None

logger = logging.getLogger(__name__)


class _MiniSeries(list):
    """List wrapper mimicking pandas Series helpers used by this command."""

    def min(self):  # noqa: A003 (min)
        return min(self) if self else None

    def max(self):  # noqa: A003 (max)
        return max(self) if self else None

    def nunique(self):
        return len(set(self))


class MiniDataFrame:
    """Minimal DataFrame stand-in when pandas is not installed.

    Supports the subset of pandas API used by unit tests and by
    ``Command.handle`` logging (``empty``, column access, ``nunique``).
    """

    _COLUMNS = ("user_id", "item_id", "rating")

    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows
        self.empty = len(rows) == 0

    def __getitem__(self, key: str | list[str]):
        if isinstance(key, list):
            return MiniDataFrame([{col: row.get(col) for col in key} for row in self._rows])
        return _MiniSeries([row.get(key) for row in self._rows])

    def __len__(self) -> int:
        return len(self._rows)


def _collect_interaction_rows() -> list[dict[str, Any]]:
    """Build implicit-rating rows from SimulationLog + VillageInteraction.

    Rating scale:
      1.0 = viewed village (dropdown selection)
      2.0 = simulated (/estimate/stay called)
      2.5 = simulated ≥2 times (stronger signal)
      3.0 = recap viewed / shared
      3.5 = bookmarked
      5.0 = clicked booking link (strongest conversion signal)
    """
    rating_by_pair: dict[tuple[str, str], float] = {}

    sims = (
        SimulationLog.objects
        .values("session_id", "village_id")
        .annotate(
            sim_count=Count("id"),
            clicked=Max("clicked_booking"),
        )
    )
    for s in sims:
        if not s["session_id"] or not s["village_id"]:
            continue
        if s["clicked"]:
            rating = 5.0
        elif (s["sim_count"] or 0) >= 2:
            rating = 2.5
        else:
            rating = 2.0
        key = (s["session_id"], s["village_id"])
        rating_by_pair[key] = max(rating_by_pair.get(key, 0.0), rating)

    signal_boost = {
        "view": 1.0,
        "simulate": 2.0,
        "bookmark": 3.5,
        "rate": 3.0,
        "click_cta": 5.0,
    }
    interactions = (
        VillageInteraction.objects
        .filter(kind__in=list(signal_boost.keys()))
        .values("session_id", "village_id", "kind")
    )
    for inter in interactions:
        if not inter["session_id"] or not inter["village_id"]:
            continue
        key = (inter["session_id"], inter["village_id"])
        boosted = signal_boost.get(inter["kind"], 2.0)
        rating_by_pair[key] = max(rating_by_pair.get(key, 0.0), boosted)

    return [
        {"user_id": uid, "item_id": iid, "rating": rating}
        for (uid, iid), rating in rating_by_pair.items()
    ]


def _as_interaction_frame(rows: list[dict[str, Any]]):
    """Return a pandas DataFrame when available, otherwise ``MiniDataFrame``."""
    if pd is None:
        return MiniDataFrame(rows)

    return pd.DataFrame(rows, columns=list(MiniDataFrame._COLUMNS))


class Command(BaseCommand):
    help = "Train Surprise SVD from SimulationLog + VillageInteraction and cache the model."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Train even if cf_model_ready flag is False.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        logger.info("recommender_train_cf_model_started force=%s", force)

        if not force:
            ready = get_cf_model_ready()
            if not ready:
                save_cf_training_state(
                    status="skipped_not_ready",
                    value_bool=False,
                    metadata={
                        "reason": "cf_model_ready is false",
                        "force": force,
                    },
                )
                self.stdout.write(
                    self.style.WARNING(
                        "cf_model_ready flag is False — skipping training. "
                        "Run check_cf_readiness first, or pass --force."
                    )
                )
                logger.info("recommender_train_cf_model_skipped reason=not_ready force=%s", force)
                return

        if pd is None or Dataset is None or Reader is None or SVD is None:
            save_cf_training_state(
                status="missing_dependencies",
                value_bool=False,
                metadata={
                    "reason": "scikit-surprise or pandas is not installed",
                    "force": force,
                },
            )
            self.stdout.write(
                self.style.ERROR(
                    "Missing dependencies: scikit-surprise and pandas must be installed.\n"
                    "Run: pip install scikit-surprise pandas"
                )
            )
            logger.error("recommender_train_cf_model_missing_dependencies force=%s", force)
            return

        self.stdout.write("Building interaction matrix…")
        logger.info("recommender_train_cf_model_building_matrix")
        df = self._build_interaction_matrix()

        if df.empty:
            save_cf_training_state(
                status="skipped_empty_matrix",
                value_bool=False,
                metadata={
                    "reason": "interaction matrix is empty",
                    "force": force,
                },
            )
            self.stdout.write(self.style.WARNING("Interaction matrix is empty — aborting."))
            logger.warning("recommender_train_cf_model_skipped reason=empty_matrix force=%s", force)
            return

        matrix_rows = len(df)
        unique_sessions = df["user_id"].nunique()
        unique_villages = df["item_id"].nunique()

        self.stdout.write(
            f"  Matrix: {unique_sessions} sessions × "
            f"{unique_villages} villages, "
            f"{matrix_rows} rows"
        )
        logger.info(
            "recommender_train_cf_model_matrix_ready rows=%d unique_sessions=%d unique_villages=%d",
            matrix_rows,
            unique_sessions,
            unique_villages,
        )

        self.stdout.write("Training SVD (n_factors=10, n_epochs=20)…")
        logger.info("recommender_train_cf_model_training_started n_factors=10 n_epochs=20")
        reader = Reader(rating_scale=(1, 5))
        training_df = df[["user_id", "item_id", "rating"]]
        data = Dataset.load_from_df(training_df, reader)
        trainset = data.build_full_trainset()

        model = SVD(n_factors=10, n_epochs=20, random_state=42)
        model.fit(trainset)

        cache.set(CF_MODEL_CACHE_KEY, model, timeout=CF_MODEL_CACHE_TIMEOUT)
        save_cf_training_state(
            status="trained",
            value_bool=True,
            metadata={
                "model_type": "SVD",
                "model_key": CF_MODEL_CACHE_KEY,
                "force": force,
                "matrix_rows": matrix_rows,
                "unique_sessions": unique_sessions,
                "unique_villages": unique_villages,
                "n_factors": 10,
                "n_epochs": 20,
                "rating_scale": [1, 5],
            },
        )

        self.stdout.write(self.style.SUCCESS("SVD model trained and cached as vtf:reco:cf_model."))
        logger.info(
            "recommender_train_cf_model_done cache_key=%s rows=%d unique_sessions=%d unique_villages=%d",
            CF_MODEL_CACHE_KEY,
            matrix_rows,
            unique_sessions,
            unique_villages,
        )

    def _build_interaction_matrix(self):
        """Return interaction matrix as pandas DataFrame or ``MiniDataFrame``."""
        return _as_interaction_frame(_collect_interaction_rows())
