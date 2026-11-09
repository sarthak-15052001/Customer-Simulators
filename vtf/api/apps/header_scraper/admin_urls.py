from django.contrib import admin
from django.urls import path

from apps.header_scraper import admin_views

urlpatterns = [
    # Start/stop scraping control panel (mirrors apps/tariff_scraper/admin_urls.py).
    path(
        "control/",
        admin.site.admin_view(admin_views.header_scraper_control_view),
        name="header_scraper_control",
    ),
    path(
        "control/start/",
        admin.site.admin_view(admin_views.header_scraper_start_view),
        name="header_scraper_control_start",
    ),
    path(
        "control/stop/",
        admin.site.admin_view(admin_views.header_scraper_stop_view),
        name="header_scraper_control_stop",
    ),
    path(
        "control/status/<str:task_id>/",
        admin.site.admin_view(admin_views.header_scraper_status_view),
        name="header_scraper_control_status",
    ),
]
