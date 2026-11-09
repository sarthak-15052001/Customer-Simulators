"""Cache orchestrator URL routing.

Mounted under /api/v1/ in config/urls.py:
    path("api/v1/", include("apps.cache_orchestrator.urls"))

Endpoints:
    POST /api/v1/admin/cache/rebuild   — trigger cache rebuild (staff only)
    GET  /api/v1/admin/cache/logs      — list rebuild history  (staff only)
"""
from __future__ import annotations

from django.urls import path

from apps.cache_orchestrator.views import (
    CacheRebuildLogListView,
    CacheRebuildView,
    CacheStatusView,
)

urlpatterns = [
    path(
        "admin/cache/rebuild",
        CacheRebuildView.as_view(),
        name="cache-rebuild",
    ),
    path(
        "admin/cache/status",
        CacheStatusView.as_view(),
        name="cache-status",
    ),
    path(
        "admin/cache/logs",
        CacheRebuildLogListView.as_view(),
        name="cache-rebuild-logs",
    ),
]
