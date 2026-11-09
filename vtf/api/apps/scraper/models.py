"""Scraper ORM models (Phase 3).

Source of truth: vtf/api/docs/03-data-models.md (scraper section). Spec §5.2.
"""
from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.db import models


class ScrapingJob(models.Model):
    """One scraping run targeting a village or a region.

    Created by POST /api/v1/admin/scraper/activities (async).
    """

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    id = models.CharField(max_length=64, primary_key=True)
    target_type = models.CharField(max_length=16)
    target_id = models.CharField(max_length=64)
    sources = models.JSONField()
    radius_km = models.SmallIntegerField(default=30)
    max_results = models.SmallIntegerField(default=50)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default="queued"
    )
    result_summary = models.JSONField(null=True, blank=True)
    triggered_by = models.CharField(max_length=128)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ScrapingCandidate(models.Model):
    """Pre-validation staging row.

    Activities discovered by scraping land here; a human reviews and either
    imports them or rejects. Spec §5.2 / US-5.5.
    """

    STATUS_CHOICES = [
        ("new", "New"),
        ("imported", "Imported"),
        ("rejected", "Rejected"),
        ("deferred", "Deferred"),
        ("hidden", "Hidden"),
    ]
    id = models.CharField(max_length=64, primary_key=True)
    job = models.ForeignKey(
        ScrapingJob, on_delete=models.CASCADE, related_name="candidates"
    )
    village = models.ForeignKey(
        "catalog.Village", on_delete=models.SET_NULL, null=True, blank=True
    )
    region = models.CharField(max_length=64)
    source = models.CharField(max_length=32)
    source_url = models.URLField(max_length=512)
    source_id = models.CharField(max_length=128)
    nom = models.CharField(max_length=128)
    type_emoji = models.CharField(max_length=8)
    price_adult = models.SmallIntegerField(null=True, blank=True)
    price_child = models.SmallIntegerField(null=True, blank=True)
    distance_km = models.FloatField()
    rating = models.FloatField(null=True, blank=True)
    review_count = models.IntegerField(default=0)
    saisons = models.JSONField(default=list)
    matched_activity_code = models.CharField(
        max_length=64, blank=True, default=""
    )
    match_confidence = models.FloatField(default=0.0)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default="new"
    )
    reviewed_by = models.CharField(max_length=128, blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    edits = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "region"]),
            models.Index(fields=["job", "status"]),
        ]


class PriceChangeAlert(models.Model):
    """Raised when re-scraping detects > 10 % delta on price_adult or
    price_child of an existing Activity. Spec §US-5.7.
    """

    STATUS_CHOICES = [
        ("pending", "Pending review"),
        ("approved", "Approved"),
        ("dismissed", "Dismissed"),
    ]
    id = models.AutoField(primary_key=True)
    activity = models.ForeignKey("catalog.Activity", on_delete=models.CASCADE)
    field = models.CharField(max_length=16)
    old_value = models.SmallIntegerField()
    new_value = models.SmallIntegerField()
    source = models.CharField(max_length=32)
    scraped_at = models.DateTimeField()
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default="pending"
    )


class ScrapingImportLog(models.Model):
    """Audit trail of what was imported / rejected / deferred and by whom."""

    id = models.BigAutoField(primary_key=True)
    job = models.ForeignKey(ScrapingJob, on_delete=models.CASCADE)
    candidate = models.ForeignKey(ScrapingCandidate, on_delete=models.CASCADE)
    action = models.CharField(max_length=16)
    activity = models.ForeignKey(
        "catalog.Activity", on_delete=models.SET_NULL, null=True, blank=True
    )
    edits = models.JSONField(null=True, blank=True)
    actor = models.CharField(max_length=128)
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class CandidateFilterRule(models.Model):
    """Global / exception rule used to auto-exclude or auto-hide scraped
    candidates that match a pattern (e.g. name contains "hotel").

    Evaluated by apps.scraper.services.filter_rules against every raw
    scraped item before (or right after) a ScrapingCandidate row is
    created. Configurable from Django admin — no code changes needed to
    add/edit/disable a rule.
    """

    FIELD_CHOICES = [
        ("nom", "Name"),
        ("region", "Region"),
        ("source", "Source"),
        ("type_emoji", "Type"),
    ]
    ACTION_CHOICES = [
        ("exclude", "Exclude (never create the candidate)"),
        ("hide", "Hide (create candidate, mark as hidden)"),
    ]

    name = models.CharField(max_length=128)
    field = models.CharField(max_length=16, choices=FIELD_CHOICES, default="nom")
    pattern = models.CharField(
        max_length=256,
        help_text="Regex pattern (or plain text if 'Is regex' is off).",
    )
    is_regex = models.BooleanField(default=True)
    case_sensitive = models.BooleanField(default=False)
    action = models.CharField(max_length=16, choices=ACTION_CHOICES, default="exclude")
    is_active = models.BooleanField(default=True)
    scope_region = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Leave blank to apply globally to all regions.",
    )
    scope_source = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Leave blank to apply to all sources (google_places, ot_local, ...).",
    )
    priority = models.SmallIntegerField(
        default=0,
        help_text="Lower runs first when several rules could match the same candidate.",
    )
    created_by = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        if self.is_regex and self.pattern:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValidationError({"pattern": f"Invalid regex: {exc}"})
