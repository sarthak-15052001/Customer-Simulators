"""Django admin for cache orchestrator models (Phase 3)."""
from __future__ import annotations

from django.contrib import admin

from apps.cache_orchestrator.models import CacheRebuildLog


@admin.register(CacheRebuildLog)
class CacheRebuildLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "scope",
        "keys_invalidated",
        "keys_rebuilt",
        "duration_ms",
        "triggered_by",
    )
    list_filter = ("scope",)
    search_fields = ("scope", "triggered_by", "reason")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
