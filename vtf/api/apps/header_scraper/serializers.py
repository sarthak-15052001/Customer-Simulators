"""Serializers for the header banner public + staff APIs."""
from __future__ import annotations

from rest_framework import serializers

from apps.header_scraper.models import HeaderBanner, HeaderBannerSnapshot


class HeaderBannerSegmentSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["text", "link", "br"])
    value = serializers.CharField(required=False, allow_blank=True)
    text = serializers.CharField(required=False, allow_blank=True)
    href = serializers.URLField(required=False, allow_blank=True)


class HeaderBannerSerializer(serializers.ModelSerializer):
    scrapedAt = serializers.DateTimeField(source="scraped_at", allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = HeaderBanner
        fields = [
            "is_active",
            "language",
            "segments",
            "plain_text",
            "source_url",
            "content_hash",
            "scrapedAt",
            "createdAt",
            "updatedAt",
        ]


class HeaderBannerSnapshotSerializer(serializers.ModelSerializer):
    scrapedAt = serializers.DateTimeField(source="scraped_at")

    class Meta:
        model = HeaderBannerSnapshot
        fields = [
            "id",
            "language",
            "status",
            "content_hash",
            "plain_text",
            "source_url",
            "error",
            "scrapedAt",
        ]


class HeaderScrapeRequestSerializer(serializers.Serializer):
    language = serializers.ChoiceField(
        choices=["FR", "GB", ""],
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional. Omit or blank to scrape FR and GB.",
    )


class HeaderScrapeResponseSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    language = serializers.CharField(allow_null=True, allow_blank=True)
    message = serializers.CharField()


class HeaderDryRunAlertSerializer(serializers.Serializer):
    """Body for POST /api/v5/header-scraper/dry-run/"""

    scenario = serializers.ChoiceField(
        choices=[
            "fetch_failed",
            "parse_failed",
            "success",
            "batch_summary",
        ],
        help_text=(
            "Which scenario to simulate. "
            "fetch_failed = HTTP + Playwright + LLM fallback all failed; "
            "parse_failed = banner HTML found but 0 segments parsed; "
            "success = banner content changed and published OK; "
            "batch_summary = fake FR + GB batch result."
        ),
    )
    language = serializers.ChoiceField(
        choices=["FR", "GB"],
        required=False,
        default="FR",
        help_text="Language to use in the fake payload (default: FR).",
    )


class HeaderDryRunAlertResponseSerializer(serializers.Serializer):
    """Response data for POST /api/v5/header-scraper/dry-run/."""

    scenario = serializers.CharField()
    language = serializers.CharField(required=False)
    languages = serializers.IntegerField(required=False)
