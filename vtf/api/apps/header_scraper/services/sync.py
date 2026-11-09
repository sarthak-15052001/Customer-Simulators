"""Persist scraped header banners (hash-skip + snapshot history)."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable, Optional

from django.db import transaction
from django.utils import timezone

from apps.header_scraper.models import HeaderBanner, HeaderBannerSnapshot
from apps.header_scraper.services.parse import parse_banner_html, segments_to_plain_text
from apps.header_scraper.services.scrape import (
    LANGUAGE_URLS,
    scrape_header_banner_html,
)

logger = logging.getLogger("header_scraper")

SNAPSHOT_KEEP = 50
SCRAPE_LANGUAGES = ("FR", "GB")


def normalize_api_language(lang: str | None) -> str:
    """Map simulator langs to stored banner rows: ES/NL → FR, EN → GB."""
    value = (lang or "FR").upper().strip()
    if value in ("GB", "EN"):
        return "GB"
    return "FR"


def content_hash_for_segments(segments: list[dict[str, Any]]) -> str:
    payload = json.dumps(segments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _trim_snapshots(language: str) -> None:
    ids = list(
        HeaderBannerSnapshot.objects.filter(language=language)
        .order_by("-scraped_at")
        .values_list("id", flat=True)[SNAPSHOT_KEEP:]
    )
    if ids:
        HeaderBannerSnapshot.objects.filter(id__in=ids).delete()


def sync_language(
    language: str,
    *,
    scrape_fn: Optional[Callable[[str], Any]] = None,
) -> dict[str, Any]:
    """Scrape one language and publish if content changed.

    On fetch/parse failure the previously published ``HeaderBanner`` is kept.
    """
    language = language.upper()
    if language not in LANGUAGE_URLS:
        return {
            "language": language,
            "status": HeaderBannerSnapshot.STATUS_FETCH_FAILED,
            "error": f"Unsupported language '{language}'",
        }

    scrape = scrape_fn or scrape_header_banner_html
    result = scrape(language)

    if not getattr(result, "ok", False):
        error = getattr(result, "error", "Unknown scrape error") or "Unknown scrape error"
        fail_url = getattr(result, "source_url", "") or LANGUAGE_URLS[language]
        HeaderBannerSnapshot.objects.create(
            language=language,
            status=HeaderBannerSnapshot.STATUS_FETCH_FAILED,
            source_url=fail_url,
            error=error,
        )
        _trim_snapshots(language)
        logger.warning("header_scraper fetch_failed language=%s error=%s", language, error)
        return {
            "language": language,
            "status": HeaderBannerSnapshot.STATUS_FETCH_FAILED,
            "source_url": fail_url,
            "error": error,
        }

    source_url = result.source_url or LANGUAGE_URLS[language]
    segments = parse_banner_html(result.banner_html, base_url=source_url)
    if not segments:
        error = (
            "Step 4 (Parse) | sync.py → sync_language() | "
            "Parsed zero segments from banner HTML."
        )
        HeaderBannerSnapshot.objects.create(
            language=language,
            status=HeaderBannerSnapshot.STATUS_PARSE_FAILED,
            source_url=source_url,
            error=error,
        )
        _trim_snapshots(language)
        logger.warning("header_scraper parse_failed language=%s", language)
        return {
            "language": language,
            "status": HeaderBannerSnapshot.STATUS_PARSE_FAILED,
            "source_url": source_url,
            "error": error,
        }

    digest = content_hash_for_segments(segments)
    plain = segments_to_plain_text(segments)
    existing = HeaderBanner.objects.filter(language=language).first()

    if existing and existing.content_hash == digest and existing.is_active:
        HeaderBannerSnapshot.objects.create(
            language=language,
            status=HeaderBannerSnapshot.STATUS_UNCHANGED,
            content_hash=digest,
            plain_text=plain,
            segments=segments,
            source_url=source_url,
        )
        _trim_snapshots(language)
        return {
            "language": language,
            "status": HeaderBannerSnapshot.STATUS_UNCHANGED,
            "source_url": source_url,
            "content_hash": digest,
            "plain_text": plain,
        }

    now = timezone.now()
    with transaction.atomic():
        banner, _created = HeaderBanner.objects.update_or_create(
            language=language,
            defaults={
                "segments": segments,
                "plain_text": plain,
                "source_url": source_url,
                "content_hash": digest,
                "is_active": True,
                "scraped_at": now,
            },
        )
        HeaderBannerSnapshot.objects.create(
            language=language,
            status=HeaderBannerSnapshot.STATUS_SUCCESS,
            content_hash=digest,
            plain_text=plain,
            segments=segments,
            source_url=source_url,
        )
    _trim_snapshots(language)
    logger.info(
        "header_scraper published language=%s hash=%s chars=%d",
        language,
        digest[:12],
        len(plain),
    )
    return {
        "language": language,
        "status": HeaderBannerSnapshot.STATUS_SUCCESS,
        "source_url": source_url,
        "content_hash": digest,
        "plain_text": plain,
        "banner_id": banner.id,
    }


def sync_all_languages(
    *,
    scrape_fn: Optional[Callable[[str], Any]] = None,
    languages: tuple[str, ...] = SCRAPE_LANGUAGES,
) -> dict[str, Any]:
    """Scrape FR + GB (or a subset) and return per-language summaries."""
    results = [sync_language(lang, scrape_fn=scrape_fn) for lang in languages]
    return {
        "results": results,
        "ok": all(
            r.get("status")
            in (
                HeaderBannerSnapshot.STATUS_SUCCESS,
                HeaderBannerSnapshot.STATUS_UNCHANGED,
            )
            for r in results
        ),
    }
