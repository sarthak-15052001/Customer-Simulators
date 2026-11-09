"""Scraper URL routing — mounted under /api/v3/ in config/urls.py.

Endpoints (all staff-only):
  POST /api/v3/admin/scraper/activities               — trigger scraping job
  GET  /api/v3/admin/scraper/jobs                     — list jobs
  GET  /api/v3/admin/scraper/jobs/{job_id}            — job status + candidates
  POST /api/v3/admin/scraper/import                   — batch import/reject
  GET  /api/v3/admin/scraper/candidates               — pending candidates
  GET  /api/v3/admin/scraper/price-updates            — price change alerts
  POST /api/v3/admin/scraper/price-updates/{id}       — approve/dismiss alert
"""
from __future__ import annotations

from django.urls import path

from apps.scraper.views import (
    ImportCandidatesView,
    PriceChangeAlertActionView,
    PriceChangeAlertListView,
    ScrapingCandidateListView,
    ScrapingJobDetailView,
    ScrapingJobListView,
    TriggerScrapingView,
)

urlpatterns = [
    path(
        "admin/scraper/activities",
        TriggerScrapingView.as_view(),
        name="scraper-trigger",
    ),
    path(
        "admin/scraper/jobs",
        ScrapingJobListView.as_view(),
        name="scraper-jobs",
    ),
    path(
        "admin/scraper/jobs/<str:job_id>",
        ScrapingJobDetailView.as_view(),
        name="scraper-job-detail",
    ),
    path(
        "admin/scraper/import",
        ImportCandidatesView.as_view(),
        name="scraper-import",
    ),
    path(
        "admin/scraper/candidates",
        ScrapingCandidateListView.as_view(),
        name="scraper-candidates",
    ),
    path(
        "admin/scraper/price-updates",
        PriceChangeAlertListView.as_view(),
        name="scraper-price-updates",
    ),
    path(
        "admin/scraper/price-updates/<int:alert_id>",
        PriceChangeAlertActionView.as_view(),
        name="scraper-price-update-action",
    ),
]