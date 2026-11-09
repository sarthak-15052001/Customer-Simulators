from datetime import date
from decimal import Decimal

import pytest

from apps.tariff_scraper.services import scraper
from apps.tariff_scraper.services.tarif_builder import build_tarifs_from_scrape
from apps.tariff_scraper.services.llm_fallback import _parse_prices_from_response


def test_cross_year_period_pulls_start_year_back(monkeypatch):
    monkeypatch.setattr(scraper, "_today", lambda: date(2026, 7, 26))

    ranges = scraper.parse_vtf_period_cell("27/12 au 3/01/26")

    assert ranges == [(date(2025, 12, 27), date(2026, 1, 3))]


def test_yearless_period_uses_current_year_not_month_as_year(monkeypatch):
    monkeypatch.setattr(scraper, "_today", lambda: date(2026, 1, 1))

    ranges = scraper.parse_vtf_period_cell("11/04 au 2/05")

    assert ranges == [(date(2026, 4, 11), date(2026, 5, 2))]


def test_pc_adult_column_does_not_pick_child_price():
    rows = [
        ["Pension complete", "Periode", "Adultes", "Enfants"],
        ["", "11/04 au 2/05/26", "637 euros", "399 euros"],
    ]

    bands = scraper.parse_grille_table(rows)

    assert len(bands) == 1
    assert bands[0].formule == "PC"
    assert bands[0].scraped_price == Decimal("637")
    assert bands[0].unit_type == "Adultes"


def test_pc_shortened_price_row_still_labels_adult_unit_type():
    """Child age-group columns are now extracted alongside adults.

    The header row has: Adultes, 11-16 ans, 6-11 ans, 1-4 ans.
    The data row has prices for the first 3 columns (1-4 ans is blank).
    We expect 3 bands: Adultes (469), 11-16 ans (420), 6-11 ans (378).
    """
    rows = [
        ["Pension complete", "Adultes", "11-16 ans", "6-11 ans", "1-4 ans"],
        ["Paques", "11/04 au 2/05/26", "469 euros", "420 euros", "378 euros"],
    ]

    bands = scraper.parse_grille_table(rows)

    assert len(bands) == 3
    # Adult band
    assert bands[0].scraped_price == Decimal("469")
    assert bands[0].unit_type == "Adultes"
    assert bands[0].nb_adults == 1
    # Child 11-16 band
    assert bands[1].scraped_price == Decimal("420")
    assert bands[1].unit_type == "11-16 ans"
    assert bands[1].nb_adults is None
    # Child 6-11 band
    assert bands[2].scraped_price == Decimal("378")
    assert bands[2].unit_type == "6-11 ans"
    assert bands[2].nb_adults is None


def test_grille_prefers_struck_regular_price_over_promo():
    html = """
    <table>
      <tr><th>Pension complete</th><th>Periode</th><th>Adultes</th></tr>
      <tr>
        <td></td><td>11/04 au 2/05/26</td>
        <td><del>469 euros</del> <span class="promo">399 euros</span></td>
      </tr>
    </table>
    """

    bands = scraper.parse_bands_from_html(html)

    assert bands[0].scraped_price == Decimal("469")


def test_not_offered_and_parse_failure_are_noted_separately():
    notes = []
    rows = [
        ["Location", "Studio", "Appartement"],
        ["", "11/04 au 2/05/26", "-", "abc"],
    ]

    bands = scraper.parse_grille_table(rows, notes=notes)

    assert bands == []
    assert any(note.startswith("not_offered:") for note in notes)
    assert any(note.startswith("parse_failed:") for note in notes)


def test_price_parser_rejects_occupancy_and_accepts_zero():
    assert scraper._parse_price("6 pers.") is None
    assert scraper._parse_price("Studio 4 pers. 469 euros") == Decimal("469")
    assert scraper._parse_price("0 euros") == Decimal("0")
    assert scraper._parse_price("0 €") == Decimal("0")


def test_dp_derivation_marks_assumed_when_only_possible_on_request():
    rows = [
        ["Pension complete", "Periode", "Adultes"],
        ["", "11/04 au 2/05/26", "700 euros"],
    ]

    bands = scraper.parse_grille_table(
        rows,
        page_text="Demi-pension possible sur demande.",
    )

    dp = [band for band in bands if band.formule == "DP"]
    assert len(dp) == 1
    assert dp[0].derivation == scraper.DERIVATION_ASSUMED


def test_direct_dp_grille_is_scraped_without_discount_derivation():
    html = """
    <table>
      <tr><th>Pension complete</th><th>Periode</th><th>Adultes</th></tr>
      <tr><td></td><td>11/04 au 2/05/26</td><td>903 euros</td></tr>
      <tr><th>Demi-pension</th><th>Periode</th><th>Adultes</th></tr>
      <tr><td></td><td>11/04 au 2/05/26</td><td>770 euros</td></tr>
    </table>
    <p>Demi-pension = 15% de remise</p>
    """

    bands = scraper.parse_bands_from_html(html)

    dp = [band for band in bands if band.formule == "DP"]
    assert len(dp) == 1
    assert dp[0].scraped_price == Decimal("770")
    assert dp[0].derivation == scraper.DERIVATION_SCRAPED
    assert dp[0].source_page == "price_grid"
    assert dp[0].raw_cell_text == "770 euros"


def test_blank_child_free_cell_keeps_blank_raw_cell_text():
    rows = [
        [
            "Pension complete",
            "Periode",
            "Adultes",
            "11 à - 16 ans",
            "6 à - 11 ans",
            "4 à - 6 ans",
            "1 à - 4 ans",
        ],
        ["", "11/04 au 2/05/26", "469 €", "420 €", "378 €", "", "Gratuit*"],
    ]

    bands = scraper.parse_grille_table(rows)

    child_free = {
        band.unit_type: band
        for band in bands
        if band.date_start == date(2026, 4, 11) and band.scraped_price == Decimal("0")
    }
    assert child_free["4 à - 6 ans"].raw_cell_text == ""
    assert child_free["1 à - 4 ans"].raw_cell_text == "Gratuit*"


def test_gratuit_child_cell_keeps_gratuit_raw_cell_text():
    rows = [
        [
            "Pension complete",
            "Periode",
            "Adultes",
            "11 à - 16 ans",
            "6 à - 11 ans",
            "3 à - 6 ans",
            "1 à - 3 ans",
        ],
        ["", "27/06 au 4/07/26", "714 €", "644 €", "574 €", "Gratuit*", "Gratuit*"],
    ]

    bands = scraper.parse_grille_table(rows)

    child_free = {
        band.unit_type: band
        for band in bands
        if band.date_start == date(2026, 6, 27) and band.scraped_price == Decimal("0")
    }
    assert child_free["3 à - 6 ans"].raw_cell_text == "Gratuit*"
    assert child_free["1 à - 3 ans"].raw_cell_text == "Gratuit*"

def test_html_colspan_center_gratuit_applies_to_each_age_column_with_season_spacer():
    """Center-aligned colspan Gratuit* keeps text on both age columns."""
    html = """
    <table>
      <tr>
        <th colspan="3">Pension complete</th>
        <th>Adultes</th>
        <th>11 a - 16 ans</th>
        <th>6 a - 11 ans</th>
        <th>3 a - 6 ans</th>
        <th>1 a - 3 ans</th>
      </tr>
      <tr>
        <td>Paques</td>
        <td>27/06 au 4/07/26</td>
        <td>27/06 au 4/07/26</td>
        <td>714 euros</td>
        <td>644 euros</td>
        <td>574 euros</td>
        <td colspan="2" align="center">Gratuit*</td>
      </tr>
    </table>
    """

    bands = scraper.parse_bands_from_html(html)

    by_unit = {
        band.unit_type: band
        for band in bands
        if band.date_start == date(2026, 6, 27)
    }
    assert list(by_unit) == [
        "Adultes",
        "11 a - 16 ans",
        "6 a - 11 ans",
        "3 a - 6 ans",
        "1 a - 3 ans",
    ]
    assert by_unit["Adultes"].scraped_price == Decimal("714")
    assert by_unit["Adultes"].raw_cell_text == "714 euros"
    assert by_unit["11 a - 16 ans"].scraped_price == Decimal("644")
    assert by_unit["6 a - 11 ans"].scraped_price == Decimal("574")
    assert by_unit["3 a - 6 ans"].raw_cell_text == "Gratuit*"
    assert by_unit["1 a - 3 ans"].raw_cell_text == "Gratuit*"


def test_html_lacanau_right_aligned_colspan_keeps_blank_before_gratuit():
    """Lacanau: align=right colspan shows blank older column + Gratuit* younger."""
    html = """
    <table>
      <tr>
        <th colspan="3">Pension complete</th>
        <th>Adultes</th>
        <th>11 a - 16 ans</th>
        <th>6 a - 11 ans</th>
        <th>4 a - 6 ans</th>
        <th>1 a - 4 ans</th>
      </tr>
      <tr>
        <td>Paques</td>
        <td>11/04 au 2/05/26</td>
        <td>11/04 au 2/05/26</td>
        <td>469 euros</td>
        <td>420 euros</td>
        <td>378 euros</td>
        <td colspan="2" align="right">Gratuit*</td>
      </tr>
    </table>
    """

    bands = scraper.parse_bands_from_html(html)

    by_unit = {
        band.unit_type: band
        for band in bands
        if band.date_start == date(2026, 4, 11)
    }
    assert by_unit["4 a - 6 ans"].scraped_price == Decimal("0")
    assert by_unit["4 a - 6 ans"].raw_cell_text == ""
    assert by_unit["1 a - 4 ans"].scraped_price == Decimal("0")
    assert by_unit["1 a - 4 ans"].raw_cell_text == "Gratuit*"


def test_html_biarritz_colspan_gratuit_child_cell_applies_to_each_age_column():
    html = """
    <table>
      <tr>
        <th colspan="2">Pension complete</th>
        <th>Adultes</th>
        <th>11 a - 16 ans</th>
        <th>6 a - 11 ans</th>
        <th>3 a - 6 ans</th>
        <th>1 a - 3 ans</th>
      </tr>
      <tr>
        <td></td>
        <td>27/06 au 4/07/26</td>
        <td>714 euros</td>
        <td>644 euros</td>
        <td>574 euros</td>
        <td colspan="2" align="center">Gratuit*</td>
      </tr>
    </table>
    """

    bands = scraper.parse_bands_from_html(html)

    by_unit = {
        band.unit_type: band
        for band in bands
        if band.date_start == date(2026, 6, 27)
    }
    assert by_unit["Adultes"].raw_cell_text == "714 euros"
    assert by_unit["3 a - 6 ans"].raw_cell_text == "Gratuit*"
    assert by_unit["1 a - 3 ans"].raw_cell_text == "Gratuit*"


def test_html_agde_paques_colspan_gratuit_on_both_child_columns():
    """Agde Pâques row: season label + duplicated period + center colspan Gratuit*."""
    html = """
    <table>
      <tr>
        <th colspan="3">Sejour semaine en pension complete</th>
        <th>Adultes</th>
        <th>11 a - 16 ans</th>
        <th>6 a - 11 ans</th>
        <th>4 a - 6 ans</th>
        <th>1 a - 4 ans</th>
      </tr>
      <tr>
        <td>Paques</td>
        <td>11 au 25/04/26</td>
        <td>11 au 25/04/26</td>
        <td>574 euros</td>
        <td>518 euros</td>
        <td>462 euros</td>
        <td colspan="2" align="center">Gratuit*</td>
      </tr>
    </table>
    """

    bands = scraper.parse_bands_from_html(html)

    by_unit = {
        band.unit_type: band
        for band in bands
        if band.date_start == date(2026, 4, 11)
    }
    assert by_unit["4 a - 6 ans"].scraped_price == Decimal("0")
    assert by_unit["4 a - 6 ans"].raw_cell_text == "Gratuit*"
    assert by_unit["1 a - 4 ans"].scraped_price == Decimal("0")
    assert by_unit["1 a - 4 ans"].raw_cell_text == "Gratuit*"


def test_talloires_under_three_child_column_is_scraped():
    rows = [
        [
            "Tarif par nuit en pension complete",
            "Adultes",
            "11 à - 16 ans",
            "3 à - 11 ans",
            "- 3 ans",
        ],
        ["4/04 au 1/11/26", "62 €", "56 €", "37 €", "Gratuit"],
    ]

    bands = scraper.parse_grille_table(rows)

    by_unit = {band.unit_type: band for band in bands}
    assert set(by_unit) == {"Adultes", "11 à - 16 ans", "3 à - 11 ans", "- 3 ans"}
    assert by_unit["- 3 ans"].scraped_price == Decimal("0")
    assert by_unit["- 3 ans"].raw_cell_text == "Gratuit"


def test_loc_grille_preserves_raw_cell_price_text():
    rows = [
        ["Location", "Periode", "Appartement 3 pièces 5/7 personnes"],
        ["", "27/06 au 4/07/26", "1253 €"],
    ]

    bands = scraper.parse_grille_table(rows)

    assert len(bands) == 1
    assert bands[0].formule == "LOC"
    assert bands[0].scraped_price == Decimal("1253")
    assert bands[0].raw_cell_text == "1253 €"


def test_derived_dp_keeps_dash_raw_cell_text():
    rows = [
        ["Pension complete", "Periode", "Adultes"],
        ["", "27/06 au 4/07/26", "714 €"],
    ]

    bands = scraper.parse_grille_table(
        rows,
        page_text="Demi-pension = 15% de remise",
    )

    dp = [band for band in bands if band.formule == "DP"]
    assert len(dp) == 1
    assert dp[0].derivation == scraper.DERIVATION_STATED
    assert dp[0].raw_cell_text == "-"


def test_multisection_grille_keeps_pc_dp_and_loc():
    html = """
    <table>
      <tr><th>Pension complete</th><th>Periode</th><th>Adultes</th></tr>
      <tr><td></td><td>11/04 au 2/05/26</td><td>903 euros</td></tr>
      <tr><th>Demi-pension</th><th>Periode</th><th>Adultes</th></tr>
      <tr><td></td><td>11/04 au 2/05/26</td><td>770 euros</td></tr>
      <tr><th>Location</th><th>Periode</th><th>Studio</th></tr>
      <tr><td></td><td>11/04 au 2/05/26</td><td>469 euros</td></tr>
    </table>
    """

    bands = scraper.parse_bands_from_html(html)

    assert [(band.formule, band.scraped_price) for band in bands] == [
        ("PC", Decimal("903")),
        ("DP", Decimal("770")),
        ("LOC", Decimal("469")),
    ]


def test_llm_response_parser_keeps_zero_price():
    assert _parse_prices_from_response("[0, 469]") == [Decimal("0"), Decimal("469")]


@pytest.mark.django_db
def test_builder_dedupes_duplicate_proposed_bands():
    from apps.catalog.models import Village

    Village.objects.create(
        id="dedupe-village",
        nom="Dedupe Village",
        region="Aquitaine / Landes",
        env_emoji="",
        env_code="sea",
        has_loc=False,
        ski=False,
        tarifs={"PC": {"hs": 469}},
    )
    band = scraper.RawPriceBand(
        formule="PC",
        source_page="price_grid",
        date_label="11/04 au 2/05/26",
        date_start=date(2026, 4, 11),
        date_end=date(2026, 5, 2),
        scraped_price=Decimal("469"),
        unit_type="Adultes",
    )
    scrape_result = scraper.VillageScrapeResult(
        village_id="dedupe-village",
        url="https://example.test",
        bands=[band, band],
    )

    result = build_tarifs_from_scrape(scrape_result)

    assert result.snapshots_created == 2
    assert result.bands_proposed == 1


@pytest.mark.django_db
def test_builder_keeps_zero_price_in_proposals_and_season_patch():
    from apps.catalog.models import Village

    Village.objects.create(
        id="free-price-village",
        nom="Free Price Village",
        region="Aquitaine / Landes",
        env_emoji="",
        env_code="sea",
        has_loc=False,
        ski=False,
        tarifs={"PC": {"hs": 469}},
    )
    band = scraper.RawPriceBand(
        formule="PC",
        source_page="price_grid",
        date_label="11/04 au 2/05/26",
        date_start=date(2026, 4, 11),
        date_end=date(2026, 5, 2),
        scraped_price=Decimal("0"),
        unit_type="Adultes",
    )
    scrape_result = scraper.VillageScrapeResult(
        village_id="free-price-village",
        url="https://example.test",
        bands=[band],
    )

    result = build_tarifs_from_scrape(scrape_result)

    assert result.snapshots_created == 1
    assert result.bands_proposed == 1
    assert result.skipped_no_price == 0

    from apps.tariff_scraper.models import TariffApproval

    approval = TariffApproval.objects.get(pk=result.approval_id)
    assert approval.proposed_bands[0]["price"] == 0
    assert approval.proposed_season_tarifs["PC"]["hs"] == 0
