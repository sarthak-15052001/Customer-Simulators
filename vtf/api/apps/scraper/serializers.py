"""Serializers for scraper endpoints (Phase 3).

Covers:
  - TriggerScrapingSerializer    — POST /api/v3/admin/scraper/activities
  - ImportCandidatesSerializer   — POST /api/v3/admin/scraper/import
  - ScrapingJobSerializer        — response for job creation / polling
  - ScrapingCandidateSerializer  — candidate listing
  - PriceChangeAlertSerializer   — price alert listing
"""
from __future__ import annotations

from rest_framework import serializers

from apps.scraper.models import (
    PriceChangeAlert,
    ScrapingCandidate,
    ScrapingImportLog,
    ScrapingJob,
)

VALID_SOURCES = ["google_places", "tripadvisor", "ot_local"]
VALID_TARGET_TYPES = ["village", "region"]


class TriggerScrapingSerializer(serializers.Serializer):
    """Input for POST /api/v3/admin/scraper/activities."""

    target = serializers.ChoiceField(choices=VALID_TARGET_TYPES, default="village")
    villageId = serializers.CharField(max_length=64, required=False, allow_blank=True)
    regionKey = serializers.CharField(max_length=64, required=False, allow_blank=True)
    sources = serializers.ListField(
        child=serializers.ChoiceField(choices=VALID_SOURCES),
        default=list(VALID_SOURCES),
    )
    radiusKm = serializers.IntegerField(min_value=1, max_value=100, default=30)
    maxResults = serializers.IntegerField(min_value=1, max_value=50, default=20)
    autoImport = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if attrs["target"] == "village" and not attrs.get("villageId"):
            raise serializers.ValidationError(
                {"villageId": "Required when target='village'."}
            )
        if attrs["target"] == "region" and not attrs.get("regionKey"):
            raise serializers.ValidationError(
                {"regionKey": "Required when target='region'."}
            )
        return attrs


class ImportActionSerializer(serializers.Serializer):
    """Single action in the import batch."""

    candidateId = serializers.CharField(max_length=64)
    action = serializers.ChoiceField(choices=["import", "reject", "defer", "hide"])
    edits = serializers.DictField(required=False, allow_null=True, default=dict)
    reason = serializers.CharField(required=False, allow_blank=True, default="")

class ImportCandidatesSerializer(serializers.Serializer):
    """Input for POST /api/v3/admin/scraper/import."""

    jobId = serializers.CharField(max_length=64)
    actions = serializers.ListField(
        child=ImportActionSerializer(),
        min_length=1,
    )

class ScrapingJobSerializer(serializers.ModelSerializer):
    """Response for job creation and status polling."""

    class Meta:
        model = ScrapingJob
        fields = [
            "id",
            "target_type",
            "target_id",
            "sources",
            "radius_km",
            "max_results",
            "status",
            "result_summary",
            "triggered_by",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields


class ScrapingCandidateSerializer(serializers.ModelSerializer):
    """Candidate listing for review."""

    villageId = serializers.CharField(source="village_id", read_only=True)

    class Meta:
        model = ScrapingCandidate
        fields = [
            "id",
            "villageId",
            "region",
            "source",
            "source_url",
            "source_id",
            "nom",
            "type_emoji",
            "price_adult",
            "price_child",
            "distance_km",
            "rating",
            "review_count",
            "saisons",
            "matched_activity_code",
            "match_confidence",
            "status",
            "reviewed_by",
            "reviewed_at",
            "edits",
        ]
        read_only_fields = fields


class ScrapingImportLogSerializer(serializers.ModelSerializer):
    """Audit log entry."""

    candidateNom = serializers.CharField(source="candidate.nom", read_only=True)
    activityCode = serializers.CharField(source="activity.code", read_only=True, allow_null=True)

    class Meta:
        model = ScrapingImportLog
        fields = [
            "id",
            "candidateNom",
            "activityCode",
            "action",
            "actor",
            "reason",
            "created_at",
        ]
        read_only_fields = fields

class PriceChangeAlertSerializer(serializers.ModelSerializer):
    """Price change alert for staff review."""

    activityCode = serializers.CharField(source="activity.code", read_only=True)
    activityNom = serializers.CharField(source="activity.nom", read_only=True)

    class Meta:
        model = PriceChangeAlert
        fields = [
            "id",
            "activityCode",
            "activityNom",
            "field",
            "old_value",
            "new_value",
            "source",
            "scraped_at",
            "status",
        ]
        read_only_fields = fields