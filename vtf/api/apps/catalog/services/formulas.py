"""Helpers for stay formula metadata."""
from __future__ import annotations

from apps.catalog.models import Formula


FALLBACK_LABELS = {
    "PC": "Pension complète",
    "DP": "Demi-pension",
    "LOC": "Location",
}

FALLBACK_INCLUDES = {
    "PC": "🥗 Inclus en pension complète : Repas buffet + vin à table · Clubs enfants · Animations · Piscine & espace bien-être · Randonnées guidées · Ménage · WIFI",
    "DP": "🥗 Inclus en demi-pension : Petit-déjeuner & dîner buffet + vin à table · Clubs enfants · Animations · Piscine & espace bien-être · Randonnées guidées · Ménage · WIFI",
    "LOC": "🏠 Inclus en location : Hébergement seul · Clubs enfants · Animations · Piscine & espace bien-être · Randonnées guidées · WIFI",
}

LABEL_TO_CODE = {
    "pension complète": "PC",
    "demi-pension": "DP",
    "location": "LOC",
}


def normalize_formula_code(code: str) -> str:
    normalized = (code or "").strip()
    return LABEL_TO_CODE.get(normalized.lower(), normalized.upper())


def formula_label(code: str) -> str:
    normalized = normalize_formula_code(code)
    try:
        label = (
            Formula.objects.filter(code=normalized)
            .values_list("label", flat=True)
            .first()
        )
    except Exception:
        label = None
    return label or FALLBACK_LABELS.get(normalized, code)


def formula_include_text(code: str) -> str:
    normalized = normalize_formula_code(code)
    try:
        include_text = (
            Formula.objects.filter(code=normalized)
            .values_list("include_text", flat=True)
            .first()
        )
    except Exception:
        include_text = None
    return include_text or FALLBACK_INCLUDES.get(normalized, "")


def formula_includes_map(codes: list[str] | tuple[str, ...] | None = None) -> dict[str, str]:
    wanted = [normalize_formula_code(code) for code in (codes or []) if code]
    try:
        qs = Formula.objects.all()
        if wanted:
            qs = qs.filter(code__in=wanted)
        rows = {row.code: row.include_text for row in qs}
    except Exception:
        rows = {}
    ordered_codes = wanted or list(rows.keys())
    return {
        code: rows.get(code) or FALLBACK_INCLUDES.get(code, "")
        for code in ordered_codes
        if rows.get(code) or FALLBACK_INCLUDES.get(code)
    }
