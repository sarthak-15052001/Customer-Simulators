"""Recommender serializers — camelCase on the wire (spec §US-4.1)."""
from __future__ import annotations

from rest_framework import serializers

from common.response import village_summary
from common.enums import Formule


# ─── Request ──────────────────────────────────────────────────────────────

class _RecommenderChildSerializer(serializers.Serializer):
    age = serializers.IntegerField(min_value=0, max_value=25)


class _FamilySerializer(serializers.Serializer):
    adultes = serializers.IntegerField(min_value=1, max_value=10)
    enfants = _RecommenderChildSerializer(many=True, required=False, default=list)
    qfVal = serializers.IntegerField(required=False, allow_null=True)
    isSoloParent = serializers.BooleanField(required=False, default=False)
    maxiFamily = serializers.BooleanField(required=False, default=False)


class _RecommenderDatesSerializer(serializers.Serializer):
    debut = serializers.DateField()
    fin = serializers.DateField()

    def validate(self, attrs):
        if attrs["fin"] <= attrs["debut"]:
            raise serializers.ValidationError("`fin` must be after `debut`.")
        return attrs


class _PreferencesSerializer(serializers.Serializer):
    envs = serializers.ListField(
        child=serializers.ChoiceField(
            choices=["sea", "mountain", "forest", "countryside", "sun"]
        ),
        required=False,
        default=list,
    )
    # formule = serializers.ChoiceField(
    #     choices=["PC", "DP", "LOC"], required=False, allow_null=True
    # )
    formule = serializers.ChoiceField(
        Formule.choices, required=False, allow_null=True
    )
    budget = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    dates = _RecommenderDatesSerializer(required=False, allow_null=True)
    mustHave = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    avoidSki = serializers.BooleanField(required=False, default=False)


class RecommendVillagesInputSerializer(serializers.Serializer):
    family = _FamilySerializer()
    preferences = _PreferencesSerializer(required=False, default=dict)
    sessionId = serializers.CharField(allow_blank=True, required=False, default="")
    limit = serializers.IntegerField(min_value=1, max_value=10, required=False, default=6)
    explain = serializers.BooleanField(required=False, default=False)


# ─── Response (OpenAPI / validation) ─────────────────────────────────────

class _VillageSummarySerializer(serializers.Serializer):
    id = serializers.CharField()
    nom = serializers.CharField()
    nom2 = serializers.CharField(required=False, allow_blank=True)
    region = serializers.CharField()
    env = serializers.CharField(required=False, allow_blank=True)
    envCode = serializers.CharField()
    formules = serializers.ListField(child=serializers.CharField())
    ski = serializers.BooleanField()
    bebeClub = serializers.BooleanField()
    qfExc = serializers.BooleanField()
    enfSoloHalf = serializers.BooleanField()
    hasLoc = serializers.BooleanField()


class RecommendedVillageSerializer(serializers.Serializer):
    village = _VillageSummarySerializer()
    score = serializers.FloatField()
    reasons = serializers.ListField(child=serializers.CharField())
    warnings = serializers.ListField(child=serializers.CharField())
    estimatedTotal = serializers.IntegerField(allow_null=True)
    bookingUrl = serializers.CharField(allow_blank=True)
    rank = serializers.IntegerField()


class RecommendVillagesOutputSerializer(serializers.Serializer):
    villages = RecommendedVillageSerializer(many=True)
    strategy = serializers.CharField()
    confidence = serializers.FloatField()
    totalScored = serializers.IntegerField()
    relaxedFilters = serializers.ListField(child=serializers.CharField())
    fallbackUsed = serializers.BooleanField()
    abGroup = serializers.CharField(required=False, allow_null=True)


class SimilarVillageSerializer(RecommendedVillageSerializer):
    """Same item shape as a single recommended village (spec §US-4.4)."""


class VillagePopularityCacheSerializer(serializers.Serializer):
    """`GET /api/v2/village-popularity-cache` — precomputed village popularity."""

    village = serializers.SerializerMethodField()
    views30d = serializers.IntegerField(source="views_30d")
    simulations30d = serializers.IntegerField(source="simulations_30d")
    bookmarks30d = serializers.IntegerField(source="bookmarks_30d")
    score = serializers.FloatField()
    updatedAt = serializers.DateTimeField(source="updated_at")

    def get_village(self, obj) -> dict:
        return village_summary(obj.village)


class BookmarkInputSerializer(serializers.Serializer):
    """`POST /api/v2/interactions/bookmark` — create/remove bookmark input."""

    sessionId = serializers.CharField(allow_blank=True, required=False, default="")
    villageId = serializers.SlugField()


# ─── Admin endpoints ──────────────────────────────────────────────────────

class InteractionStatsSerializer(serializers.Serializer):
    villageId = serializers.CharField()
    villageNom = serializers.CharField()
    views = serializers.IntegerField()
    simulations = serializers.IntegerField()
    bookmarks = serializers.IntegerField()
    total = serializers.IntegerField()


class InteractionStatsResponseSerializer(serializers.Serializer):
    period = serializers.CharField()
    startDate = serializers.DateField(required=False)
    endDate = serializers.DateField(required=False)
    villages = InteractionStatsSerializer(many=True)


class RecoWeightsInputSerializer(serializers.Serializer):
    budget_fit = serializers.FloatField(min_value=0.0, max_value=1.0, required=False)
    env_match = serializers.FloatField(min_value=0.0, max_value=1.0, required=False)
    family_fit = serializers.FloatField(min_value=0.0, max_value=1.0, required=False)
    season_availability = serializers.FloatField(min_value=0.0, max_value=1.0, required=False)
    extras_match = serializers.FloatField(min_value=0.0, max_value=1.0, required=False)
    popularity_boost = serializers.FloatField(min_value=0.0, max_value=1.0, required=False)
    interaction_boost = serializers.FloatField(min_value=0.0, max_value=1.0, required=False)
