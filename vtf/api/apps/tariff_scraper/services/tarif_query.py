"""Tarif query helpers — read active VillageTarif rows.

The pricing engine (stay_estimate.py) calls get_active_tarif() instead of
reading from Village.tarifs JSONField when a matching scraped band exists.

Fallback: if no VillageTarif row exists for a village+formule+date,
the caller falls back to Village.tarifs (the old static fixture).

Safety note: PC/DP adult lookups explicitly filter to adult-only rows to avoid
accidentally returning a child age-group price. Child VillageTarif rows
(unit_type like "6 à - 11 ans") are exposed through the child-specific helpers.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from apps.tariff_scraper.models import PRICING_TYPE_PER_PERSON, VillageTarif
from apps.tariff_scraper.services.scraper import _is_adult_column_header, _is_child_column_header


def _active_row(
    village_id: str,
    formule: str,
    stay_date: date,
    unit_type: str = "",
) -> Optional[VillageTarif]:
    qs = VillageTarif.objects.filter(
        village_id=village_id,
        formule=formule,
        is_active=True,
        date_start__lte=stay_date,
        date_end__gt=stay_date,
    )

    if formule == "LOC" and unit_type:
        qs = qs.filter(unit_type=unit_type)

    if formule == "LOC" and not unit_type:
        # Prefer lowest unit price when the estimate has no room type.
        return qs.order_by("price", "-effective_at").first()

    # PC/DP: filter to adult-only rows to avoid child age-group prices.
    # unit_type="" is legacy adult; anything else is matched with the same
    # predicate the scraper uses to *write* unit_type (_is_adult_column_header),
    # so headers like "Adultes (16 ans et +)" / "Adulte" / "Adults" — which
    # the scraper already accepts and counts into the season buckets — are
    # not silently invisible to the pricing engine. The old exact/iexact
    # "adultes" check was stricter than the writer and dropped those rows,
    # causing a silent fallback to fixture pricing.
    if formule in ("PC", "DP"):
        candidates = [
            row for row in qs.order_by("-date_start", "-effective_at")
            if row.unit_type == "" or _is_adult_column_header(row.unit_type)
        ]
        return candidates[0] if candidates else None

    return qs.order_by("-date_start", "-effective_at").first()


def _child_age_matches_unit_type(age: int, unit_type: str) -> bool:
    """Return True when a scraped child age-band label covers ``age``."""
    import re
    import unicodedata

    if age < 0 or not _is_child_column_header(unit_type):
        return False

    label = unicodedata.normalize("NFKD", unit_type.lower())
    label = "".join(ch for ch in label if not unicodedata.combining(ch))

    under = re.search(r"^(?:[<≤]\s*|-+\s*|moins\s+de\s+)(\d+)\s*ans?\b", label)
    if under:
        return age < int(under.group(1))

    between = re.search(r"(\d+)\s*([–\-a])\s*-?\s*(\d+)\s*ans?\b", label)
    if not between:
        return False

    start = int(between.group(1))
    end = int(between.group(3))
    if start > end:
        start, end = end, start

    # VTF commonly writes "11 à - 16 ans" to mean from 11 up to under 16.
    # Plain hyphen ranges like "2-5 ans" are treated as inclusive.
    if between.group(2) == "a":
        return start <= age < end
    return start <= age <= end


def _active_child_row(
    village_id: str,
    formule: str,
    stay_date: date,
    age: int,
) -> Optional[VillageTarif]:
    qs = VillageTarif.objects.filter(
        village_id=village_id,
        formule=formule,
        is_active=True,
        date_start__lte=stay_date,
        date_end__gt=stay_date,
    )
    candidates = [
        row for row in qs.order_by("-date_start", "-effective_at")
        if _child_age_matches_unit_type(age, row.unit_type or "")
    ]
    return candidates[0] if candidates else None


def get_active_tarif(
    village_id: str,
    formule: str,
    stay_date: date,
    unit_type: str = "",
) -> Optional[Decimal]:
    """Return the active scraped price for village / formule on a given date.

    For PC / DP: returns the per-adult price — weekly *unless* the village's
    pricing_type is per_person_per_night (à la carte villages, e.g.
    Talloires), in which case it's a nightly rate. Callers that need to know
    which one they got should use ``get_active_tarif_with_type`` instead.
    For LOC:     returns the flat weekly unit rate.
                 When ``unit_type`` is blank, returns the cheapest matching
                 LOC band (estimate "à partir de" when room type is unknown).

    Returns None if no active tarif row covers the date — caller should
    fall back to the legacy Village.tarifs JSONField in that case.
    """
    row = _active_row(village_id, formule, stay_date, unit_type)
    return row.price if row else None


def get_active_tarif_with_type(
    village_id: str,
    formule: str,
    stay_date: date,
    unit_type: str = "",
) -> Optional[tuple[Decimal, str]]:
    """Like ``get_active_tarif`` but also returns the row's ``pricing_type``.

    The pricing engine needs this to know whether the returned PC/DP price is
    a weekly price (``per_person``) or a nightly price
    (``per_person_per_night``, e.g. Talloires) before multiplying it into a
    stay total — see stay_estimate.py's segment-summation loop.

    Returns None if no active tarif row covers the date.
    """
    row = _active_row(village_id, formule, stay_date, unit_type)
    if row is None:
        return None
    return row.price, row.pricing_type or PRICING_TYPE_PER_PERSON


def get_active_child_tarif_with_type(
    village_id: str,
    formule: str,
    stay_date: date,
    age: int,
) -> Optional[tuple[Decimal, str]]:
    """Return the active scraped child age-band price covering ``age``.

    Returns None when the village/date/formule has no specific child age-band
    row, so callers can fall back to the legacy child-discount calculation.
    """
    row = _active_child_row(village_id, formule, stay_date, age)
    if row is None:
        return None
    return row.price, row.pricing_type or PRICING_TYPE_PER_PERSON


def get_all_active_tarifs(village_id: str) -> list[dict]:
    """Return all active tarif rows for a village, ordered by formule + date_start.

    Useful for the GET /tariffs/{village_id}/ API endpoint.
    """
    return list(
        VillageTarif.objects.filter(
            village_id=village_id,
            is_active=True,
        )
        .order_by("formule", "date_start", "unit_type")
        .values(
            "id",
            "formule",
            "date_start",
            "date_end",
            "pricing_type",
            "unit_type",
            "price",
            "effective_at",
            "source_snapshot_id",
        )
    )
