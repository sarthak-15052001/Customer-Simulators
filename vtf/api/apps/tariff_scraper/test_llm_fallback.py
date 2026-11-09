"""Tests for tariff LLM fallback — must not break deterministic scraping.

Covers:
  - Adult + child age-band PC/DP mapping (mirrors scraper.py child columns)
  - Legacy adult-only fallback when header row can't be aligned
  - DP derived from remise for every PC column, adult and child alike
  - Mocked LM Studio path
  - scrape_village does not call LLM when priced bands exist
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.tariff_scraper.services.llm_fallback import (
    FootnoteInfo,
    RowPayload,
    _recognized_columns,
    chunk_grille_html,
    extract_footnotes,
    extract_row_prices,
    llm_bands_to_raw_price_bands,
    parse_grille_with_llm,
)
from apps.tariff_scraper.services.scraper import (
    HttpGridScrapeResult,
    RawPriceBand,
    scrape_village,
)

FIXTURE = Path(__file__).parent / "fixtures" / "messy_pc_grille.html"

# Minimal messy PC grille (colspan + Gratuit + demi-pension footnote)
MESSY_PC_HTML = """
<html><body>
<div>Grille tarifaire — pension complète</div>
<table>
  <tr>
    <th colspan="3">Séjour semaine en pension complète</th>
    <th>Adultes</th>
    <th>11 à - 16 ans</th>
    <th>6 à - 11 ans</th>
    <th>3 à - 6 ans</th>
    <th>1 à - 3ans</th>
  </tr>
  <tr>
    <th>Hors vacances</th>
    <td colspan="2">2/05 au 4/07, 29/08 au 26/09/26</td>
    <td>637 €</td>
    <td>574 €</td>
    <td>511 €</td>
    <td>385 €</td>
    <td>Gratuit</td>
  </tr>
  <tr>
    <th>Eté</th>
    <td colspan="2">25/07 au 15/08/26</td>
    <td>763 €</td>
    <td>686 €</td>
    <td>609 €</td>
    <td>455 €</td>
    <td>231 €</td>
  </tr>
</table>
<blockquote>
  1/2 pension possible = 15% de remise sur le tarif en pension complète
  Supplément court séjour : 25€/nuit — 10% de remise sur les séjours quinzaine
</blockquote>
</body></html>
"""


class ChunkerAndFootnotesTest(TestCase):
    def test_chunk_extracts_rows_and_adult_cells(self):
        rows = chunk_grille_html(MESSY_PC_HTML)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0].formule_hint, "PC")
        self.assertTrue(rows[0].cells)
        # First cell is adult price (Gratuit→0 already applied on last cols)
        self.assertEqual(rows[0].cells[0], "637")

    def test_chunk_extracts_child_age_columns_aligned_with_price_cells(self):
        """Header row's child age-band labels line up 1:1 with price cells."""
        rows = chunk_grille_html(MESSY_PC_HTML)
        self.assertEqual(len(rows), 2)
        row = rows[0]
        self.assertEqual(
            row.column_labels,
            ["Adultes", "11 à - 16 ans", "6 à - 11 ans", "3 à - 6 ans", "1 à - 3ans"],
        )
        self.assertEqual(len(row.column_labels), len(row.cells))
        # Gratuit → 0 still applies for the youngest (free) child column
        self.assertEqual(row.cells[-1], "0")

    def test_footnotes_dp_only_no_supplement_fields(self):
        info = extract_footnotes(MESSY_PC_HTML)
        self.assertEqual(info.dp_remise, Decimal("0.15"))
        # FootnoteInfo must not expose supplement/discount attributes
        self.assertFalse(hasattr(info, "supplements"))
        self.assertFalse(hasattr(info, "discounts"))
        self.assertFalse(hasattr(info, "age_groups"))


class RecognizedColumnsTest(TestCase):
    def test_recognizes_adult_and_child_columns_in_order(self):
        rows = chunk_grille_html(MESSY_PC_HTML)
        cols = _recognized_columns(rows[0])
        self.assertEqual(
            [(i, role) for i, _label, role in cols],
            [(0, "adults"), (1, "child"), (2, "child"), (3, "child"), (4, "child")],
        )

    def test_falls_back_to_adult_only_when_column_labels_not_aligned(self):
        """Legacy behavior: rows without a resolvable header row stay adult-only."""
        row = RowPayload(
            row_index=0,
            season="",
            period_text="x",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 7),
            cells=["500"],
            formule_hint="PC",
            unit_type="Adultes",
        )
        self.assertEqual(_recognized_columns(row), [(0, "Adultes", "adults")])

    def test_generic_enfants_header_without_age_range_is_not_recognized(self):
        """A vague 'Enfants' column (no age range) can't map to an age band —
        same rule scraper.py's _is_child_column_header applies."""
        html = """
        <html><body><table>
          <tr><th>Pension complete</th><th>Periode</th><th>Adultes</th><th>Enfants</th></tr>
          <tr><td></td><td>11/04 au 2/05/26</td><td>903 euros</td><td>300 euros</td></tr>
        </table></body></html>
        """
        rows = chunk_grille_html(html)
        cols = _recognized_columns(rows[0])
        self.assertEqual([role for _, _, role in cols], ["adults"])

    def test_loc_rows_have_no_recognized_columns(self):
        row = RowPayload(
            row_index=0,
            season="",
            period_text="x",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 7),
            cells=["469", "399"],
            formule_hint="LOC",
        )
        self.assertEqual(_recognized_columns(row), [])


class MappingAdultOnlyTest(TestCase):
    def test_pc_uses_adult_price_only_and_derives_dp(self):
        rows = [
            RowPayload(
                row_index=0,
                season="",
                period_text="25/07 au 15/08/26",
                date_start=date(2026, 7, 25),
                date_end=date(2026, 8, 15),
                cells=["763", "686", "609", "455", "231"],
                formule_hint="PC",
            )
        ]
        prices = [[Decimal("763"), None, None, None, None]]
        footnotes = FootnoteInfo(dp_remise=Decimal("0.15"))
        bands = llm_bands_to_raw_price_bands(rows, prices, footnotes)

        pc = [b for b in bands if b.formule == "PC"]
        dp = [b for b in bands if b.formule == "DP"]
        self.assertEqual(len(pc), 1)
        self.assertEqual(pc[0].scraped_price, Decimal("763"))
        self.assertEqual(pc[0].nb_adults, 1)
        self.assertEqual(pc[0].source_page, "llm_fallback")
        self.assertEqual(len(dp), 1)
        # nightly 763/7 * 0.85 rounded * 7
        self.assertGreater(dp[0].scraped_price, 0)
        # No LOC / no age-tier formules
        self.assertTrue(all(b.formule in ("PC", "DP") for b in bands))


class MappingChildAgeBandsTest(TestCase):
    """PC/DP rows with a recognized child age-band header row must produce
    one band per column (adult + each child age band), and DP derivation
    must run for every one of those columns — not just the adult column."""

    def test_pc_and_dp_bands_produced_for_every_column(self):
        rows = chunk_grille_html(MESSY_PC_HTML)
        self.assertEqual(len(rows), 2)

        # Mimic extract_row_prices() output: full-length, aligned to row.cells
        all_prices = [
            [Decimal("637"), Decimal("574"), Decimal("511"), Decimal("385"), Decimal("0")],
            [Decimal("763"), Decimal("686"), Decimal("609"), Decimal("455"), Decimal("231")],
        ]
        footnotes = FootnoteInfo(dp_remise=Decimal("0.15"))
        bands = llm_bands_to_raw_price_bands(rows, all_prices, footnotes)

        pc = [b for b in bands if b.formule == "PC"]
        dp = [b for b in bands if b.formule == "DP"]

        # Row 0's period text is a multi-range cell ("2/05 au 4/07, 29/08 au
        # 26/09/26" → 2 date ranges); row 1 is a single range. 5 columns
        # each: (2 + 1) ranges x 5 columns = 15 PC bands, same for DP.
        self.assertEqual(len(pc), 15)
        self.assertEqual(len(dp), 15)
        self.assertTrue(all(b.source_page == "llm_fallback" for b in pc + dp))

        # Adult column keeps nb_adults=1; child columns don't claim adults.
        adult_pc = [b for b in pc if b.unit_type == "Adultes"]
        child_pc = [b for b in pc if b.unit_type != "Adultes"]
        self.assertEqual(len(adult_pc), 3)
        self.assertEqual(len(child_pc), 12)
        self.assertTrue(all(b.nb_adults == 1 for b in adult_pc))
        self.assertTrue(all(b.nb_adults is None for b in child_pc))

        # Spot-check one child age band's price and label.
        row0_611 = next(
            b for b in pc
            if b.unit_type == "6 à - 11 ans" and b.date_start == date(2026, 5, 2)
        )
        self.assertEqual(row0_611.scraped_price, Decimal("511"))

        # Free child column (Gratuit → 0) is still a real priced band, not dropped.
        free_band = next(
            b for b in pc
            if b.unit_type == "1 à - 3ans" and b.date_start == date(2026, 5, 2)
        )
        self.assertEqual(free_band.scraped_price, Decimal("0"))

        # DP was derived per column, including for the free child band (0 stays 0).
        free_dp = next(
            b for b in dp
            if b.unit_type == "1 à - 3ans" and b.date_start == date(2026, 5, 2)
        )
        self.assertEqual(free_dp.scraped_price, Decimal("0"))
        self.assertIn(free_dp.derivation, ("derived_stated", "derived_assumed"))

    def test_legacy_adult_only_row_unaffected(self):
        """A row without column_labels (unresolved header) still yields a
        single adult PC band + single derived DP band, exactly as before."""
        rows = [
            RowPayload(
                row_index=0,
                season="",
                period_text="25/07 au 15/08/26",
                date_start=date(2026, 7, 25),
                date_end=date(2026, 8, 15),
                cells=["763", "686", "609", "455", "231"],
                formule_hint="PC",
                unit_type="Adultes",
            )
        ]
        prices = [[Decimal("763"), None, None, None, None]]
        footnotes = FootnoteInfo(dp_remise=Decimal("0.15"))
        bands = llm_bands_to_raw_price_bands(rows, prices, footnotes)

        pc = [b for b in bands if b.formule == "PC"]
        dp = [b for b in bands if b.formule == "DP"]
        self.assertEqual(len(pc), 1)
        self.assertEqual(len(dp), 1)
        self.assertEqual(pc[0].unit_type, "Adultes")
        self.assertEqual(pc[0].nb_adults, 1)


class ExtractRowPricesChildColumnsTest(TestCase):
    """extract_row_prices() must expand LLM output to the adult + child
    column positions, leaving unrecognized columns as None."""

    @patch("apps.tariff_scraper.services.llm_fallback._call_lmstudio")
    def test_llm_response_maps_to_adult_and_child_positions(self, mock_llm):
        mock_llm.return_value = "[637, 574, 511, 385, 0]"
        rows = chunk_grille_html(MESSY_PC_HTML)
        prices = extract_row_prices(rows[0])
        self.assertEqual(
            prices,
            [Decimal("637"), Decimal("574"), Decimal("511"), Decimal("385"), Decimal("0")],
        )

    @patch("apps.tariff_scraper.services.llm_fallback._call_lmstudio", return_value=None)
    def test_regex_fallback_still_covers_all_columns(self, _mock_llm):
        rows = chunk_grille_html(MESSY_PC_HTML)
        prices = extract_row_prices(rows[0])
        # Regex fallback parses each cleaned cell directly — same result.
        self.assertEqual(
            prices,
            [Decimal("637"), Decimal("574"), Decimal("511"), Decimal("385"), Decimal("0")],
        )

    @patch("apps.tariff_scraper.services.llm_fallback._call_lmstudio")
    def test_wrong_length_llm_response_falls_back_to_regex(self, mock_llm):
        """A hallucinated/short LLM response (adult-only) must not silently
        drop the child columns — regex fallback should still fill them in."""
        mock_llm.return_value = "[637]"
        rows = chunk_grille_html(MESSY_PC_HTML)
        prices = extract_row_prices(rows[0])
        self.assertEqual(
            prices,
            [Decimal("637"), Decimal("574"), Decimal("511"), Decimal("385"), Decimal("0")],
        )


@override_settings(LLM_FALLBACK_ENABLED=True)
class ParseGrilleWithLlmChildAgeBandsTest(TestCase):
    """End-to-end parse_grille_with_llm() over a real child-age-band grille."""

    @patch("apps.tariff_scraper.services.llm_fallback._call_lmstudio")
    def test_child_age_bands_come_through_end_to_end(self, mock_llm):
        mock_llm.side_effect = [
            "[637, 574, 511, 385, 0]",
            "[763, 686, 609, 455, 231]",
        ]
        bands = parse_grille_with_llm(MESSY_PC_HTML, "test-village")

        pc = [b for b in bands if b.formule == "PC"]
        dp = [b for b in bands if b.formule == "DP"]
        self.assertEqual(len(pc), 15)
        self.assertEqual(len(dp), 15)

        child_labels = {b.unit_type for b in pc if b.nb_adults is None}
        self.assertEqual(
            child_labels,
            {"11 à - 16 ans", "6 à - 11 ans", "3 à - 6 ans", "1 à - 3ans"},
        )
        self.assertTrue(all(b.source_page == "llm_fallback" for b in bands))
        self.assertTrue(all(b.formule in ("PC", "DP", "LOC") for b in bands))


@override_settings(LLM_FALLBACK_ENABLED=True)
class ParseGrilleWithLlmTest(TestCase):
    @patch("apps.tariff_scraper.services.llm_fallback._call_lmstudio")
    def test_mocked_llm_returns_adult_pc_bands(self, mock_llm):
        mock_llm.return_value = "[637]"
        bands = parse_grille_with_llm(MESSY_PC_HTML, "test-village")
        pc = [b for b in bands if b.formule == "PC"]
        self.assertGreaterEqual(len(pc), 1)
        self.assertEqual(pc[0].scraped_price, Decimal("637"))
        self.assertTrue(all(b.source_page == "llm_fallback" for b in bands))
        self.assertTrue(all(b.formule in ("PC", "DP", "LOC") for b in bands))

    @patch("apps.tariff_scraper.services.llm_fallback._call_lmstudio", return_value=None)
    def test_regex_fallback_when_llm_down(self, _mock_llm):
        bands = parse_grille_with_llm(MESSY_PC_HTML, "test-village")
        pc = [b for b in bands if b.formule == "PC"]
        self.assertGreaterEqual(len(pc), 1)
        self.assertEqual(pc[0].scraped_price, Decimal("637"))

    @patch("apps.tariff_scraper.services.llm_fallback._call_lmstudio")
    def test_direct_dp_grille_is_preserved_in_llm_fallback(self, mock_llm):
        html = """
        <html><body>
        <table>
          <tr><th>Pension complete</th><th>Periode</th><th>Adultes</th></tr>
          <tr><td></td><td>11/04 au 2/05/26</td><td>903 euros</td></tr>
          <tr><th>Demi-pension</th><th>Periode</th><th>Adultes</th></tr>
          <tr><td></td><td>11/04 au 2/05/26</td><td>770 euros</td></tr>
          <tr><th>Location</th><th>Periode</th><th>Studio</th></tr>
          <tr><td></td><td>11/04 au 2/05/26</td><td>469 euros</td></tr>
        </table>
        <p>Demi-pension = 15% de remise</p>
        </body></html>
        """
        mock_llm.side_effect = ["[903]", "[770]", "[469]"]

        bands = parse_grille_with_llm(html, "test-village")

        self.assertEqual(
            [(band.formule, band.scraped_price) for band in bands],
            [("PC", Decimal("903")), ("DP", Decimal("770")), ("LOC", Decimal("469"))],
        )
        dp = [band for band in bands if band.formule == "DP"]
        self.assertEqual(dp[0].derivation, "scraped")
        self.assertEqual(dp[0].source_page, "llm_fallback")

    @patch("apps.tariff_scraper.services.llm_fallback._call_lmstudio")
    def test_footnote_row_inside_table_does_not_hijack_formule_hint(self, mock_llm):
        """Regression for a trailing <tr> footnote inside the PC table.

        A "Demi-pension = 15% de remise" note row must not be mistaken for
        a DP section header — it has no period cell, so it should be
        skipped, and the PC period after it must stay PC with its scraped
        Adultes unit label intact.
        """
        html = """
        <html><body>
        <table>
          <tr><th>Pension complete</th><th>Periode</th><th>Adultes</th></tr>
          <tr><td></td><td>11/04 au 2/05/26</td><td>903 euros</td></tr>
          <tr><td colspan="3">Demi-pension = 15% de remise</td></tr>
          <tr><td></td><td>3/05 au 30/05/26</td><td>950 euros</td></tr>
        </table>
        </body></html>
        """
        mock_llm.side_effect = ["[903]", "[950]"]

        bands = parse_grille_with_llm(html, "test-village")

        pc = [b for b in bands if b.formule == "PC"]
        self.assertEqual(len(pc), 2)
        self.assertEqual(
            {(b.date_start, b.date_end): b.scraped_price for b in pc},
            {
                (date(2026, 4, 11), date(2026, 5, 2)): Decimal("903"),
                (date(2026, 5, 3), date(2026, 5, 30)): Decimal("950"),
            },
        )
        # Both PC rows keep their scraped Adultes unit label — the footnote
        # row must not have reset pension_unit_type.
        self.assertTrue(all(b.unit_type == "Adultes" for b in pc))
        # No band was mislabeled DP by the footnote.
        self.assertFalse(any(b.formule == "DP" for b in bands if b.scraped_price == Decimal("950")))

    @patch("apps.tariff_scraper.services.llm_fallback._call_lmstudio")
    def test_dp_derivation_is_per_band_not_page_global(self, mock_llm):
        """A DP grid covering only part of the season must not suppress
        derived DP for PC periods outside that DP grid's coverage."""
        html = """
        <html><body>
        <table>
          <tr><th>Pension complete</th><th>Periode</th><th>Adultes</th></tr>
          <tr><td></td><td>11/04 au 2/05/26</td><td>700 euros</td></tr>
          <tr><td></td><td>25/07 au 15/08/26</td><td>900 euros</td></tr>
          <tr><th>Demi-pension</th><th>Periode</th><th>Adultes</th></tr>
          <tr><td></td><td>25/07 au 15/08/26</td><td>770 euros</td></tr>
        </table>
        </body></html>
        """
        mock_llm.side_effect = ["[700]", "[900]", "[770]"]

        bands = parse_grille_with_llm(html, "test-village")

        dp = [b for b in bands if b.formule == "DP"]
        dp_by_period = {(b.date_start, b.date_end): b for b in dp}

        # High season: direct scraped DP is preserved as-is.
        high_season = (date(2026, 7, 25), date(2026, 8, 15))
        self.assertIn(high_season, dp_by_period)
        self.assertEqual(dp_by_period[high_season].scraped_price, Decimal("770"))
        self.assertEqual(dp_by_period[high_season].derivation, "scraped")

        # Off season: no direct DP was scraped for it, so it must still get
        # a derived DP band instead of being silently dropped.
        off_season = (date(2026, 4, 11), date(2026, 5, 2))
        self.assertIn(off_season, dp_by_period)
        self.assertIn(dp_by_period[off_season].derivation, ("derived_stated", "derived_assumed"))
        self.assertGreater(dp_by_period[off_season].scraped_price, 0)


@override_settings(LLM_FALLBACK_ENABLED=True)
class ScrapeVillageDoesNotBreakTest(TestCase):
    @patch("apps.tariff_scraper.services.llm_fallback.parse_grille_with_llm")
    @patch("apps.tariff_scraper.services.scraper.scrape_price_grid_http")
    def test_llm_not_called_when_scrape_succeeds(self, mock_http, mock_llm):
        mock_http.return_value = HttpGridScrapeResult(
            bands=[
                RawPriceBand(
                    formule="PC",
                    source_page="price_grid",
                    date_label="25/07 au 15/08/26",
                    date_start=date(2026, 7, 25),
                    date_end=date(2026, 8, 15),
                    scraped_price=Decimal("763"),
                    is_available=True,
                    nb_adults=1,
                )
            ],
            html_len=100,
            html="<html></html>",
            has_grille_markers=True,
        )
        result = scrape_village("lacanau", "https://example.com/lacanau")
        mock_llm.assert_not_called()
        self.assertEqual(len(result.bands), 1)
        self.assertEqual(result.bands[0].source_page, "price_grid")

    @patch("apps.tariff_scraper.services.llm_fallback.parse_grille_with_llm")
    @patch("apps.tariff_scraper.services.scraper.scrape_price_grid_http")
    def test_llm_used_only_when_zero_priced_bands(self, mock_http, mock_parse):
        mock_http.return_value = HttpGridScrapeResult(
            bands=[],
            html_len=len(MESSY_PC_HTML),
            html=MESSY_PC_HTML,
            has_grille_markers=True,
        )
        mock_parse.return_value = [
            RawPriceBand(
                formule="PC",
                source_page="llm_fallback",
                date_label="25/07 au 15/08/26",
                date_start=date(2026, 7, 25),
                date_end=date(2026, 8, 15),
                scraped_price=Decimal("637"),
                is_available=True,
                nb_adults=1,
            )
        ]

        import builtins
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "playwright.sync_api" or name == "playwright":
                raise ImportError("playwright disabled in test")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            result = scrape_village("test-village", "https://example.com/x")

        mock_parse.assert_called_once()
        self.assertEqual(result.bands[0].source_page, "llm_fallback")
        self.assertEqual(result.bands[0].scraped_price, Decimal("637"))


class FixtureFileTest(TestCase):
    def test_poc_fixture_chunks_if_present(self):
        if not FIXTURE.exists():
            self.skipTest("messy_pc_grille.html fixture not copied yet")
        html = FIXTURE.read_text(encoding="utf-8")
        rows = chunk_grille_html(html)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0].formule_hint, "PC")
