"""ORM models for the Django-admin-driven translation table.

This is the "Translation Table" the client asked for: staff (or any other
part of the app) write/​edit a canonical French ``TranslationSource`` row
in the Django admin, and a Celery task automatically translates it through
the configured LLM into every target language, **overwriting** the matching
``TranslationEntry.translated_text`` each time the source text changes.

This is intentionally separate from ``apps.catalog.services.translations``
(the existing v1 runtime request/response translator) — that module is left
untouched. This table is for admin-managed, persisted translations that are
visible and editable as rows in the Django admin, not the on-the-fly API
response translation used by v1.
"""
from __future__ import annotations

import hashlib

from django.db import models

LANGUAGE_CHOICES = [
    ("FR", "French"),
    ("GB", "English"),
]
LANGUAGE_CODES = [code for code, _ in LANGUAGE_CHOICES]

SOURCE_LANGUAGE_CHOICES = LANGUAGE_CHOICES
TARGET_LANGUAGE_CHOICES = LANGUAGE_CHOICES


def target_languages_for(source_language: str) -> list[str]:
    """Every configured language available in TranslationEntry."""
    return LANGUAGE_CODES


def _hash_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


class TranslationSource(models.Model):
    """One canonical (French) piece of text to keep translated.

    ``key`` is a stable, human-assigned identifier (e.g.
    ``catalog.village.description.talloires`` or
    ``admin.header_scraper.banner.promo``) so the same row can be looked up
    and overwritten again later instead of growing duplicate rows.
    """

    key = models.SlugField(max_length=160, unique=True)
    source_language = models.CharField(
        max_length=2, choices=LANGUAGE_CHOICES, default="FR"
    )
    source_text = models.TextField()
    content_hash = models.CharField(max_length=64, blank=True, default="", editable=False)
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True, default="")
    # Set by sync_translation_sources when this row was auto-pulled from a
    # real model field, e.g. "catalog.Village.nom" — blank for rows entered
    # by hand in the admin. See apps.translation_manager.services.registry.
    source_model_ref = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key

    def save(self, *args, **kwargs):
        self.content_hash = _hash_text(self.source_text)
        super().save(*args, **kwargs)


class TranslationEntry(models.Model):
    """One target-language translation of a ``TranslationSource`` row.

    ``translated_text`` is overwritten in place every time the Celery task
    runs for this (source, language) pair — that overwrite is the behaviour
    the client described ("automatically translate and overwrite").
    """

    STATUS_PENDING = "pending"
    STATUS_TRANSLATED = "translated"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_TRANSLATED, "Translated"),
        (STATUS_FAILED, "Failed"),
    ]

    source = models.ForeignKey(
        TranslationSource, related_name="translations", on_delete=models.CASCADE
    )
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    translated_text = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    model_used = models.CharField(max_length=120, blank=True, default="")
    source_content_hash = models.CharField(max_length=64, blank=True, default="")
    error = models.TextField(blank=True, default="")
    translated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("source", "language")]
        ordering = ["source__key", "language"]

    def __str__(self) -> str:
        return f"TranslationEntry({self.source_id}, {self.language}, {self.status})"

    @property
    def is_stale(self) -> bool:
        """True when the source text changed since this row was translated."""
        return self.source_content_hash != self.source.content_hash
