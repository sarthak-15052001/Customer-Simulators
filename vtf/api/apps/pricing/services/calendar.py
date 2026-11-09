"""Calendar / season helpers.

Port of vtf/front/src/utils/stayTab.ts (date helpers, ouverture parser, season idx).

diff_nuits, date_to_saison_idx, and saison_key are canonical in common/utils.py.
They are re-exported here so existing callers keep working unchanged.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Literal

from common.utils import (
    date_to_saison_idx,
    diff_nuits,
    saison_key_from_date as saison_key,
)

SaisonKey = Literal["hs", "vs", "ete", "fetes"]
SAISON_KEYS: list[SaisonKey] = ["hs", "vs", "ete", "fetes"]


_PLAGE_RE = re.compile(
    r"([0-9]{1,2})/([0-9]{1,2})(?:/([0-9]{2}))?[–\-]([0-9]{1,2})/([0-9]{1,2})(?:/([0-9]{2}))?"
)
_PAREN_RE = re.compile(r"\(([^)]*)\)")
# Detects an exclusion clause inside parens, e.g. "(sf 4/07–15/08)" or
# "(sauf 4/07-15/08)" — the date ranges that follow are *closed* periods.
_SAUF_RE = re.compile(r"^\s*s(?:f|auf)\b", re.IGNORECASE)


# def _parse_ranges(s: str) -> list[tuple[int, int]]:
#     out: list[tuple[int, int]] = []
#     for m in _PLAGE_RE.finditer(s):
#         d1j, d1m, d1y_raw = int(m[1]), int(m[2]), int(m[3]) if m[3] else None
#         d2j, d2m, d2y_raw = int(m[4]), int(m[5]), int(m[6]) if m[6] else None
#         # Choose an appropriate year for ranges that omit the year.
#         # If the range's end (month/day) is before today, assume the next calendar year,
#         # otherwise use the current year. This avoids hardcoding a fixed year like 2026.
#         if d2y_raw:
#             y2 = 2000 + d2y_raw
#         else:
#             today = date.today()
#             # If end month/day is earlier in the calendar than today, assign next year
#             if (d2m, d2j) < (today.month, today.day):
#                 y2 = today.year + 1
#             else:
#                 y2 = today.year
#         if d1y_raw:
#             y1 = 2000 + d1y_raw
#         elif d1m > d2m or (d1m == d2m and d1j > d2j):
#             y1 = y2 - 1
#         else:
#             y1 = y2
#         out.append((y1 * 10000 + d1m * 100 + d1j, y2 * 10000 + d2m * 100 + d2j))
#     return out


def _parse_ranges(s: str, ref_date: date | None = None) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for m in _PLAGE_RE.finditer(s):
        d1j, d1m, d1y_raw = int(m[1]), int(m[2]), int(m[3]) if m[3] else None
        d2j, d2m, d2y_raw = int(m[4]), int(m[5]), int(m[6]) if m[6] else None
        # Choose an appropriate year for ranges that omit the year.
        if d1y_raw and d2y_raw:
            y1, y2 = 2000 + d1y_raw, 2000 + d2y_raw
        elif d1y_raw and not d2y_raw:
            # Start year is known; derive the end year relative to it so
            # ranges crossing New Year's (e.g. "20/12/25–11/04") resolve to
            # the following year, not whatever year happens to be "today".
            y1 = 2000 + d1y_raw
            y2 = y1 + 1 if (d2m, d2j) < (d1m, d1j) else y1
        elif d2y_raw and not d1y_raw:
            y2 = 2000 + d2y_raw
            y1 = y2 - 1 if (d1m, d1j) > (d2m, d2j) else y2
        else:
            # Neither year given — anchor off the provided reference date
            # (typically the queried `openOn`), falling back to today.
            # If the range's end (month/day) is before the reference date,
            # assume the next calendar year, otherwise use the reference year.
            today = ref_date if ref_date is not None else date.today()
            if (d2m, d2j) < (today.month, today.day):
                y2 = today.year + 1
            else:
                y2 = today.year
            y1 = y2 - 1 if (d1m, d1j) > (d2m, d2j) else y2
        out.append((y1 * 10000 + d1m * 100 + d1j, y2 * 10000 + d2m * 100 + d2j))
    return out


def parse_ouverture(s: str | None, ref_date: date | None = None) -> tuple[list[tuple[int, int]], list[tuple[int, int]]] | None:
    """Return (open_ranges, closed_ranges) or None when no usable info.

    Each range is `(abs_start, abs_end)` where `abs = year*10000 + month*100 + day`.
    Parenthesised clauses prefixed with "sf" / "sauf" become *closed* ranges;
    other parenthesised clauses fall back to additional *open* ranges (this
    matches the TS source's intent of treating "(20/12–18/04/26)" as the only
    open window in strings like "Hiver uniquement (20/12–18/04/26)").
    """
    if not s or "confirmer" in s:
        return None
    s = re.sub(r"[A-Za-zÀ-ÿ]+\s+(?:LOC|PC|DP)[/A-Za-z]*", "", s)

    closed: list[tuple[int, int]] = []
    extra_open: list[tuple[int, int]] = []
    for m in _PAREN_RE.finditer(s):
        inner = m.group(1)
        ranges = _parse_ranges(inner, ref_date=ref_date)
        if not ranges:
            continue
        if _SAUF_RE.search(inner):
            closed.extend(ranges)
        else:
            extra_open.extend(ranges)

    base = re.sub(_PAREN_RE, "", s)
    open_ranges = _parse_ranges(base, ref_date=ref_date) + extra_open
    if not open_ranges and not closed:
        return None
    return open_ranges, closed


def is_village_ouvert(ouverture: str | None, d: date | None) -> bool:
    """True when village is open at date d. Defaults to True if ouverture unknown.

    A date inside any *open* range AND outside every *closed* range is open.
    Empty open list means "no info" → permissive (True).
    """
    if not ouverture or not d:
        return True
    # Parse ouverture anchored to the queried date `d` so year inference
    # matches the caller's intent (e.g. openOn=2026-12-05).
    parsed = parse_ouverture(ouverture, ref_date=d)
    if parsed is None:
        return True
    open_ranges, closed_ranges = parsed
    djj = d.year * 10000 + d.month * 100 + d.day
    in_open = not open_ranges or any(start <= djj < end for start, end in open_ranges)
    in_closed = any(start <= djj < end for start, end in closed_ranges)
    return in_open and not in_closed


_FR_DAYS = ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."]
_FR_MONTHS = [
    "", "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
]


def _day_label(d: date) -> str:
    """French abbreviated label e.g. 'Dim. 5 juil.' — spec §US-2.7."""
    day_name = _FR_DAYS[d.weekday()]
    month_name = _FR_MONTHS[d.month]
    return f"{day_name} {d.day} {month_name}"


def get_stay_days(date_debut: date | None, date_fin: date | None) -> list[dict]:
    """List of {key, label, date} for each night of the stay.

    Spec §US-2.7: returns exactly nuits days (date_fin excluded, not included).
    Labels use French abbreviated names: 'Dim. 5 juil.', 'Lun. 6 juil.', etc.
    """
    if not date_debut or not date_fin or date_fin <= date_debut:
        return []
    out: list[dict] = []
    cur = date_debut
    while cur < date_fin and len(out) <= 31:
        out.append({"key": cur.isoformat(), "label": _day_label(cur), "date": cur})
        cur += timedelta(days=1)
    return out
