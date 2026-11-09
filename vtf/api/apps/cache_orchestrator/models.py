"""Cache orchestrator ORM models (Phase 3).

Source of truth: vtf/api/docs/03-data-models.md (cache_orchestrator section).
Spec §5.1.

Cache key naming convention (informational; enforced in services):

    vtf:catalog:villages:list                     → GET /villages
    vtf:catalog:villages:{id}:detail              → GET /villages/{id}
    vtf:catalog:villages:{id}:attractions         → GET /villages/{id}/attractions
    vtf:catalog:regions:list                      → GET /regions
    vtf:catalog:regions:{key}:activities          → GET /regions/{key}/activities
    vtf:catalog:pricing_rules                     → GET /pricing-rules
    vtf:catalog:seasons                           → GET /seasons
    vtf:catalog:meals                             → GET /meals
    vtf:catalog:fuels                             → GET /fuels
    vtf:catalog:promos_catalog                    → GET /promos/catalog
    vtf:reco:popularity:{village_id}              → popularity score
    vtf:reco:cf_model                             → serialized SVD model
    vtf:booking:token:{token}                     → redirect token payload
"""
from __future__ import annotations

from django.db import models


class CacheRebuildLog(models.Model):
    """Audit log of every cache rebuild — manual, signal-driven, or cron.

    Surfaced via GET /api/v1/health and the admin dashboard.
    """

    SCOPE_CHOICES = [
        ("all", "Everything"),
        ("catalog", "Villages, regions, activities, animations, meals, fuels"),
        ("pricing", "Pricing rules, season calendar, promo catalog"),
        ("recommendations", "Popularity cache, CF model"),
        ("booking_urls", "Pre-built VTF target URLs"),
        # Granular scopes use a colon: 'villages:biarritz' / 'regions:Aquitaine / Landes'
    ]
    id = models.AutoField(primary_key=True)
    scope = models.CharField(max_length=64)
    keys_invalidated = models.IntegerField(default=0)
    keys_rebuilt = models.IntegerField(default=0)
    duration_ms = models.IntegerField(default=0)
    triggered_by = models.CharField(max_length=128)
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
