from django.urls import path

from apps.tariff_scraper.views import (
    AllVillageTariffsListView,
    DryRunAlertView,
    FormatChangeLogView,
    TariffApprovalDetailView,
    TariffApprovalListView,
    TariffScrapeView,
    VillageTariffListView,
)

urlpatterns = [
    # POST /api/v4/tariff-scraper/scrape/
    path(
        "tariff-scraper/scrape/",
        TariffScrapeView.as_view(),
        name="tariff-scrape",
    ),
    # GET /api/v4/tariff-scraper/tariffs/  (all villages — before village detail)
    path(
        "tariff-scraper/tariffs/",
        AllVillageTariffsListView.as_view(),
        name="tariff-list-all",
    ),
    # GET /api/v4/tariff-scraper/tariffs/<village_id>/
    path(
        "tariff-scraper/tariffs/<str:village_id>/",
        VillageTariffListView.as_view(),
        name="tariff-list",
    ),
    # GET /api/v4/tariff-scraper/format-changes/
    path(
        "tariff-scraper/format-changes/",
        FormatChangeLogView.as_view(),
        name="format-change-log",
    ),
    # POST /api/v4/tariff-scraper/dry-run/
    path(
        "tariff-scraper/dry-run/",
        DryRunAlertView.as_view(),
        name="dry-run-alert",
    ),
    # Staff: list / review pending tariff proposals
    path(
        "admin/tariff-scraper/approvals/",
        TariffApprovalListView.as_view(),
        name="tariff-approval-list",
    ),
    path(
        "admin/tariff-scraper/approvals/<int:approval_id>/",
        TariffApprovalDetailView.as_view(),
        name="tariff-approval-detail",
    ),
]
