"""Minimal LLM caller for the admin-managed translation table.

Deliberately independent from ``apps.catalog.services.translations`` (the
existing v1 runtime translator) so that file stays untouched. Reuses the
same LM Studio settings already defined in ``config/settings/base.py``
(``LMSTUDIO_BASE_URL``, ``LMSTUDIO_MODEL``, ``TRANSLATION_LLM_*``) — same
model, same endpoint, just a simpler plain-text-in/plain-text-out call
shaped for one source string at a time instead of a whole API payload.
"""
from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger("translation_manager")

LANGUAGE_NAMES = {
    "FR": "French",
    "GB": "English",
}


class TranslationLLMError(RuntimeError):
    """Raised when the LLM call fails or returns something unusable."""


def _setting(name: str, default: str = "") -> str:
    val = getattr(settings, name, None)
    return str(val) if val is not None else default


def _int_setting(name: str, default: int) -> int:
    try:
        return int(_setting(name, str(default)))
    except (TypeError, ValueError):
        return default


def _base_url() -> str:
    return _setting("LMSTUDIO_BASE_URL", "http://localhost:1234/v1").rstrip("/")


def model_name() -> str:
    return _setting("LMSTUDIO_MODEL", "luth-lfm2-350m")


def llm_enabled() -> bool:
    return _setting("TRANSLATION_LLM_ENABLED", "false").lower() in ("1", "true", "yes")


def translate_text(source_text: str, target_language: str) -> str:
    """Translate one plain-text string via the configured LLM.

    Raises ``TranslationLLMError`` on any failure (connection, timeout,
    non-2xx, empty response) — callers decide how to record that as a
    ``TranslationEntry.status = failed`` row.
    """
    target_language = target_language.upper()
    if target_language not in LANGUAGE_NAMES:
        raise TranslationLLMError(f"Unsupported target language: {target_language}")
    if not llm_enabled():
        raise TranslationLLMError("TRANSLATION_LLM_ENABLED is off.")

    timeout = _int_setting("TRANSLATION_LLM_TIMEOUT_SECONDS", 900)
    prompt = (
        f"Translate the following text to {LANGUAGE_NAMES[target_language]}. "
        "Return only the translated text, with no quotes, no explanations, "
        "and no surrounding commentary.\n\n"
        f"TEXT:\n{source_text}"
    )

    try:
        resp = requests.post(
            f"{_base_url()}/chat/completions",
            json={
                "model": model_name(),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": _int_setting("TRANSLATION_LLM_MAX_TOKENS", 4000),
            },
            timeout=timeout,
        )
    except requests.exceptions.Timeout as exc:
        raise TranslationLLMError(
            f"LM Studio timed out after {timeout}s for {target_language}"
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise TranslationLLMError(
            f"LM Studio connection failed for {target_language}: {exc}"
        ) from exc

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise TranslationLLMError(
            f"LM Studio returned {resp.status_code} for {target_language}: {resp.text[:300]}"
        ) from exc

    try:
        content = resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        raise TranslationLLMError(f"Unexpected LM Studio response shape: {exc}") from exc

    if not content:
        raise TranslationLLMError("LM Studio returned an empty translation.")
    return content
