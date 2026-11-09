"""Dates must render as JJ/MM/AAAA everywhere in the admin.

Two rendering paths have to agree: model ``DateField``s, which Django
localizes through ``FORMAT_MODULE_PATH`` (config/formats/fr), and dates stored
inside JSON blobs (``TariffApproval.proposed_bands``), which arrive as ISO
strings and are formatted by ``admin_display.fr_date``. Before this, the same
review screen showed "1 mars 2027" in one table and "2026-08-01" in the next.
"""
from datetime import date, datetime

import pytest
from django.utils import timezone
from django.utils.formats import date_format, localize

from apps.tariff_scraper.admin_display import (
    fr_date,
    render_bands_grid,
    render_season_tarifs_notes,
)


# ─── Locale-level formats (model fields) ──────────────────────────────────


def test_locale_renders_dates_numerically():
    assert date_format(date(2027, 3, 1), "DATE_FORMAT") == "01/03/2027"
    assert date_format(date(2026, 8, 1), "SHORT_DATE_FORMAT") == "01/08/2026"


def test_localize_matches_the_booking_funnel_format():
    """`localize` is what the admin calls for model DateFields."""
    assert localize(date(2026, 8, 8)) == "08/08/2026"


def test_iso_input_still_accepted_by_forms():
    from django.utils.formats import get_format

    # Fixtures, the API and the admin's own change forms post ISO.
    assert "%Y-%m-%d" in get_format("DATE_INPUT_FORMATS")
    assert "%d/%m/%Y" in get_format("DATE_INPUT_FORMATS")


# ─── fr_date helper (JSON-sourced dates) ──────────────────────────────────


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-08-01", "01/08/2026"),
        (date(2026, 8, 1), "01/08/2026"),
        ("2026-12-26", "26/12/2026"),
        (None, "-"),
        ("", "-"),
    ],
)
def test_fr_date_renders_numeric_french(value, expected):
    assert fr_date(value) == expected


def test_fr_date_handles_datetimes():
    assert fr_date(datetime(2026, 8, 1, 14, 30)) == "01/08/2026 14:30"
    assert fr_date("2026-08-01T14:30:00") == "01/08/2026 14:30"


def test_fr_date_renders_aware_datetimes_in_local_time():
    aware = timezone.make_aware(datetime(2026, 8, 1, 23, 30))
    assert fr_date(aware).startswith("01/08/2026")


def test_fr_date_echoes_unparseable_input():
    """A malformed scraped date must stay visible, not be silently blanked."""
    assert fr_date("sur demande") == "sur demande"


# ─── Rendered admin tables ────────────────────────────────────────────────


def test_bands_grid_shows_french_dates_only():
    html = render_bands_grid(
        [
            {
                "formule": "PC",
                "date_start": "2026-07-25",
                "date_end": "2026-08-15",
                "pricing_type": "per_person",
                "unit_type": "Adultes",
                "price": 728,
                "source_page": "price_grid",
                "date_label": "25/07 au 15/08/26",
                "source_snapshot_id": 1,
            }
        ]
    )

    assert "25/07/2026" in html
    assert "15/08/2026" in html
    assert "2026-07-25" not in html
    assert "2026-08-15" not in html


def test_notes_grid_lists_unverified_and_dropped_buckets():
    html = render_season_tarifs_notes(
        {
            "unverified": [{"formule": "LOC", "season": "hs", "price": 450}],
            "dropped_closed": [{"formule": "PC", "season": "fetes", "price": 728}],
        }
    )

    assert "LOC" in html and "HS" in html
    assert "PC" in html and "Fetes" in html
    assert "Non verifie par ce scrape" in html
    assert "Retire (village ferme)" in html


def test_notes_grid_says_so_when_everything_was_scraped():
    html = render_season_tarifs_notes({"unverified": [], "dropped_closed": []})

    assert "proviennent de ce scrape" in html
