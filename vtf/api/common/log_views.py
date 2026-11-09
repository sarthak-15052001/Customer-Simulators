from __future__ import annotations

from pathlib import Path

from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from common.log_reader import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    paginate_log_entries,
    parse_positive_int,
    read_log_entries,
)
from common.log_serializers import PaginatedLogSerializer
from common.response import CustomResponse


class ApiLogListView(APIView):
    @extend_schema(
        tags=["loggers"],
        parameters=[
            OpenApiParameter("page", int, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False),
        ],
        responses={status.HTTP_200_OK: PaginatedLogSerializer},
        summary="List all API / app log entries (local.log)",
    )
    def get(self, request):
        # Do not filter by logger_name here — local.log is the catch-all file
        # for Django, translation_manager, catalog, pricing, mailer, etc.
        # Filtering to only 'common.api' would silently hide translation_manager
        # (and other app-level) entries that also write to this file.
        return log_file_response(request, "local.log", "API logs fetched successfully.")


class CeleryLogListView(APIView):
    @extend_schema(
        tags=["loggers"],
        parameters=[
            OpenApiParameter("page", int, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False),
        ],
        responses={status.HTTP_200_OK: PaginatedLogSerializer},
    )
    def get(self, request):
        return log_file_response(request, "celery_logger.log", "Celery logs fetched successfully.")


class ScraperLogListView(APIView):
    @extend_schema(
        tags=["loggers"],
        parameters=[
            OpenApiParameter("page", int, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("limit", int, OpenApiParameter.QUERY, required=False),
        ],
        responses={status.HTTP_200_OK: PaginatedLogSerializer},
        summary="List scraper log entries (scraper_logger.log)",
    )
    def get(self, request):
        return log_file_response(request, "scraper_logger.log", "Scraper logs fetched successfully.")



def log_file_response(request, filename: str, message: str) -> CustomResponse:
    page = parse_positive_int(request.query_params.get("page"), 1)
    limit = min(parse_positive_int(request.query_params.get("limit"), DEFAULT_PAGE_LIMIT), MAX_PAGE_LIMIT)
    path = Path(settings.LOG_DIR) / filename
    # No logger_name filter: local.log is a shared catch-all for all app-level
    # loggers (django, apps.catalog, translation_manager, common.api, etc.).
    # Filtering to a single logger name here would silently hide valid entries.
    entries = read_log_entries(path, logger_name=None)
    return CustomResponse.success(message, data=paginate_log_entries(entries, page, limit))
