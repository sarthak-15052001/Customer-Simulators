"""ORM models for the VTF homepage top-banner scraper."""
from __future__ import annotations

from django.db import models


class HeaderBanner(models.Model):
    """Published announcement banner for one simulator language."""

    LANGUAGE_CHOICES = [
        ("FR", "French"),
        ("GB", "English"),
    ]

    language = models.CharField(max_length=2, unique=True, choices=LANGUAGE_CHOICES)
    segments = models.JSONField(default=list)
    plain_text = models.TextField(blank=True, default="")
    source_url = models.URLField(max_length=512)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    is_active = models.BooleanField(default=True)
    scraped_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["language"]

    def __str__(self) -> str:
        preview = (self.plain_text or "")[:60]
        return f"HeaderBanner({self.language}): {preview}"


class HeaderBannerSnapshot(models.Model):
    """One scrape attempt (success, unchanged, or failure)."""

    STATUS_SUCCESS = "success"
    STATUS_UNCHANGED = "unchanged"
    STATUS_PARSE_FAILED = "parse_failed"
    STATUS_FETCH_FAILED = "fetch_failed"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_UNCHANGED, "Unchanged"),
        (STATUS_PARSE_FAILED, "Parse failed"),
        (STATUS_FETCH_FAILED, "Fetch failed"),
    ]

    language = models.CharField(max_length=2, db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    plain_text = models.TextField(blank=True, default="")
    segments = models.JSONField(default=list, blank=True)
    source_url = models.URLField(max_length=512, blank=True, default="")
    error = models.TextField(blank=True, default="")
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scraped_at"]

    def __str__(self) -> str:
        return f"HeaderBannerSnapshot({self.language}, {self.status})"
