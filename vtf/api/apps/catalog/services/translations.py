"""Runtime locale translation through the configured local LLM.

The frontend keeps French as the canonical source. Non-French locales can be
generated through the OpenAI-compatible LM Studio endpoint and are cached, with
the committed frontend locale files used as a resilience fallback.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import hashlib
from copy import deepcopy
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class _StableEncoder(json.JSONEncoder):
    """JSON encoder that handles types DRF serializers emit with
    ``coerce_to_string=False`` — most commonly ``decimal.Decimal`` from
    fields like ``FuelOptionSerializer.costPerKm`` and
    ``PromoSerializer.rate``.  Converting to ``str`` gives a stable,
    hash-safe representation that round-trips cleanly through the LLM
    prompt and the Redis cache key.
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


def _json_dumps(obj: Any, **kwargs: Any) -> str:
    """Wrapper around ``json.dumps`` that uses ``_StableEncoder`` so
    ``Decimal`` values (and any future non-serializable DRF types) never
    crash prompt-building or cache-key generation.
    """
    kwargs.setdefault("cls", _StableEncoder)
    return json.dumps(obj, **kwargs)

SUPPORTED_LANGUAGES = {"FR", "GB"}
LANGUAGE_NAMES = {
    "FR": "French",
    "GB": "English",
}



STATIC_RESPONSE_MESSAGES = {
    "FR": {
        "Activities fetched.": "Activités récupérées.",
        "Animations fetched.": "Animations récupérées.",
        "API is healthy.": "L'API est opérationnelle.",
        "Attractions fetched.": "Attractions récupérées.",
        "Available promos fetched.": "Promotions disponibles récupérées.",
        "Cache status fetched.": "Statut du cache récupéré.",
        "Car cost calculated.": "Coût voiture calculé.",
        "Environments fetched.": "Environnements récupérés.",
        "Estimation impossible for given inputs — check family, dates and formule.": (
            "Estimation impossible avec les données fournies — vérifiez la famille, "
            "les dates et la formule."
        ),
        "Formules fetched.": "Formules récupérées.",
        "Fuels fetched.": "Carburants récupérés.",
        "Header banner": "Bannière d'en-tête",
        "Invalid date filter.": "Filtre de date invalide.",
        "Landing map fetched.": "Carte d'accueil récupérée.",
        "Marketing seasons fetched.": "Saisons marketing récupérées.",
        "Meals fetched.": "Repas récupérés.",
        "No active pricing rules found.": "Aucune règle tarifaire active trouvée.",
        "No header banner published.": "Aucune bannière d'en-tête publiée.",
        "Pricing rules fetched.": "Règles tarifaires récupérées.",
        "Promos fetched.": "Promotions récupérées.",
        "Quotient familial calculated.": "Quotient familial calculé.",
        "Recommendations generated.": "Recommandations générées.",
        "Regions fetched.": "Régions récupérées.",
        "Restaurant total calculated.": "Total restaurant calculé.",
        "Scoring weights fetched.": "Pondérations de score récupérées.",
        "Scoring weights updated.": "Pondérations de score mises à jour.",
        "Season for date fetched.": "Saison pour la date récupérée.",
        "Seasons fetched.": "Saisons récupérées.",
        "Similar villages fetched.": "Villages similaires récupérés.",
        "Stay days generated.": "Jours de séjour générés.",
        "Stay estimate calculated.": "Estimation du séjour calculée.",
        "Train cost calculated.": "Coût train calculé.",
        "Translation payload unavailable.": "Payload de traduction indisponible.",
        "Translations fetched successfully.": "Traductions récupérées avec succès.",
        "Unsupported language.": "Langue non prise en charge.",
        "Village detail fetched.": "Détail du village récupéré.",
        "Village not found.": "Village introuvable.",
        "Village popularity cache fetched.": "Cache de popularité des villages récupéré.",
        "Villages fetched successfully.": "Villages récupérés avec succès.",
    },
    "GB": {
        "Activities fetched.": "Activities fetched.",
        "Animations fetched.": "Animations fetched.",
        "Attractions fetched.": "Attractions fetched.",
        "Formules fetched.": "Formulas fetched.",
        "Fuels fetched.": "Fuels fetched.",
        "Meals fetched.": "Meals fetched.",
        "Promos fetched.": "Promotions fetched.",
        "Regions fetched.": "Regions fetched.",
        "Villages fetched successfully.": "Villages fetched successfully.",
    },
}

STATIC_RESPONSE_TEXT_VALUES = {
    "GB": {
        "Clubs enfants & ados": "Kids and teen clubs",
        "Encadrés par animateurs diplômés · sans supplément": (
            "Supervised by qualified activity leaders · no extra charge"
        ),
        "Animations de journée": "Daytime activities",
        "4 rendez-vous/semaine : balade, activité sportive, ludique ou terroir": (
            "4 sessions per week: walks, sports, games or local discovery"
        ),
        "Animations de soirée": "Evening entertainment",
        "Spectacles, concerts, quiz, soirées à thème · Programme variable": (
            "Shows, concerts, quizzes, themed evenings · program varies"
        ),
        "Randonnées accompagnées": "Guided hikes",
        "Sorties nature encadrées gratuites · niveaux adaptés": (
            "Free supervised nature outings · suitable levels"
        ),
    },
    "FR": {},
}


class TranslationError(RuntimeError):
    """Raised when an LLM response cannot be used as a locale payload."""


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


def _model() -> str:
    return _setting("LMSTUDIO_MODEL", "luth-lfm2-350m")


def _llm_enabled() -> bool:
    return _setting("TRANSLATION_LLM_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )




def _build_response_prompt(source: dict[str, Any], target_language: str) -> str:
    return (
        "Translate this API response object to "
        f"{LANGUAGE_NAMES[target_language]}. Return strict JSON only. "
        "Preserve every key, nesting level, array length, boolean, null, "
        "number, id/code/slug, URL, email, date, currency symbol, placeholder, "
        "HTML tag, product name, and brand name. Translate only human-readable "
        "text values. Do not add explanations.\n"
        f"JSON:\n{_json_dumps(source, ensure_ascii=False, separators=(',', ':'))}"
    )


def _extract_json_object(raw: str) -> dict[str, Any]:
    """Parse the model's JSON output.

    Small local models routinely emit literal control characters (a real
    newline byte instead of the escaped `\\n`) inside string values —
    strictly invalid JSON, but a very common failure mode for tiny LLMs.
    `strict=False` tells Python's json parser to tolerate those instead of
    raising `Invalid control character at: ...`, which otherwise crashes
    an entire batch over a single unescaped newline in one string value.
    """
    try:
        parsed = json.loads(raw, strict=False)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise TranslationError("LLM response did not contain a JSON object.")
    try:
        parsed = json.loads(match.group(0), strict=False)
    except json.JSONDecodeError as exc:
        raise TranslationError(f"LLM response was not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise TranslationError("LLM response JSON was not an object.")
    return parsed


def _shape_matches(source: Any, candidate: Any) -> bool:
    if isinstance(source, dict):
        return (
            isinstance(candidate, dict)
            and set(source.keys()) == set(candidate.keys())
            and all(_shape_matches(source[key], candidate[key]) for key in source)
        )
    if isinstance(source, list):
        return (
            isinstance(candidate, list)
            and len(source) == len(candidate)
            and all(_shape_matches(a, b) for a, b in zip(source, candidate))
        )
    return not isinstance(candidate, (dict, list))


def _apply_static_response_messages(payload: dict[str, Any], language: str) -> dict[str, Any]:
    translated = deepcopy(payload)
    message = translated.get("message")
    if isinstance(message, str):
        translated["message"] = STATIC_RESPONSE_MESSAGES.get(language, {}).get(
            message,
            message,
        )
    return translated


def _apply_static_response_text_values(value: Any, language: str) -> Any:
    translations = STATIC_RESPONSE_TEXT_VALUES.get(language, {})
    if not translations:
        return value
    if isinstance(value, dict):
        return {
            key: _apply_static_response_text_values(sub_value, language)
            for key, sub_value in value.items()
        }
    if isinstance(value, list):
        return [_apply_static_response_text_values(item, language) for item in value]
    if isinstance(value, str):
        return translations.get(value, value)
    return value


_session_lock = threading.Lock()
_session: requests.Session | None = None


def _get_session() -> requests.Session:
    """A shared session that retries only connection-level failures
    (e.g. RemoteDisconnected / ConnectionResetError while the local model
    is still loading or busy). Read timeouts are deliberately NOT retried
    here: a request that already timed out waiting on a slow local CPU
    model will just time out again on retry, and each retry silently
    repeats the full (slow) prompt processing from scratch — see
    `_call_llm` for how read timeouts are surfaced instead.
    """
    global _session
    if _session is not None:
        return _session
    with _session_lock:
        if _session is None:
            session = requests.Session()
            retry = Retry(
                total=_int_setting("TRANSLATION_LLM_MAX_RETRIES", 3),
                connect=_int_setting("TRANSLATION_LLM_MAX_RETRIES", 3),
                read=0,
                backoff_factor=1.5,
                status_forcelist=(502, 503, 504),
                allowed_methods=("POST",),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            _session = session
    return _session


def _call_llm_raw(payload: dict[str, Any], target_language: str, timeout: int) -> dict[str, Any]:
    """POST a single chat-completions request and return the parsed JSON body.

    Raises TranslationError for every failure mode that should trigger the
    file-fallback path: connection refused/dropped, the request timing out,
    or a non-2xx HTTP status.
    """
    session = _get_session()
    try:
        resp = session.post(
            f"{_base_url()}/chat/completions",
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.Timeout as exc:
        # The local model didn't finish (prefill + generation) inside
        # `timeout` seconds. This is the common case on small CPU-bound
        # models with a large prompt — NOT a connection problem, so it
        # must be caught separately from ConnectionError below or it
        # propagates as an unhandled exception and gets misreported as
        # "unexpected" in the logs instead of a clear timeout message.
        raise TranslationError(
            f"LM Studio timed out after {timeout}s for {target_language} "
            "(model likely too slow for this prompt size — see "
            "TRANSLATION_LLM_TIMEOUT_SECONDS)"
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        # Covers urllib3's RemoteDisconnected: the LM Studio/llama-server
        # process isn't running, isn't listening on this port, or closed
        # the socket without sending a response.
        raise TranslationError(
            f"LM Studio connection failed for {target_language}: {exc}"
        ) from exc

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise TranslationError(
            f"LM Studio returned {resp.status_code} for {target_language}: {resp.text[:300]}"
        ) from exc

    return resp.json()


def _best_effort_merge(source: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Return a dict that has every key from *source*, using the translated
    value from *candidate* where the shapes match, and falling back to the
    source value where they don't.

    This prevents a single LLM shape-mismatch from discarding every key in
    a response payload — instead, correctly-shaped translated keys are kept
    and only the malformed ones fall back to the original French value.
    """
    result: dict[str, Any] = {}
    for key, source_val in source.items():
        cand_val = candidate.get(key, source_val)
        if isinstance(source_val, dict) and isinstance(cand_val, dict):
            result[key] = _best_effort_merge(source_val, cand_val)
        elif isinstance(source_val, list) and isinstance(cand_val, list) and len(source_val) == len(cand_val):
            result[key] = cand_val
        elif not isinstance(source_val, (dict, list)) and not isinstance(cand_val, (dict, list)):
            result[key] = cand_val
        else:
            # Shape mismatch for this key — keep the source value
            result[key] = source_val
    return result


def _call_llm_chunk(
    source: dict[str, Any],
    target_language: str,
    *,
    response_payload: bool = True,
) -> dict[str, Any]:
    """Translate one API response JSON object in a single LLM call.

    A shape mismatch on the LLM output is handled via best-effort merging:
    keys whose shapes match are kept translated, keys whose shapes differ
    fall back to the source value.  This prevents the most common small-model
    failure mode (an extra or missing key in a list item) from discarding the
    entire translated response and silently serving French content to a GB user.
    """
    timeout = _int_setting("TRANSLATION_LLM_TIMEOUT_SECONDS", 900)
    data = _call_llm_raw(
        {
            "model": _model(),
            "messages": [
                {
                    "role": "user",
                    "content": _build_response_prompt(source, target_language),
                }
            ],
            "temperature": 0,
            "max_tokens": _int_setting("TRANSLATION_LLM_MAX_TOKENS", 12000),
        },
        target_language,
        timeout,
    )
    content = data["choices"][0]["message"]["content"].strip()
    translated = _extract_json_object(content)
    if not _shape_matches(source, translated):
        logger.debug(
            "translation_llm_response_shape_mismatch language=%s — using best-effort merge",
            target_language,
        )
        return _best_effort_merge(source, translated)
    return translated



def _response_cache_key(language: str, payload: dict[str, Any]) -> str:
    encoded = _json_dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"vtf:api:response-translation:{language}:v1:{digest}"




def response_translation_enabled() -> bool:
    return _llm_enabled() and _setting(
        "TRANSLATION_GLOBAL_RESPONSES_ENABLED", "true"
    ).lower() in ("1", "true", "yes")


def translate_response_payload(payload: Any, language: str) -> Any:
    """Translate one API response payload synchronously, preserving its shape.

    Contract:
    - Always returns a valid dict — never raises.
    - When no language is requested, or language == FR, returns the payload
      with static message/text substitutions applied (which is still French).
    - When GB is requested and the LLM is enabled, attempts live translation
      and caches the result.  On any LLM failure (connection error, timeout,
      shape mismatch, unexpected exception) it falls back silently to the
      static-translated FR payload — the caller gets a valid response in all
      cases.  The error is logged at WARNING so it's visible without causing
      an API error.
    """
    language = language.upper()
    if language not in SUPPORTED_LANGUAGES:
        return payload
    if not isinstance(payload, dict):
        return payload

    payload_with_static_messages = _apply_static_response_messages(payload, language)
    payload_with_static_text = _apply_static_response_text_values(
        payload_with_static_messages,
        language,
    )

    # FR (and no-language-requested) — static substitutions are the full
    # translation; no LLM involvement at all.
    if language == "FR":
        return payload_with_static_text

    # LLM disabled → serve the static-translated payload (still FR for
    # any strings not in STATIC_RESPONSE_TEXT_VALUES, which is fine —
    # French is the canonical language and a graceful fallback).
    if not response_translation_enabled():
        return payload_with_static_text

    cache_key = _response_cache_key(language, payload_with_static_text)
    cached = cache.get(cache_key)
    if cached is not None:
        return deepcopy(cached)

    # Attempt LLM translation.  Any failure at any level is caught here so
    # the function never raises — callers always get a valid dict back.
    try:
        translated = _translate_response_envelope(payload_with_static_text, language)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "api_response_translation_envelope_failed language=%s error=%s "
            "— serving FR fallback",
            language,
            exc,
        )
        return payload_with_static_text

    try:
        cache.set(cache_key, translated, _int_setting("TRANSLATION_CACHE_TTL", 604800))
    except Exception as exc:  # noqa: BLE001
        # Cache write failure is non-fatal — translated payload is still usable.
        logger.warning(
            "api_response_translation_cache_set_failed language=%s error=%s",
            language,
            exc,
        )
    return translated


def _translate_response_envelope(payload: dict[str, Any], language: str) -> dict[str, Any]:
    """Translate a {success, message, data} envelope without ever sending
    the full list-valued ``data`` field as one giant LLM chunk.

    Small local models (<=1B params) reliably fail _shape_matches when the
    prompt contains a list of N objects — they drop items, reorder them, or
    hallucinate extra keys. The fix is to walk the ``data`` value recursively
    so every list of dicts is translated item-by-item, regardless of how deeply
    nested the list is (e.g. ``data`` is a list, or ``data.items`` is a list).

    Non-list scalars (strings, numbers) inside a dict are batched together in
    one small LLM call. Items that individually fail translation are kept as-is
    (French original) rather than failing the whole response.
    """
    data = payload.get("data")
    translated_data = _translate_data_value(data, language)
    return {**payload, "data": translated_data}


def _translate_data_value(value: Any, language: str) -> Any:
    """Recursively translate a JSON value from the API response ``data`` field.

    Strategy:
    - ``list``  → translate each dict item individually; non-dict items pass through.
    - ``dict``  → split into scalar-valued keys (batched in one LLM call) and
                  list/dict-valued keys (recursed into individually).  This avoids
                  sending a large nested payload as one chunk.
    - scalar    → pass through unchanged (strings/numbers are only translated
                  as part of enclosing dict batches, never in isolation).
    """
    if isinstance(value, list):
        translated_items = []
        for item in value:
            if not isinstance(item, dict):
                # scalars / nulls inside a list — pass through
                translated_items.append(item)
                continue
            try:
                translated_items.append(
                    _call_llm_chunk(item, language, response_payload=True)
                )
            except TranslationError as exc:
                logger.warning(
                    "api_response_translation_item_failed language=%s error=%s",
                    language,
                    exc,
                )
                translated_items.append(item)
        return translated_items

    if isinstance(value, dict):
        # Split into scalar leaves (safe to batch) and complex values (recurse)
        scalar_batch: dict[str, Any] = {}
        complex_keys: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                complex_keys[k] = v
            else:
                scalar_batch[k] = v

        result: dict[str, Any] = {}

        # Batch-translate scalar leaves in one LLM call
        if scalar_batch:
            try:
                translated_scalars = _call_llm_chunk(
                    scalar_batch, language, response_payload=True
                )
                result.update(translated_scalars)
            except TranslationError as exc:
                logger.warning(
                    "api_response_translation_dict_scalars_failed language=%s error=%s",
                    language,
                    exc,
                )
                result.update(scalar_batch)

        # Recurse into complex values (lists / nested dicts)
        for k, v in complex_keys.items():
            result[k] = _translate_data_value(v, language)

        return result

    # Scalar at top level — nothing to do
    return value