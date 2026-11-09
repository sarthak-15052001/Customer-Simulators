from django.contrib import admin
from django.urls import path

from apps.translation_manager import admin_views

urlpatterns = [
    # Control panel (mirrors apps/header_scraper/admin_urls.py).
    path(
        "control/",
        admin.site.admin_view(admin_views.translation_control_view),
        name="translation_manager_control",
    ),
    path(
        "control/start/",
        admin.site.admin_view(admin_views.translation_control_start_view),
        name="translation_manager_control_start",
    ),
    path(
        "control/sync/",
        admin.site.admin_view(admin_views.translation_control_sync_view),
        name="translation_manager_control_sync",
    ),
    path(
        "control/status/<str:task_id>/",
        admin.site.admin_view(admin_views.translation_control_status_view),
        name="translation_manager_control_status",
    ),
]
