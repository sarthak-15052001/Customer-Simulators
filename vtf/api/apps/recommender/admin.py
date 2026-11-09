"""Django admin for recommender models (Phase 2)."""
from __future__ import annotations

from django.contrib import admin

from apps.recommender.models import (
    RecommendationSystemState,
    RecoWeights,
    VillageInteraction,
    VillagePopularityCache,
)


@admin.register(RecommendationSystemState)
class RecommendationSystemStateAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "value_bool", "updated_at")
    search_fields = ("key",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("key",)


@admin.register(VillageInteraction)
class VillageInteractionAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "session_id", "village", "kind", "value")
    list_filter = ("kind",)
    search_fields = ("session_id", "village__id", "village__nom")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    autocomplete_fields = ("village", "user")
    list_per_page = 50


@admin.register(RecoWeights)
class RecoWeightsAdmin(admin.ModelAdmin):
    list_display = ("id", "is_active", "updated_at")
    list_filter = ("is_active",)
    actions = ("activate_selected",)

    @admin.action(description="Mark selected as the active weights (deactivates others)")
    def activate_selected(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one row to activate.", level="error")
            return
        target = queryset.first()
        RecoWeights.objects.filter(is_active=True).exclude(pk=target.pk).update(is_active=False)
        target.is_active = True
        target.save(update_fields=["is_active"])
        self.message_user(request, f"RecoWeights #{target.pk} is now active.")


@admin.register(VillagePopularityCache)
class VillagePopularityCacheAdmin(admin.ModelAdmin):
    list_display = (
        "village",
        "score",
        "views_30d",
        "simulations_30d",
        "bookmarks_30d",
        "updated_at",
    )
    search_fields = ("village__id", "village__nom")
    autocomplete_fields = ("village",)
    ordering = ("-score",)
