"""Celery tasks for the recommender app.

Three tasks wrap the existing management commands so Celery Beat can
schedule them (AC2.7, AC2.11, AC2.14).  The management commands are
kept as-is so they can still be run manually:

    python manage.py refresh_popularity
    python manage.py check_cf_readiness
    python manage.py train_cf_model
"""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

from apps.catalog.models import Village
from apps.recommender.management.commands.train_cf_model import (
    _as_interaction_frame,
    _collect_interaction_rows,
)
from apps.recommender.models import VillageInteraction, VillagePopularityCache
from apps.recommender.services.cf_state import (
    CF_MODEL_CACHE_KEY,
    CF_MODEL_CACHE_TIMEOUT,
    evaluate_cf_readiness,
    get_cf_model_ready,
    save_cf_readiness_state,
    save_cf_training_state,
)
from apps.cache_orchestrator.tasks import task_rebuild_cache

try:
    from surprise import SVD, Dataset, Reader
except ImportError:
    Dataset = Reader = SVD = None

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.recommender.tasks.task_refresh_popularity",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    ignore_result=True,
)
def task_refresh_popularity(self, days: int = 30) -> None:
    """Refresh VillagePopularityCache — runs every 6h via Celery Beat (AC2.7).

    Equivalent to: python manage.py refresh_popularity --days=<days>
    """
    try:
        cutoff = timezone.now() - timedelta(days=days)
        logger.info("task_refresh_popularity: aggregating last %d days", days)

        agg = (
            VillageInteraction.objects
            .filter(created_at__gte=cutoff)
            .values("village_id", "kind")
            .annotate(count=Count("id"))
        )

        village_stats: dict[str, dict] = {}
        for row in agg:
            vid = row["village_id"]
            if vid not in village_stats:
                village_stats[vid] = {"views": 0, "simulations": 0, "bookmarks": 0}
            kind = row["kind"]
            if kind == "view":
                village_stats[vid]["views"] += row["count"]
            elif kind == "simulate":
                village_stats[vid]["simulations"] += row["count"]
            elif kind == "bookmark":
                village_stats[vid]["bookmarks"] += row["count"]

        updated = 0
        for village_id, stats in village_stats.items():
            raw_score = (
                stats["views"] * 1.0
                + stats["simulations"] * 3.0
                + stats["bookmarks"] * 5.0
            )
            try:
                village = Village.objects.get(pk=village_id)
            except Village.DoesNotExist:
                continue
            VillagePopularityCache.objects.update_or_create(
                village=village,
                defaults={
                    "views_30d": stats["views"],
                    "simulations_30d": stats["simulations"],
                    "bookmarks_30d": stats["bookmarks"],
                    "score": round(raw_score, 2),
                },
            )
            updated += 1

        # Ensure every village has a cache row even with zero interactions
        for village in Village.objects.all():
            VillagePopularityCache.objects.get_or_create(
                village=village,
                defaults={
                    "views_30d": 0,
                    "simulations_30d": 0,
                    "bookmarks_30d": 0,
                    "score": 0.0,
                },
            )

        logger.info(
            "task_refresh_popularity: done, updated=%d total_villages=%d",
            updated,
            Village.objects.count(),
        )
        try:
            task_rebuild_cache.delay(
                scope="recommendations",
                reason="refresh_popularity completed",
                triggered_by="system:task_refresh_popularity",
            )
        except Exception as exc:
            logger.warning("task_refresh_popularity_cache_rebuild_enqueue_failed: %s", exc)
    except Exception as exc:
        logger.exception("task_refresh_popularity failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    name="apps.recommender.tasks.task_check_cf_readiness",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    ignore_result=True,
)
def task_check_cf_readiness(self) -> None:
    """Check SVD thresholds and update cf_model_ready cache flag (AC2.11 / AC2.14).

    Equivalent to: python manage.py check_cf_readiness

    Runs at 02:50 AM daily, just before task_train_cf_model at 03:00.
    Also called after each /estimate/stay via a Django signal so the flag
    stays fresh without waiting for the next cron window (AC2.11 fix).
    """
    try:
        result = evaluate_cf_readiness()
        counts = result["counts"]
        ready = result["ready"]
        save_cf_readiness_state(ready=ready, metadata=result["metadata"])

        logger.info(
            "task_check_cf_readiness: ready=%s sims=%d sessions=%d "
            "multi_village=%d villages_with_enough=%d",
            ready,
            counts["simulation_logs"],
            counts["unique_sessions"],
            counts["multi_village_sessions"],
            counts["villages_with_enough_sims"],
        )
    except Exception as exc:
        logger.exception("task_check_cf_readiness failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    name="apps.recommender.tasks.task_train_cf_model",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
    ignore_result=True,
    time_limit=600,   # 10-minute hard limit
    soft_time_limit=540,
)
def task_train_cf_model(self, force: bool = False) -> None:
    """Train Surprise SVD and cache the model — runs daily at 03:00 AM (AC2.14).

    Equivalent to: python manage.py train_cf_model [--force]

    Only trains when cf_model_ready is True unless force=True.
    """
    try:
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
                logger.info(
                    "task_train_cf_model: cf_model_ready is False — skipping. "
                    "Run check_cf_readiness first."
                )
                return

        if Dataset is None or Reader is None or SVD is None:
            save_cf_training_state(
                status="missing_dependencies",
                value_bool=False,
                metadata={
                    "reason": "scikit-surprise or pandas is not installed",
                    "force": force,
                },
            )
            logger.error(
                "task_train_cf_model: scikit-surprise not installed. "
                "Run: pip install scikit-surprise pandas"
            )
            return

        logger.info("task_train_cf_model: building interaction matrix…")
        rows = _collect_interaction_rows()
        df = _as_interaction_frame(rows)

        if df.empty:
            save_cf_training_state(
                status="skipped_empty_matrix",
                value_bool=False,
                metadata={
                    "reason": "interaction matrix is empty",
                    "force": force,
                },
            )
            logger.warning("task_train_cf_model: interaction matrix is empty — aborting.")
            return

        matrix_rows = len(df)
        unique_sessions = df["user_id"].nunique()
        unique_villages = df["item_id"].nunique()

        logger.info(
            "task_train_cf_model: matrix has %d sessions × %d villages, %d rows",
            unique_sessions,
            unique_villages,
            matrix_rows,
        )

        reader = Reader(rating_scale=(1, 5))
        training_df = df[["user_id", "item_id", "rating"]]
        data = Dataset.load_from_df(training_df, reader)
        trainset = data.build_full_trainset()

        model = SVD(n_factors=10, n_epochs=20, random_state=42)
        model.fit(trainset)

        # Cache for 25 hours so it survives until the next daily run
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
        logger.info("task_train_cf_model: SVD model trained and cached as vtf:reco:cf_model.")

    except Exception as exc:
        logger.exception("task_train_cf_model failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    name="apps.recommender.tasks.task_check_cf_readiness_after_estimate",
    ignore_result=True,
)
def task_check_cf_readiness_after_estimate() -> None:
    """Lightweight post-estimate CF flag check (AC2.11).

    Triggered via Django signal after each /estimate/stay call.
    Only updates the cache flag if thresholds are newly met, avoiding
    unnecessary DB queries on every request after the flag is already set.
    """
    # If already confirmed ready, no need to recheck on every simulation
    if cache.get("cf_model_ready"):
        logger.info("task_check_cf_readiness_after_estimate: already ready, skipping")
        return

    # Run the full check asynchronously
    result = task_check_cf_readiness.delay()
    logger.info(
        "task_check_cf_readiness_after_estimate: enqueued task_check_cf_readiness task_id=%s",
        getattr(result, "id", None),
    )
