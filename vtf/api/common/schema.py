from __future__ import annotations

from typing import Any

# Paths excluded from response translation — must stay in sync with
# _should_translate_response() in common/middleware.py.
_LANGUAGE_EXCLUDED_PREFIXES = (
    "/api/v1/health",
    "/api/v1/interactions",
    "/api/v1/landing/map",
    "/api/v1/signals",
    "/api/v1/exports/",
    "/api/v1/loggers",
    "/api/v1/mailer/",
    "/api/v1/simulations/",
)
# Exact-path exclusions (OpenAPI paths have no trailing slash in most cases,
# so we strip it for the comparison just as the middleware does).
_LANGUAGE_EXCLUDED_EXACT = {
    "/api/v1/season",
    "/api/v1/stay/days",
}



def _is_translation_excluded(path: str) -> bool:
    """Return True if this OpenAPI path must NOT receive the language parameter."""
    if path.startswith(_LANGUAGE_EXCLUDED_PREFIXES):
        return True
    if path.rstrip("/") in _LANGUAGE_EXCLUDED_EXACT:
        return True
    return False


def add_global_language_parameter(
    result: dict[str, Any],
    generator,
    request,
    public: bool,
) -> dict[str, Any]:
    """Expose the response-translation language selector in Swagger UI.

    The parameter is injected into every /api/v1/ endpoint **except** the
    ones listed in _LANGUAGE_EXCLUDED_PREFIXES / _LANGUAGE_EXCLUDED_EXACT,
    which mirror the exclusions in ApiResponseTranslationMiddleware.
    """
    language_parameter = {
        "name": "language",
        "in": "query",
        "required": False,
        "schema": {
            "type": "string",
            "enum": ["FR", "GB"],
        },
        "description": "Optional response translation language.",
    }

    for path, path_item in result.get("paths", {}).items():
        if not path.startswith("/api/v1/"):
            continue
        if _is_translation_excluded(path):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            parameters = operation.setdefault("parameters", [])
            if any(
                param.get("name") == "language" and param.get("in") == "query"
                for param in parameters
            ):
                continue
            parameters.append(dict(language_parameter))
    return result

