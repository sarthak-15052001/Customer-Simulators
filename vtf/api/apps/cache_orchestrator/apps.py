"""Cache orchestrator app config.

Wires the PricingRules post_save signal in ready() so the cache
auto-rebuilds whenever a new active ruleset is saved.
"""
from __future__ import annotations

from importlib import import_module

from django.apps import AppConfig


class CacheOrchestratorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cache_orchestrator"
    label = "cache_orchestrator"
    verbose_name = "Cache Orchestrator"

    def ready(self) -> None:
        # Wire PricingRules post_save → auto cache rebuild (AC3.5)
        import_module("apps.cache_orchestrator.signals")
