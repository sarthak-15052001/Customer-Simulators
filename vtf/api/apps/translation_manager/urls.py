"""URL routes for translation_manager — mounted under /api/v6/."""
from __future__ import annotations

from django.urls import path

from apps.translation_manager.views import (
    TranslationListView,
    TranslationSourceSyncView,
    TranslationTriggerView,
)

urlpatterns = [
    path("translations", TranslationListView.as_view(), name="translations"),
    path(
        "admin/translation-manager/translate",
        TranslationTriggerView.as_view(),
        name="translation-manager-translate",
    ),
    path(
        "admin/translation-manager/sync-sources",
        TranslationSourceSyncView.as_view(),
        name="translation-manager-sync-sources",
    ),
]
