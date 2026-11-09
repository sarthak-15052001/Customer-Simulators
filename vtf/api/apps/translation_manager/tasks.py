"""Celery tasks for the admin-managed translation table.

task_translate_source        -> translate one TranslationSource into every
                                 target language, overwriting the matching
                                 TranslationEntry rows. Fired automatically
                                 by the post_save signal (see signals.py)
                                 whenever a source's text changes, and can
                                 also be queued by hand from the admin.
task_translate_pending       -> periodic sweep (Celery Beat) that catches
                                 anything still pending/failed/stale — a
                                 safety net so nothing is left untranslated
                                 if a single request-time task failed.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone as dj_timezone

logger = logging.getLogger("translation_manager")


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="apps.translation_manager.tasks.task_translate_source",
)
def task_translate_source(self, source_id: int, languages: list[str] | None = None) -> dict:
    """Translate one TranslationSource into `languages`.

    Same-language targets are stored as the source text; other languages use
    the configured LLM.
    """
    from apps.translation_manager.models import TranslationSource, target_languages_for
    from apps.translation_manager.services.llm_client import (
        TranslationLLMError,
        model_name,
        translate_text,
    )

    try:
        source = TranslationSource.objects.get(pk=source_id)
    except TranslationSource.DoesNotExist:
        logger.warning("task_translate_source: source_id=%s no longer exists", source_id)
        return {"ok": False, "error": "source not found"}

    targets = [language.upper() for language in (languages or target_languages_for(source.source_language))]
    results = []

    for language in targets:
        entry, _ = source.translations.get_or_create(language=language)
        if language == source.source_language.upper():
            entry.translated_text = source.source_text
            entry.status = entry.STATUS_TRANSLATED
            entry.model_used = "source"
            entry.source_content_hash = source.content_hash
            entry.error = ""
            entry.translated_at = dj_timezone.now()
            entry.save()
            results.append({"language": language, "status": "copied"})
            logger.info(
                "task_translate_source: source=%s language=%s COPIED", source.key, language
            )
            continue

        try:
            translated = translate_text(source.source_text, language)
            entry.translated_text = translated
            entry.status = entry.STATUS_TRANSLATED
            entry.model_used = model_name()
            entry.source_content_hash = source.content_hash
            entry.error = ""
            entry.translated_at = dj_timezone.now()
            entry.save()
            results.append({"language": language, "status": "translated"})
            logger.info(
                "task_translate_source: source=%s language=%s DONE", source.key, language
            )
        except TranslationLLMError as exc:
            entry.status = entry.STATUS_FAILED
            entry.error = str(exc)
            entry.save(update_fields=["status", "error", "updated_at"])
            results.append({"language": language, "status": "failed", "error": str(exc)})
            logger.warning(
                "task_translate_source: source=%s language=%s FAILED error=%s",
                source.key,
                language,
                exc,
            )

    return {"ok": True, "source": source.key, "results": results}


@shared_task(
    name="apps.translation_manager.tasks.task_translate_pending",
)
def task_translate_pending(batch_size: int = 50, language: str | None = None) -> dict:
    """Periodic/on-demand sweep: translate every entry that is pending,
    failed, or stale (its source text changed since it was last translated).

    `language`, when given, restricts the sweep to entries whose
    TranslationEntry.language matches.
    """
    from django.db.models import F

    from apps.translation_manager.models import TranslationEntry

    stale_or_pending = (
        TranslationEntry.objects.filter(source__is_active=True)
        .exclude(source_content_hash=F("source__content_hash"))
    )
    if language:
        stale_or_pending = stale_or_pending.filter(language=language.upper())

    stale_or_pending = stale_or_pending.select_related("source")[:batch_size]
    source_ids = sorted({entry.source_id for entry in stale_or_pending})

    for source_id in source_ids:
        task_translate_source.delay(source_id, [language.upper()] if language else None)

    logger.info(
        "task_translate_pending: queued %s source(s) language=%s",
        len(source_ids),
        language or "ALL",
    )
    return {"queued_sources": len(source_ids), "language": language or "ALL"}


@shared_task(
    name="apps.translation_manager.tasks.task_sync_translation_sources",
)
def task_sync_translation_sources(translate: bool = False, language: str | None = None) -> dict:
    """Pull every registered catalog model field into
    TranslationSource rows, creating/updating them as needed. Saving a
    changed row fires the post_save signal, which queues its translation —
    so this is the "take all the model fields" entry point."""
    from apps.translation_manager.services.registry import sync_all

    summary = sync_all()
    translate_task_id = ""
    if translate:
        async_result = task_translate_pending.delay(language=language)
        translate_task_id = async_result.id
        summary["translate_task_id"] = translate_task_id

    logger.info(
        "task_sync_translation_sources: created=%s updated=%s unchanged=%s translate_task_id=%s",
        summary["created"],
        summary["updated"],
        summary["unchanged"],
        translate_task_id or "-",
    )
    return summary
