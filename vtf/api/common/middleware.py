from __future__ import annotations

import json
import logging
import time
from typing import Any

from common.utils import get_client_ip as _client_ip
from django.http import RawPostDataException


logger = logging.getLogger("common.api")
MAX_LOG_VALUE_LENGTH = 1000


class ApiRequestLoggingMiddleware:
    """Write one structured log line for every public API request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        is_api_request = request.path.startswith(
            ("/api/v1/", "/api/v2/", "/api/v3/", "/api/v4/", "/api/v5/")
        )
        request_data = _request_data(request) if is_api_request else "{}"
        response = self.get_response(request)

        if is_api_request:
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.info(
                "api_request method=%s path=%s endpoint=%s api_version=%s tag=%s "
                "status_code=%s duration_ms=%s ip=%s query_params=%s request_data=%s",
                request.method,
                request.get_full_path(),
                _endpoint_name(request),
                _api_version(request.path),
                _api_tag(request.path),
                getattr(response, "status_code", ""),
                duration_ms,
                _client_ip(request),
                _compact_json(dict(request.GET.lists())),
                request_data,
            )

        return response


class ApiResponseTranslationMiddleware:
    """Translate v1 JSON API response bodies when a supported language is requested."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        language = _requested_language(request)
        should_translate = bool(language) and _should_translate_response(request, response)
        if request.path.startswith("/api/v1/") and language:
            logger.info(
                "api_response_translation_check path=%s language=%s should_translate=%s has_data=%s status_code=%s",
                request.path,
                language,
                should_translate,
                hasattr(response, "data"),
                getattr(response, "status_code", ""),
            )
        if not should_translate:
            return response

        try:
            from apps.catalog.services.translations import translate_response_payload

            original_data = response.data
            translated_data = translate_response_payload(response.data, language)

            if translated_data is not original_data:
                # Only mutate + re-render when translation actually changed
                # something — avoids an unnecessary render cycle for FR
                # requests or LLM-disabled runs that return the same object.
                response.data = translated_data
                response._is_rendered = False
                if hasattr(response, "_container"):
                    del response._container
                response["Content-Language"] = language.lower()
                if getattr(response, "accepted_renderer", None) is None:
                    from rest_framework.renderers import JSONRenderer

                    response.accepted_renderer = JSONRenderer()
                    response.accepted_media_type = "application/json"
                    response.renderer_context = {}
                response.render()


            logger.info(
                "api_response_translation_done path=%s language=%s changed=%s",
                request.path,
                language,
                translated_data is not original_data,
            )
        except Exception:
            # translate_response_payload is designed never to raise, so this
            # handler is a last-resort safety net (e.g. an import error or an
            # unhandled render failure).  Restore the original rendered state
            # so the request still returns a valid FR response.
            logger.exception(
                "api_response_translation_failed_unexpected path=%s language=%s",
                request.path,
                language,
            )
            # If data was swapped before the failure, put it back.
            try:
                response.data = original_data  # type: ignore[possibly-undefined]
            except Exception:
                pass
            # Ensure the response is always in a renderable state.
            if not getattr(response, "_is_rendered", True):
                try:
                    response.render()
                except Exception:
                    pass
        return response




def _endpoint_name(request) -> str:
    match = getattr(request, "resolver_match", None)
    return getattr(match, "view_name", None) or ""


def _api_version(path: str) -> str:
    if path.startswith("/api/v5/"):
        return "V5"
    if path.startswith("/api/v4/"):
        return "V4"
    if path.startswith("/api/v3/"):
        return "V3"
    if path.startswith("/api/v2/"):
        return "V2"
    if path.startswith("/api/v1/"):
        return "V1"
    return ""


def _api_tag(path: str) -> str:
    if path.startswith("/api/v5/admin/header-scraper/") or path.startswith(
        "/api/v5/header-banner"
    ):
        return "header_scraper"
    if path.startswith("/api/v4/tariff-scraper/") or path.startswith(
        "/api/v4/admin/tariff-scraper/"
    ):
        return "tariff_scraper"
    if path.startswith("/api/v3/admin/cache/"):
        return "cache_orchestrator"
    if path.startswith("/api/v2/"):
        return "recommender"
    if path.startswith("/api/v1/loggers"):
        return "loggers"
    if path.startswith("/api/v1/mailer/"):
        return "mailer"
    if path.startswith("/api/v1/simulations/pdf"):
        return "PDF"
    pricing_prefixes = (
        "/api/v1/estimate/",
        "/api/v1/transport/",
        "/api/v1/family/",
        "/api/v1/resto/",
        "/api/v1/promos/available",
        "/api/v1/stay/",
        "/api/v1/exports/",
        "/api/v1/go/",
        "/api/v1/signals",
        "/api/v1/interactions",
    )
    if path.startswith(pricing_prefixes) or (
        path.startswith("/api/v1/villages/") and path.endswith("/booking-link")
    ):
        return "Pricing"
    return "catalog"


def _requested_language(request) -> str:
    raw = (
        request.GET.get("language")
        or request.GET.get("lang")
        or request.headers.get("X-Language")
        or ""
    )

    if not raw:
        return ""
    first = raw.split(",", 1)[0].strip().lower().replace("_", "-")
    aliases = {
        "fr": "FR",
        "fr-fr": "FR",
        "french": "FR",
        "gb": "GB",
        "en": "GB",
        "en-gb": "GB",
        "en-us": "GB",
        "english": "GB",
    }
    language = aliases.get(first, first.upper())
    return language if language in {"FR", "GB"} else ""


def _should_translate_response(request, response) -> bool:
    if not request.path.startswith("/api/v1/"):
        return False

    # Endpoints for which translation is permanently disabled.
    # Rules:
    #   • Prefix match  — covers a path and all its sub-paths.
    #   • Exact match   — used where a prefix would accidentally exclude a
    #                     sibling that DOES need translation (e.g. /season
    #                     must not exclude /seasons).
    _TRANSLATION_EXCLUDED_PREFIXES = (
        "/api/v1/health",           # health probe—no human-readable copy
        "/api/v1/interactions",     # write-only interaction tracking
        "/api/v1/landing/map",      # internal map data (not user-facing text)
        "/api/v1/signals",          # event signal receiver
        "/api/v1/exports/",         # bulk export downloads (CSV/binary)
        "/api/v1/loggers",          # internal log viewer (raw log lines)
        "/api/v1/mailer/",          # email send triggers—not display content
        "/api/v1/simulations/",     # PDF generation—binary/template output
    )
    # Exact-path exclusions (strip trailing slash for normalisation).
    _TRANSLATION_EXCLUDED_EXACT = {
        "/api/v1/season",           # returns {saisonKey, saisonIdx} — codes, not copy
        "/api/v1/stay/days",        # stay duration calculation — date ranges / numbers
    }


    path = request.path
    if path.startswith(_TRANSLATION_EXCLUDED_PREFIXES):
        return False
    if path.rstrip("/") in _TRANSLATION_EXCLUDED_EXACT:
        return False

    if getattr(response, "streaming", False):
        return False
    if not hasattr(response, "data"):
        return False
    return 200 <= getattr(response, "status_code", 500) < 500


def _request_data(request) -> str:

    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return "{}"

    content_type = request.META.get("CONTENT_TYPE", "")
    if "application/json" not in content_type:
        return "{}"

    try:
        payload: Any = json.loads((request.body or b"{}").decode(request.encoding or "utf-8"))
    except (RawPostDataException, TypeError, ValueError, UnicodeDecodeError):
        return "{}"
    return _compact_json(payload)


def _compact_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    if len(encoded) <= MAX_LOG_VALUE_LENGTH:
        return encoded
    return encoded[:MAX_LOG_VALUE_LENGTH] + "...<truncated>"
