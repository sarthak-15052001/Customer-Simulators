"""Recommender URL routing — spec §4.3 endpoint table."""
from __future__ import annotations

from django.urls import path

from apps.recommender.views import (
    BookmarkCreateView,
    BookmarkRemoveView,
    InteractionStatsView,
    RecoWeightsView,
    RecommendVillagesView,
    SimilarVillagesView,
    VillagePopularityCacheView,
)

urlpatterns = [
    # Phase 2 — Interactions
    path(
        "interactions/bookmark",
        BookmarkCreateView.as_view(),
        name="interactions-bookmark-create",
    ),
    path(
        "interactions/bookmark/remove",
        BookmarkRemoveView.as_view(),
        name="interactions-bookmark-remove",
    ),

    # Phase 2 — Core recommendation
    path("recommend/villages", RecommendVillagesView.as_view(), name="recommend-villages"),
    path("villages/<slug:id>/similar", SimilarVillagesView.as_view(), name="similar-villages"),
    path(
        "village-popularity-cache",
        VillagePopularityCacheView.as_view(),
        name="village-popularity-cache",
    ),

    # Phase 2 — Admin analytics
    path("admin/interactions/stats", InteractionStatsView.as_view(), name="interactions-stats"),
    path("admin/reco-weights", RecoWeightsView.as_view(), name="reco-weights"),
    # GET + POST on same path (read current / update)
]
