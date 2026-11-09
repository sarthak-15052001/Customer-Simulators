"""Dynamic ``perAdultBase`` preview for the /villages list & detail APIs.

The Stay Estimate API (apps.pricing.services.stay_estimate) resolves the real
current price for a village by preferring an active *scraped* ``VillageTarif``
row and only falling back to the static ``Village.tarifs`` fixture when no
scrape exists. The catalog list/detail endpoints used to just dump the raw
``tarifs`` fixture, so they could show stale numbers that didn't match what a
real simulation would return.

This module reuses that exact same resolution logic (via
``_resolve_base_tarif``) so ``GET /villages/`` and ``GET /villages/{id}/``
report a live "starting from" price per adult, for a given ``formule`` and
``date`` query param.

Unlike the full Stay Estimate, this is *not* personalised: it does not apply
QF / promo / quinzaine discounts, since the catalog endpoints don't receive a
family payload. It's the same weekly base price the estimate starts from
before those personal discounts are applied.
"""
from __future__ import annotations

from datetime import date

from apps.pricing.services._round import jsround
from apps.pricing.services.calendar import saison_key
from apps.pricing.services.stay_estimate import _resolve_base_tarif

VALID_FORMULES = {"PC", "DP", "LOC"}
DEFAULT_FORMULE = "DP"


def village_to_pricing_dict(village) -> dict:
    """Minimal camelCase dict shape expected by ``_resolve_base_tarif``."""
    return {
        "id": village.id,
        "region": village.region,
        "tarifs": village.tarifs,
        "tarifUnit": getattr(village, "tarif_unit", "week"),
        "qfExc": village.qf_exc,
        "bebeClub": village.bebe_club,
    }


def resolve_formule(raw: str | None) -> str:
    """Normalize/validate a ``?formule=`` query param, defaulting to DP."""
    formule = (raw or DEFAULT_FORMULE).strip().upper()
    return formule if formule in VALID_FORMULES else DEFAULT_FORMULE


def resolve_stay_date(raw: str | None) -> date:
    """Parse a ``?dateDebut=`` query param (YYYY-MM-DD), defaulting to today."""
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return date.today()


DEFAULT_NIGHTS = 7


def resolve_nights(*, date_debut_raw: str | None, date_fin_raw: str | None) -> tuple[date, int]:
    """Derive the pricing (stay_date, nights) window from ``?dateDebut=`` /
    ``?dateFin=`` — the same arrival/departure pair the Stay Estimate API
    already takes (``sejour.dateDebut`` / ``sejour.dateFin`` on the
    frontend), instead of inventing a separate raw nights param.

    - Both present & valid & dateFin > dateDebut: nights = (dateFin -
      dateDebut).days, exactly how ``estimate_sejour_total`` derives
      ``nuits`` from dates.
    - Only ``dateDebut`` present: nights defaults to 7 (unchanged "starting
      from a week" behaviour for callers that don't care about duration).
    - Neither present: today, 7 nights.
    """
    stay_date = date.today()
    if date_debut_raw:
        try:
            stay_date = date.fromisoformat(date_debut_raw)
        except ValueError:
            pass

    nights = DEFAULT_NIGHTS
    if date_fin_raw:
        try:
            end = date.fromisoformat(date_fin_raw)
            diff = (end - stay_date).days
            if diff > 0:
                nights = diff
        except ValueError:
            pass

    return stay_date, nights


def resolve_per_adult_base(
    *,
    village: dict,
    formule: str,
    stay_date: date,
    pricing_rules: dict,
    nights: int = DEFAULT_NIGHTS,
) -> int | None:
    """Per-adult base price ("à partir de") for village/formule/date/nights.

    Walks the stay in 7-night blocks and resolves + sums each block's own
    real weekly price — the same segmenting ``estimate_sejour_total`` (Stay
    Estimate) uses — so a multi-week stay that crosses a season boundary
    prices each week correctly instead of just multiplying one week's price.

    Returns ``None`` when no scraped or fixture tarif covers this
    village/formule/date (e.g. village doesn't offer that formule, or the
    fixture has no price for that season).
    """
    if formule not in VALID_FORMULES:
        return None
    if nights < 1:
        nights = DEFAULT_NIGHTS

    pricing_rules = pricing_rules or {}
    total = 0.0
    cursor = stay_date
    remaining = nights
    resolved_any = False

    while remaining > 0:
        segment_nights = min(7, remaining)
        resolved = _resolve_base_tarif(
            village=village,
            formule=formule,
            stay_date=cursor,
            saison=saison_key(cursor),
            pricing_rules=pricing_rules,
        )
        if resolved is None:
            return None

        base, formula_coef, is_per_night = resolved
        if is_per_night:
            total += base * segment_nights * formula_coef
        elif segment_nights == 7:
            total += base * formula_coef
        else:
            nightly = round(base / 7)
            total += nightly * segment_nights * formula_coef

        resolved_any = True
        cursor = date.fromordinal(cursor.toordinal() + segment_nights)
        remaining -= segment_nights

    if not resolved_any:
        return None

    return jsround(total)


def resolve_per_adult_base_with_fallback(
    *,
    village: dict,
    formule: str,
    stay_date: date,
    pricing_rules: dict,
    available_formules: list[str] | None = None,
    nights: int = DEFAULT_NIGHTS,
) -> tuple[int | None, str | None]:
    """Like ``resolve_per_adult_base`` but never silently returns ``None``
    just because the village doesn't sell the requested/default formule.

    Some villages only sell one formule (e.g. LOC-only seaside villages with
    no PC/DP tarifs). Asking those villages for the default ``DP`` price
    would otherwise always come back ``null``, which reads as "broken" to a
    frontend even though it's technically correct. Instead:

    1. Try the requested ``formule`` first.
    2. If that resolves to nothing, fall back through the village's own
       ``formules`` list (its real catalog order, e.g. ``["PC", "DP"]`` or
       ``["LOC"]``), trying each until one produces a price.
    3. If the village has no ``formules`` list to go by, fall back through
       the fixed ``DP → PC → LOC`` priority order as a last resort.

    Returns ``(perAdultBase, formuleUsed)``. ``formuleUsed`` tells the caller
    which formule the returned price actually belongs to — it may differ
    from the requested ``formule`` when a fallback kicked in, so callers
    (the serializer) should surface it rather than silently relabeling a
    LOC price as if it were DP. Both come back ``(None, None)`` only when
    the village has no usable tarif for *any* formule on that date.
    """
    candidates = [formule]
    for fallback_formule in (available_formules or []) or list(VALID_FORMULES):
        if fallback_formule in VALID_FORMULES and fallback_formule not in candidates:
            candidates.append(fallback_formule)
    # Deterministic last-resort order even if available_formules was empty/None.
    for fallback_formule in ("DP", "PC", "LOC"):
        if fallback_formule not in candidates:
            candidates.append(fallback_formule)

    for candidate in candidates:
        price = resolve_per_adult_base(
            village=village,
            formule=candidate,
            stay_date=stay_date,
            pricing_rules=pricing_rules,
            nights=nights,
        )
        if price is not None:
            return price, candidate

    return None, None