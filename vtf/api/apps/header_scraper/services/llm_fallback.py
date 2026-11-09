"""LLM fallback for the VTF homepage top announcement banner.

Activated only after the HTTP and Playwright scraper tiers fail. Uses the
same LM Studio settings as the tariff scraper:

  LLM_FALLBACK_ENABLED
  LMSTUDIO_BASE_URL
  LMSTUDIO_MODEL
  LLM_MAX_RETRIES
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from apps.header_scraper.services.parse import parse_banner_html

logger = logging.getLogger("header_scraper")


def _setting(name: str, default: str = "") -> str:
    """Read a Django setting with fallback to env."""
    try:
        from django.conf import settings

        val = getattr(settings, name, None)
        if val is not None:
            return str(val)
    except Exception:
        pass
    return os.environ.get(name, default)


def llm_fallback_enabled() -> bool:
    return _setting("LLM_FALLBACK_ENABLED", "false").lower() in ("true", "1", "yes")


def _base_url() -> str:
    return _setting("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")


def _model() -> str:
    return _setting("LMSTUDIO_MODEL", "luth-lfm2-350m")


def _max_retries() -> int:
    try:
        return int(_setting("LLM_MAX_RETRIES", "2"))
    except (ValueError, TypeError):
        return 2


def _call_lmstudio(prompt: str, temperature: float = 0.0) -> Optional[str]:
    """Call the LM Studio local API and return the response text."""
    import requests

    try:
        resp = requests.post(
            f"{_base_url()}/chat/completions",
            json={
                "model": _model(),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": 384,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("header_scraper LLM call failed: %s", exc)
        return None


def _build_prompt(page_html: str, language: str) -> str:
    excerpt = page_html[:40_000]
    return (
        "Extract only the VTF homepage top announcement banner HTML from this page. "
        "Return strict JSON with exactly one key: banner_html. "
        "Keep the original inline anchor tags and href values. "
        "Do not include navigation, language switcher, phone numbers, menus, hero text, "
        "or explanations. If no top announcement banner is present, return "
        '{"banner_html": ""}.\n'
        f"Language: {language}\n"
        "HTML:\n"
        f"{excerpt}"
    )


def _extract_json_object(response: str) -> dict:
    try:
        data = json.loads(response)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", response)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_banner_html(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def extract_banner_html_with_llm(
    page_html: str,
    language: str,
    *,
    base_url: str,
) -> str:
    """Extract banner HTML with LLM and validate it through the normal parser."""
    if not page_html or not page_html.strip():
        return ""

    prompt = _build_prompt(page_html, language)
    for attempt in range(_max_retries() + 1):
        response = _call_lmstudio(prompt)
        if not response:
            logger.debug("header_scraper LLM attempt %d returned no response", attempt)
            continue

        data = _extract_json_object(response)
        banner_html = _normalize_banner_html(data.get("banner_html"))
        if banner_html and parse_banner_html(banner_html, base_url=base_url):
            return banner_html

        logger.debug("header_scraper LLM attempt %d produced no parseable banner", attempt)

    return ""
