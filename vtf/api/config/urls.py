"""Project URL configuration.

All public endpoints live under `/api/v1/`. OpenAPI / Swagger / ReDoc are
served from `/api/` with no version prefix (one schema per build).
"""
from __future__ import annotations

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from common.log_views import ApiLogListView, CeleryLogListView, ScraperLogListView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.pricing.urls")),
    path("api/v1/", include("apps.mailer.urls")),
    path("api/v1/loggers", ApiLogListView.as_view(), name="loggers"),
    path("api/v1/loggers/celery", CeleryLogListView.as_view(), name="loggers-celery"),
    path("api/v1/loggers/scraper", ScraperLogListView.as_view(), name="loggers-scraper"),
    path("api/v2/", include("apps.recommender.urls")),
    path("api/v3/", include("apps.cache_orchestrator.urls")),
    path("api/v3/", include("apps.scraper.urls")),
    path("api/v4/", include("apps.tariff_scraper.urls")),
    path("api/v5/", include("apps.header_scraper.urls")),
    path("api/v6/", include("apps.translation_manager.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
