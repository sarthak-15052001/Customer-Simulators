"""
The only change is adding `import apps.recommender.signals` in ready()
so the SimulationLog post_save signal is wired when Django starts (AC2.11).
"""

from __future__ import annotations

from importlib import import_module

from django.apps import AppConfig


class RecommenderConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recommender"
    # label = "recommender"
    verbose_name = "Recommender"


    def ready(self) -> None:
        # Wire the post_save signal on SimulationLog so that
        # task_check_cf_readiness_after_estimate fires after every new
        # simulation — keeping cf_model_ready flag up to date without
        # waiting for the daily cron (AC2.11).
        import_module("apps.recommender.signals")
