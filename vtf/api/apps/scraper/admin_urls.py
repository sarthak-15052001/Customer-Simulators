from django.contrib import admin
from django.urls import path

from apps.scraper import admin_views

urlpatterns = [
    path(
        "control/",
        admin.site.admin_view(admin_views.scraper_control_view),
        name="scraper_control",
    ),
    path(
        "control/start/",
        admin.site.admin_view(admin_views.scraper_start_view),
        name="scraper_start",
    ),
    path(
        "control/stop/",
        admin.site.admin_view(admin_views.scraper_stop_view),
        name="scraper_stop",
    ),
    path(
        "control/status/<str:job_id>/",
        admin.site.admin_view(admin_views.scraper_status_view),
        name="scraper_status",
    ),
]
