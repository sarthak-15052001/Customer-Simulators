"""Auto-queue a translation run whenever a TranslationSource's text changes.

This is what makes the table "automatic": staff edit/save the French row in
the Django admin, and this signal enqueues the Celery task that overwrites
the target-language TranslationEntry rows — no separate button needed
(though the admin also exposes a manual "Translate now" action/button for
re-runs and for when Celery is unavailable).
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.translation_manager.models import TranslationEntry, TranslationSource

logger = logging.getLogger("translation_manager")


@receiver(post_save, sender=TranslationSource)
def queue_translation_on_save(sender, instance: TranslationSource, created, **kwargs):
    if not instance.is_active:
        return
    from apps.translation_manager.tasks import task_translate_source

    try:
        task_translate_source.delay(instance.pk)
    except Exception:  # noqa: BLE001 — broker down, etc.; admin action / beat sweep covers it
        logging.getLogger("translation_manager").warning(
            "queue_translation_on_save: could not queue Celery task for source=%s "
            "(broker unavailable?) — will be picked up by task_translate_pending",
            instance.key,
        )


@receiver(post_save, sender=TranslationEntry)
def invalidate_translation_list_cache_on_save(sender, instance: TranslationEntry, **kwargs):
    """Bust the 7-day TranslationListView cache whenever an entry changes.

    Without this, a re-translation (Celery task overwriting
    ``translated_text``) or an admin edit to the source text could be
    invisible to the public API for up to 7 days — the length of the cache
    TTL added in views.py. This keeps that cache correct while still saving
    the DB/serialization work on repeat reads.
    """
    from apps.translation_manager.views import (
        TRANSLATION_LIST_CACHE_PREFIX,
        _translation_list_cache_key,
    )
    from apps.cache_orchestrator.cache_ops import delete_patterns

    try:
        source_key = instance.source.key
    except TranslationSource.DoesNotExist:
        source_key = ""

    # Every combination that could contain this entry: the unfiltered list,
    # the language-only filter, the key-only filter, and the exact
    # lang+key pair — plus a wildcard sweep as a safety net for any other
    # cache backend key layout.
    keys_to_delete = {
        _translation_list_cache_key("", ""),
        _translation_list_cache_key(instance.language, ""),
    }
    if source_key:
        keys_to_delete.add(_translation_list_cache_key("", source_key))
        keys_to_delete.add(_translation_list_cache_key(instance.language, source_key))

    from django.core.cache import cache

    # Cache invalidation must never break the save() it's hooked into (same
    # defensive pattern as queue_translation_on_save above) — a Redis blip
    # here should not stop a translation from being written.
    try:
        cache.delete_many(list(keys_to_delete))
    except Exception:  # noqa: BLE001
        logger.warning(
            "invalidate_translation_list_cache_on_save: cache.delete_many failed "
            "(cache backend unavailable?) — entries will still expire via TTL",
            exc_info=True,
        )

    try:
        delete_patterns([f"{TRANSLATION_LIST_CACHE_PREFIX}:*"])
    except Exception:  # noqa: BLE001 — best-effort; explicit deletes above already cover it
        logger.debug(
            "invalidate_translation_list_cache_on_save: delete_patterns failed", exc_info=True
        )
