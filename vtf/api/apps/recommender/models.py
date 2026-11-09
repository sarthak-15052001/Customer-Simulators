"""Recommender ORM models (Phase 2).

Source of truth: vtf/api/docs/03-data-models.md (recommender section).
Spec §4.2.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


class RecommendationSystemState(models.Model):
    """Small key-value table for global recommender runtime state."""

    id = models.BigAutoField(primary_key=True)
    key = models.CharField(max_length=64, unique=True, db_index=True)
    value_bool = models.BooleanField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class VillageInteraction(models.Model):
    """Lightweight signals from the frontend.

    Drives popularity ranking and is the implicit-ratings source for SVD.
    High-volume table — consider partitioning / TTL once we exceed 10M rows.
    """

    KIND_CHOICES = [
        ("view", "View"),
        ("simulate", "Simulate"),
        ("bookmark", "Bookmark"),
        ("rate", "Rate (1–5)"),
        ("click_cta", "Click CTA"),
    ]
    id = models.BigAutoField(primary_key=True)
    session_id = models.CharField(max_length=64, db_index=True)
    # Use the swappable user model reference so projects with a custom
    # AUTH_USER_MODEL keep working without an Alter migration.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    village = models.ForeignKey("catalog.Village", on_delete=models.CASCADE)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    value = models.FloatField(default=1.0)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["session_id", "kind"]),
            models.Index(fields=["village", "kind", "created_at"]),
            models.Index(fields=["created_at"]),
        ]


class RecoWeights(models.Model):
    """Tunable scoring weights for the content-based recommender.

    Singleton via the same is_active pattern as PricingRules. Spec §4.2.
    """

    id = models.AutoField(primary_key=True)
    payload = models.JSONField()
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="unique_active_reco_weights",
            ),
        ]

    @classmethod
    def active(cls) -> dict:
        return cls.objects.filter(is_active=True).values_list(
            "payload", flat=True
        ).first() or {
            "budget_fit": 0.30,
            "env_match": 0.25,
            "family_fit": 0.20,
            "season_availability": 0.15,
            "extras_match": 0.10,
            "popularity_boost": 0.05,
            "interaction_boost": 0.05,
        }


class VillagePopularityCache(models.Model):
    """Pre-computed popularity score per village.

    Refreshed by `python manage.py refresh_popularity` (cron every 6 h).
    Used as Tier 4 fallback in the recommender waterfall. Spec §4.2.
    """

    village = models.OneToOneField(
        "catalog.Village", on_delete=models.CASCADE, primary_key=True, related_name="popularity_cache",
    )
    views_30d = models.IntegerField(default=0)
    simulations_30d = models.IntegerField(default=0)
    bookmarks_30d = models.IntegerField(default=0)
    score = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)
