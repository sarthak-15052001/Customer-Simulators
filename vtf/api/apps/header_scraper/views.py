"""Header banner API views.

Public:
  GET /api/v5/header-banner?lang=FR

Staff:
  POST /api/v5/admin/header-scraper/scrape
  GET  /api/v5/admin/header-scraper/jobs
  POST /api/v5/header-scraper/dry-run/
"""
from __future__ import annotations

import logging

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.header_scraper.models import HeaderBanner, HeaderBannerSnapshot
from apps.header_scraper.serializers import (
    HeaderBannerSerializer,
    HeaderBannerSnapshotSerializer,
    HeaderDryRunAlertResponseSerializer,
    HeaderDryRunAlertSerializer,
    HeaderScrapeRequestSerializer,
    HeaderScrapeResponseSerializer,
)
from apps.header_scraper.services.sync import normalize_api_language
from common.permissions import StaffAPIViewMixin
from common.response import CustomResponse

logger = logging.getLogger("header_scraper")


class HeaderBannerView(APIView):
    """Public read of the published top announcement banner."""

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "lang",
                str,
                required=False,
                description="Simulator language: FR, GB, ES, NL (ES/NL → FR).",
            ),
        ],
        responses={200: HeaderBannerSerializer},
        tags=["v5"],
        summary="Get VTF top header banner",
    )
    def get(self, request: Request) -> CustomResponse:
        lang = normalize_api_language(request.query_params.get("lang"))
        banner = (
            HeaderBanner.objects.filter(language=lang, is_active=True)
            .order_by("-scraped_at")
            .first()
        )
        if not banner:
            return CustomResponse.success("No header banner published.", data=None)

        data = HeaderBannerSerializer(banner).data
        return CustomResponse.success("Header banner", data=data)


class HeaderScrapeTriggerView(StaffAPIViewMixin, APIView):
    """Staff-only: queue a header banner scrape."""

    serializer_class = HeaderScrapeRequestSerializer

    @extend_schema(
        request=HeaderScrapeRequestSerializer,
        responses={202: HeaderScrapeResponseSerializer},
        tags=["v5"],
        summary="Trigger header banner scrape",
    )
    def post(self, request: Request) -> CustomResponse:
        serializer = HeaderScrapeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        language = (serializer.validated_data.get("language") or "").strip().upper()

        if language:
            from apps.header_scraper.tasks import task_scrape_header_banner_language

            async_result = task_scrape_header_banner_language.delay(language)
            message = f"Queued header scrape for {language}."
            return CustomResponse.success(
                message,
                data={
                    "task_id": async_result.id,
                    "language": language,
                    "message": message,
                },
                status_code=status.HTTP_202_ACCEPTED,
            )

        from apps.header_scraper.tasks import task_scrape_header_banner

        async_result = task_scrape_header_banner.delay()
        message = "Queued header scrape for FR and GB."
        return CustomResponse.success(
            message,
            data={
                "task_id": async_result.id,
                "language": None,
                "message": message,
            },
            status_code=status.HTTP_202_ACCEPTED,
        )


class HeaderScrapeJobsView(StaffAPIViewMixin, APIView):
    """Staff-only: recent scrape snapshots."""

    @extend_schema(
        parameters=[
            OpenApiParameter("lang", str, required=False),
            OpenApiParameter("limit", int, required=False),
        ],
        responses={200: HeaderBannerSnapshotSerializer(many=True)},
        tags=["v5"],
        summary="List recent header scrape snapshots",
    )
    def get(self, request: Request) -> CustomResponse:
        qs = HeaderBannerSnapshot.objects.all()
        lang = (request.query_params.get("lang") or "").strip().upper()
        if lang:
            qs = qs.filter(language=normalize_api_language(lang))
        try:
            limit = min(int(request.query_params.get("limit") or 20), 100)
        except ValueError:
            limit = 20
        rows = list(qs.order_by("-scraped_at")[:limit])
        data = HeaderBannerSnapshotSerializer(rows, many=True).data
        return CustomResponse.success(f"{len(data)} header scrape snapshots.", data=data)


class DryRunAlertView(StaffAPIViewMixin, APIView):
    """POST /api/v5/header-scraper/dry-run/ — test alert pipeline with fake payload.

    Sends a Discord alert using a fake payload — no live VTF page is hit and
    nothing is written to HeaderBanner/HeaderBannerSnapshot. Use this to
    verify the Discord alert system end-to-end (same idea as
    apps.tariff_scraper's POST /api/v4/tariff-scraper/dry-run/).

    Scenarios:
      fetch_failed  → 🔴 RED (HTTP + Playwright + LLM fallback all failed)
      parse_failed  → 🟡 YELLOW (banner HTML found but 0 segments parsed)
      success       → 🟢 GREEN (banner content changed and published OK)
      batch_summary → 🔴/🟡/🟢 (fake FR + GB batch result)
    """

    @extend_schema(
        operation_id="v5_header_dry_run_alert",
        request=HeaderDryRunAlertSerializer,
        responses={200: HeaderDryRunAlertResponseSerializer},
        tags=["v5"],
        summary="Dry-run test alert pipeline",
        description=(
            "Sends a Discord alert using a fake payload. "
            "Use this to verify the header banner alert system works end-to-end."
        ),
    )
    def post(self, request: Request) -> CustomResponse:
        from apps.header_scraper.services.alerts import (
            notify_batch_summary,
            notify_scrape_failure,
            notify_scrape_success,
        )

        serializer = HeaderDryRunAlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        scenario = serializer.validated_data["scenario"]
        language = serializer.validated_data.get("language", "FR")
        source_url = (
            "https://www.vtf-vacances.com/fr_FR/"
            if language == "FR"
            else "https://www.vtf-vacances.com/en_GB/"
        )

        if scenario == "success":
            result = {
                "language": language,
                "source_url": source_url,
                "content_hash": "abc123def456",
                "plain_text": "Ne manquez pas les dernières offres — dry-run test.",
            }
            notify_scrape_success(result)
            return CustomResponse.success(
                f"Success alert sent for language '{language}'.",
                data={"scenario": scenario, "language": language},
            )

        if scenario == "batch_summary":
            results = [
                {
                    "language": "FR",
                    "status": "success",
                    "source_url": "https://www.vtf-vacances.com/fr_FR/",
                },
                {
                    "language": "GB",
                    "status": "fetch_failed",
                    "source_url": "https://www.vtf-vacances.com/en_GB/",
                    "error": (
                        "Step 1 (HTTP Fetch) | scrape.py → scrape_header_banner_html_http() | HTTP 403 Forbidden"
                        " | Step 2 (Playwright Scrape) | scrape.py → scrape_header_banner_html_playwright() | "
                        "Banner node not found on page (selector cascade empty)."
                        " | Step 3 (LLM Fallback) | scrape.py → scrape_header_banner_html_llm() | "
                        "LLM fallback is disabled."
                    ),
                },
            ]
            notify_batch_summary(results)
            return CustomResponse.success(
                "Batch summary alert sent (2 languages: 1 OK, 1 failed).",
                data={"scenario": scenario, "languages": len(results)},
            )

        if scenario == "fetch_failed":
            result = {
                "language": language,
                "status": "fetch_failed",
                "source_url": source_url,
                "error": (
                    f"Step 1 (HTTP Fetch) | scrape.py → scrape_header_banner_html_http() | "
                    f"HTTP fetch failed: 403 Client Error: Forbidden for url: {source_url}"
                    " | Step 2 (Playwright Scrape) | scrape.py → scrape_header_banner_html_playwright() | "
                    "Banner node not found on page (selector cascade empty)."
                    " | Step 3 (LLM Fallback) | scrape.py → scrape_header_banner_html_llm() | "
                    "LLM fallback is disabled."
                ),
            }
        elif scenario == "parse_failed":
            result = {
                "language": language,
                "status": "parse_failed",
                "source_url": source_url,
                "error": (
                    "Step 4 (Parse) | sync.py → sync_language() | "
                    "Parsed zero segments from banner HTML."
                ),
            }
        else:
            return CustomResponse.error(
                f"Unknown scenario '{scenario}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        notify_scrape_failure(result)

        return CustomResponse.success(
            f"Alert sent for scenario '{scenario}' (language: {language}).",
            data={"scenario": scenario, "language": language},
        )
