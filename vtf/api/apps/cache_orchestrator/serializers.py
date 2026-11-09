"""Serializers for cache_orchestrator admin endpoint.

  POST /api/v1/admin/cache/rebuild
    Input:  CacheRebuildRequestSerializer
    Output: CacheRebuildResponseSerializer
"""
from __future__ import annotations

from rest_framework import serializers

VALID_SCOPES = [
    "all",
    "catalog",
    "pricing",
    "recommendations",
    "booking_urls",
]


class CacheRebuildRequestSerializer(serializers.Serializer):
    """Validates the POST /admin/cache/rebuild request body.

    Example::
        {
            "scope": "pricing",
            "reason": "New pricing rules uploaded for summer 2027"
        }

    Granular scopes like "villages:biarritz" or "regions:Alpes / Savoie"
    are also accepted — they bypass the VALID_SCOPES list check.
    """

    scope = serializers.CharField(
        default="all",
        help_text=(
            "Which cache scope to rebuild. "
            f"One of {VALID_SCOPES} or a granular scope like 'villages:biarritz'."
        ),
    )
    reason = serializers.CharField(
        default="",
        allow_blank=True,
        max_length=512,
        help_text="Human-readable reason for the rebuild (stored in CacheRebuildLog).",
    )

    def validate_scope(self, value: str) -> str:
        # Accept known fixed scopes
        if value in VALID_SCOPES:
            return value
        # Accept granular scopes: "villages:<id>" or "regions:<key>"
        if value.startswith("villages:") or value.startswith("regions:"):
            return value
        raise serializers.ValidationError(
            f"Invalid scope '{value}'. "
            f"Must be one of {VALID_SCOPES} or 'villages:<id>' / 'regions:<key>'."
        )


class CacheRebuildResponseSerializer(serializers.Serializer):
    """Shape of the POST /admin/cache/rebuild response.

    Matches spec §US-5.1 response shape exactly.
    """

    status = serializers.CharField()
    scope = serializers.CharField()
    keysInvalidated = serializers.IntegerField()
    keysRebuilt = serializers.IntegerField()
    durationMs = serializers.IntegerField()
    triggeredBy = serializers.CharField()
    reason = serializers.CharField(allow_blank=True)
    timestamp = serializers.DateTimeField()


class CacheRebuildLogSerializer(serializers.Serializer):
    """Read-only serializer for CacheRebuildLog rows (used by health endpoint)."""

    scope = serializers.CharField()
    keysInvalidated = serializers.IntegerField(source="keys_invalidated")
    keysRebuilt = serializers.IntegerField(source="keys_rebuilt")
    durationMs = serializers.IntegerField(source="duration_ms")
    triggeredBy = serializers.CharField(source="triggered_by")
    reason = serializers.CharField()
    createdAt = serializers.DateTimeField(source="created_at")


class CacheKeyTtlSerializer(serializers.Serializer):
    """One row in the per-key TTL listing."""

    key = serializers.CharField()
    ttlSeconds = serializers.IntegerField(allow_null=True)
    noExpiry = serializers.BooleanField()


class CacheStatusSerializer(serializers.Serializer):
    """`GET /admin/cache/status` — live cache dashboard (spec US-5.1)."""

    backend = serializers.CharField()
    connected = serializers.BooleanField()
    totalKeys = serializers.IntegerField(allow_null=True)
    memoryUsedMb = serializers.FloatField(allow_null=True)
    hitRatePercent = serializers.FloatField(allow_null=True)
    oldestKeyAgeSec = serializers.IntegerField(allow_null=True)
    lastRebuild = serializers.CharField(allow_null=True)
    lastRebuildScope = serializers.CharField(allow_null=True)
    lastRebuildDurationMs = serializers.IntegerField(allow_null=True)
    scopes = serializers.DictField(child=serializers.IntegerField(), required=False)
    keys = CacheKeyTtlSerializer(many=True, required=False)
