"""Serializers for tariff_scraper API responses."""
from __future__ import annotations

from rest_framework import serializers

from apps.tariff_scraper.models import (
    FormatChangeLog,
    PriceSnapshot,
    TariffApproval,
    VillageTarif,
)


class VillageTarifSerializer(serializers.ModelSerializer):
    class Meta:
        model = VillageTarif
        fields = [
            "id",
            "village_id",
            "formule",
            "date_start",
            "date_end",
            "pricing_type",
            "unit_type",
            "price",
            "is_active",
            "effective_at",
            "source_snapshot_id",
        ]


class PriceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceSnapshot
        fields = [
            "id",
            "village_id",
            "formule",
            "source_page",
            "date_label",
            "date_start",
            "date_end",
            "unit_type",
            "nb_adults",
            "scraped_price",
            "is_available",
            "derivation",
            "scraped_at",
        ]


class TariffApprovalSerializer(serializers.ModelSerializer):
    village_name = serializers.CharField(source="village.nom", read_only=True)
    reviewed_by_username = serializers.SerializerMethodField()
    reverted_by_username = serializers.SerializerMethodField()

    class Meta:
        model = TariffApproval
        fields = [
            "id",
            "village_id",
            "village_name",
            "status",
            "source_url",
            "proposed_bands",
            "proposed_season_tarifs",
            # Which of the proposed season buckets this scrape actually
            # confirmed — a client showing proposed_season_tarifs without it
            # presents carried-over fixture values as freshly scraped.
            "season_tarifs_notes",
            "previous_village_tarifs",
            "bands_count",
            "reject_reason",
            "created_at",
            "reviewed_at",
            "reviewed_by",
            "reviewed_by_username",
            # A reverted approval keeps its review timestamp/author and records
            # the rollback separately — clients need both to render the history.
            "reverted_at",
            "reverted_by",
            "reverted_by_username",
        ]

    def get_reviewed_by_username(self, obj: TariffApproval) -> str | None:
        user = obj.reviewed_by
        return user.get_username() if user is not None else None

    def get_reverted_by_username(self, obj: TariffApproval) -> str | None:
        user = obj.reverted_by
        return user.get_username() if user is not None else None


class TariffApprovalActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=["approve", "reject", "revert"],
        help_text=(
            "approve — activate the proposed bands and update Village.tarifs. "
            "reject — refuse a pending proposal, pricing untouched. "
            "revert — roll back an already-applied approval."
        ),
    )
    reject_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional reason when action=reject.",
    )


class ScrapeRequestSerializer(serializers.Serializer):
    """Body for POST /api/v4/tariff-scraper/scrape/."""

    village_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=(
            "Catalog Village.id to scrape (e.g. 'lacanau'). "
            "If omitted, all 32 villages are queued."
        ),
    )


class ScrapeResponseSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    village_id = serializers.CharField(allow_null=True)
    message = serializers.CharField()


class FormatChangeLogSerializer(serializers.ModelSerializer):
    village_name = serializers.CharField(source="village.nom", read_only=True)

    class Meta:
        model = FormatChangeLog
        fields = [
            "id",
            "village_id",
            "village_name",
            "change_type",
            "source_url",
            "expected_markers",
            "found_markers",
            "missing_markers",
            "html_length",
            "table_count",
            "bands_scraped",
            "priced_bands",
            "errors",
            "detected_at",
        ]
        read_only_fields = fields

class DryRunAlertSerializer(serializers.Serializer):
    """Body for POST /api/v4/tariff-scraper/dry-run/"""

    scenario = serializers.ChoiceField(
        choices=[
            "hard_failure",
            "zero_prices",
            "parse_failure",
            "marker_missing",
            "partial",
            "success",
            "batch_summary",
        ],
        help_text=(
            "Which scenario to simulate. "
            "hard_failure = HTTP 404 / blocked; "
            "zero_prices = page loaded but no prices; "
            "parse_failure = dates/prices couldn't parse; "
            "marker_missing = all grille markers gone; "
            "partial = some data with errors; "
            "success = clean scrape OK; "
            "batch_summary = fake 32-village batch result."
        ),
    )
    village_id = serializers.CharField(
        required=False,
        default="lacanau",
        help_text="Village id to use in the fake payload (default: lacanau).",
    )


class DryRunAlertResponseSerializer(serializers.Serializer):
    """Response data for POST /api/v4/tariff-scraper/dry-run/."""

    scenario = serializers.CharField()
    village_id = serializers.CharField(required=False)
    villages = serializers.IntegerField(required=False)
