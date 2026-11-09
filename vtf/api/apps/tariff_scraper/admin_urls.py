from django.contrib import admin
from django.urls import path

from apps.tariff_scraper import admin_views

urlpatterns = [
    path(
        "dashboard/",
        admin.site.admin_view(admin_views.price_health_dashboard_view),
        name="tariff_scraper_price_health_dashboard",
    ),
    path(
        "dashboard/<str:village_id>/errors/",
        admin.site.admin_view(admin_views.village_error_detail_view),
        name="tariff_scraper_village_error_detail",
    ),
    # Start/stop scraping control panel (mirrors apps/scraper/admin_urls.py).
    path(
        "control/",
        admin.site.admin_view(admin_views.tariff_scraper_control_view),
        name="tariff_scraper_control",
    ),
    path(
        "control/start/",
        admin.site.admin_view(admin_views.tariff_scraper_start_view),
        name="tariff_scraper_control_start",
    ),
    path(
        "control/stop/",
        admin.site.admin_view(admin_views.tariff_scraper_stop_view),
        name="tariff_scraper_control_stop",
    ),
    path(
        "control/status/<str:task_id>/",
        admin.site.admin_view(admin_views.tariff_scraper_status_view),
        name="tariff_scraper_control_status",
    ),
]
