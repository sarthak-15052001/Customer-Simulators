"""URL routes for header_scraper — mounted under /api/v5/."""
from __future__ import annotations

from django.urls import path

from apps.header_scraper.views import (
    DryRunAlertView,
    HeaderBannerView,
    HeaderScrapeJobsView,
    HeaderScrapeTriggerView,
)

urlpatterns = [
    path("header-banner", HeaderBannerView.as_view(), name="header-banner"),
    path(
        "admin/header-scraper/scrape",
        HeaderScrapeTriggerView.as_view(),
        name="header-scraper-scrape",
    ),
    path(
        "admin/header-scraper/jobs",
        HeaderScrapeJobsView.as_view(),
        name="header-scraper-jobs",
    ),
    path(
        "header-scraper/dry-run/",
        DryRunAlertView.as_view(),
        name="header-scraper-dry-run",
    ),
]
