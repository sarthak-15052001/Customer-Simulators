"""Marketing season helpers — dynamic year-rolling for season dates.

Marketing season rows (whether freshly loaded from the fixture, or sitting
untouched in the DB from a previous year) store a start/end window. This
module is the single place that turns "whatever is in the DB right now"
into "the correct dates for the next real occurrence of this season",
without ever needing the fixture or the DB row itself to be rewritten.

Why this matters: previously this exact algorithm was copy-pasted in three
places (apps/catalog/views.py, apps/cache_orchestrator/service.py, and
partially in apps/pricing/services/stay_estimate.py) and had already begun
to drift — see the docstring on stay_estimate's usage for a bug this drift
caused. Both apps/catalog/views.py and apps/cache_orchestrator/service.py
now call `marketing_seasons_payload()` below, so there is one algorithm
and one cache-shape, no matter which code path builds the response.

This module works correctly even if `load_vtf_mocks` / `loaddata` has
never been run against the *current* year's rows — every call recomputes
the real-world window from whatever start_date/end_date currently sit on
the row, on every call, with no dependency on a fixture reload having
happened recently.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.catalog.models import MarketingSeasons


def _next_weekend_within(start_d: date, end_d: date, after: date) -> tuple[date, date]:
    """Return (saturday, sunday) where saturday is the first Saturday >= max(after, start_d)
    and both days are within [start_d, end_d]. If no Saturday fits, fall back to the
    start of the window.
    """
    cur = max(after, start_d)
    for i in range(0, 366):
        cand = cur + timedelta(days=i)
        if cand.weekday() == 5 and cand <= end_d:
            sat = cand
            sun = sat + timedelta(days=1)
            if sun > end_d:
                sun = end_d
            return sat, sun
    sat = start_d
    sun = min(start_d + timedelta(days=1), end_d)
    return sat, sun


def roll_season_dates_to_current_year(
    anchor_start: date,
    anchor_end: date,
    today: date | None = None,
) -> tuple[date, date, date]:
    """Roll a season's stored start/end dates forward to the next real occurrence.

    Works regardless of what year is currently on the row — whether it's
    the fixture's anchor year (e.g. 2000), a year that's already correct,
    or a year that's gone stale because nobody re-ran load_vtf_mocks.

    Args:
        anchor_start: the season's start date, whatever year it currently has.
        anchor_end: the season's end date. For winter this is one calendar
            year ahead of anchor_start (e.g. ...-12-01 -> ...+1-02-28).
        today: defaults to date.today(); injectable for tests.

    Returns:
        (start_date, end_date, default_date) — start_date/end_date are the
        season window shifted to whole years so that end_date >= today;
        default_date is the next Saturday inside that window (the
        marketing "book this weekend" default).
    """
    if today is None:
        today = date.today()

    year_offset = today.year - anchor_end.year
    cand_start = anchor_start.replace(year=anchor_start.year + year_offset)
    cand_end = anchor_end.replace(year=anchor_end.year + year_offset)

    if cand_end < today:
        cand_start = cand_start.replace(year=cand_start.year + 1)
        cand_end = cand_end.replace(year=cand_end.year + 1)

    default_sat, _ = _next_weekend_within(cand_start, cand_end, today)

    return cand_start, cand_end, default_sat


def marketing_seasons_payload(today: date | None = None) -> dict:
    """Build the `{"items": [...]}` payload for the marketing-seasons endpoint.

    Reads MarketingSeasons rows fresh from the DB and rolls each one's
    dates to the current real-world year on the fly. Safe to call:
    - right after a fresh `load_vtf_mocks` run (rows already current-year)
    - a year later, with nobody having reseeded (rows still stale anchor
      dates) — this still produces correct output either way
    - from any caller: the live API view, the cache-warming job, or a
      future management command — all get the same shape and the same
      dates, because this is the only place that does the math.

    This is intentionally imported lazily (Django models, inside the
    function) so this module has no hard Django import at module load
    time, keeping it cheap to unit test the pure date math above.
    """
    from apps.catalog.models import MarketingSeasons
    from apps.catalog.serializers import MarketingSeasonsSerializer

    if today is None:
        today = date.today()

    items = MarketingSeasonsSerializer(
        MarketingSeasons.objects.all(), many=True
    ).data

    for item in items:
        try:
            # serializer uses camelCase keys
            orig_start = date.fromisoformat(item["startDate"])
            orig_end = date.fromisoformat(item["endDate"])
        except Exception:
            continue

        cand_start, cand_end, default_sat = roll_season_dates_to_current_year(
            orig_start, orig_end, today
        )

        item["startDate"] = cand_start.isoformat()
        item["endDate"] = cand_end.isoformat()
        item["defaultDate"] = default_sat.isoformat()

        # Winter only: sales opening date (10 June of the current year)
        try:
            if item.get("key") == "hiver":
                item["salesOpenDate"] = date(today.year, 6, 10).isoformat()
        except Exception:
            pass

        # Whether this season's (rolled) window contains today
        try:
            item["currentSalesSeason"] = cand_start <= today <= cand_end
        except Exception:
            item["currentSalesSeason"] = False

    return {"items": items}


def rolled_season_window(
    season: "MarketingSeasons", today: date | None = None
) -> tuple[date, date]:
    """Convenience for single-season lookups (e.g. pricing's QF eligibility check).

    Returns (start_date, end_date) for `season`, rolled to the current
    real-world year, without building the full serialized payload.
    """
    cand_start, cand_end, _ = roll_season_dates_to_current_year(
        season.start_date, season.end_date, today
    )
    return cand_start, cand_end