"""Tests for DP remise verification — must not break deterministic scraping
or the existing LLM fallback.

Covers:
  - Runs automatically whenever scrape_village() sees a DP band that was
    *derived* (no separate on/off switch)
  - Agreement: regex stated % == LLM % -> match=True, no alert
  - Agreement: neither side finds a remise -> match=True
  - Mismatch: regex assumed default 15% but LLM finds an explicit different %
  - Mismatch: regex found explicit % but LLM finds none
  - Mismatch: regex found explicit % but LLM disagrees on the number
  - Tolerance setting absorbs small differences instead of flagging them
  - LLM failure / bad JSON -> "unable to verify" (checked=False), never a
    false-positive mismatch
  - scrape_village only calls verification when a DP band was *derived*
    (never when DP was scraped directly, never when nothing was priced)
  - A failure inside verification never breaks the scrape itself
  - tasks.py dispatches notify_dp_remise_mismatch only on checked+mismatch,
    and never touches summary["ok"]
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.tariff_scraper.services.dp_verification import (
    DpVerificationResult,
    _compare,
    _extract_llm_remise,
    verify_dp_remise,
)
from apps.tariff_scraper.services.scraper import (
    DERIVATION_ASSUMED,
    DERIVATION_STATED,
    DpRemiseInfo,
    HttpGridScrapeResult,
    RawPriceBand,
    scrape_village,
)

STATED_HTML = """
<html><body>
<div>Grille tarifaire — pension complète</div>
<blockquote>
  1/2 pension possible = 15% de remise sur le tarif en pension complète
</blockquote>
</body></html>
"""

ASSUMED_HTML = """
<html><body>
<div>Grille tarifaire — pension complète</div>
<blockquote>
  1/2 pension possible sur demande
</blockquote>
</body></html>
"""

NO_MENTION_HTML = "<html><body><div>Grille tarifaire</div></body></html>"


# ---------------------------------------------------------------------------
# Basic entry-point guards (empty html)
# ---------------------------------------------------------------------------

class ConfigTest(TestCase):
    def test_verify_handles_empty_html(self):
        result = verify_dp_remise("", "lacanau")
        self.assertFalse(result.checked)
        self.assertIn("no html", result.note.lower())


# ---------------------------------------------------------------------------
# Comparison logic (pure function, no LLM)
# ---------------------------------------------------------------------------

class CompareTest(TestCase):
    def test_both_none_is_a_match(self):
        match, note = _compare(None, None)
        self.assertTrue(match)

    def test_exact_agreement_is_a_match(self):
        info = DpRemiseInfo(remise=Decimal("0.15"), derivation=DERIVATION_STATED)
        match, note = _compare(info, Decimal("0.15"))
        self.assertTrue(match)

    def test_regex_assumed_default_but_llm_finds_explicit_pct_is_a_mismatch(self):
        # This is exactly the client's scenario: page moved from "possible"
        # to a stated (different) %, regex still silently assumes 15%.
        info = DpRemiseInfo(remise=Decimal("0.15"), derivation=DERIVATION_ASSUMED)
        match, note = _compare(info, Decimal("0.20"))
        self.assertFalse(match)
        self.assertIn("assumed default", note)

    def test_regex_stated_but_llm_finds_nothing_is_a_mismatch(self):
        info = DpRemiseInfo(remise=Decimal("0.15"), derivation=DERIVATION_STATED)
        match, note = _compare(info, None)
        self.assertFalse(match)

    def test_regex_none_but_llm_finds_explicit_pct_is_a_mismatch(self):
        match, note = _compare(None, Decimal("0.10"))
        self.assertFalse(match)

    def test_disagreeing_explicit_percentages_is_a_mismatch(self):
        info = DpRemiseInfo(remise=Decimal("0.15"), derivation=DERIVATION_STATED)
        match, note = _compare(info, Decimal("0.18"))
        self.assertFalse(match)

    def test_tolerance_absorbs_small_drift(self):
        info = DpRemiseInfo(remise=Decimal("0.15"), derivation=DERIVATION_STATED)
        with patch(
            "apps.tariff_scraper.services.dp_verification._tolerance_pp",
            return_value=Decimal("5"),
        ):
            match, note = _compare(info, Decimal("0.17"))
        self.assertTrue(match)


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------

class LlmParsingTest(TestCase):
    @patch("apps.tariff_scraper.services.dp_verification._call_lmstudio")
    def test_parses_explicit_percentage(self, mock_llm):
        mock_llm.return_value = '{"remise_percent": 15}'
        remise, ok = _extract_llm_remise("some page text")
        self.assertTrue(ok)
        self.assertEqual(remise, Decimal("0.15"))

    @patch("apps.tariff_scraper.services.dp_verification._call_lmstudio")
    def test_parses_null_as_no_remise(self, mock_llm):
        mock_llm.return_value = '{"remise_percent": null}'
        remise, ok = _extract_llm_remise("some page text")
        self.assertTrue(ok)
        self.assertIsNone(remise)

    @patch("apps.tariff_scraper.services.dp_verification._call_lmstudio")
    def test_extracts_json_even_with_surrounding_chatter(self, mock_llm):
        mock_llm.return_value = 'Sure! {"remise_percent": 20} — hope that helps.'
        remise, ok = _extract_llm_remise("some page text")
        self.assertTrue(ok)
        self.assertEqual(remise, Decimal("0.20"))

    @patch("apps.tariff_scraper.services.dp_verification._call_lmstudio", return_value=None)
    def test_llm_down_is_not_ok(self, _mock_llm):
        remise, ok = _extract_llm_remise("some page text")
        self.assertFalse(ok)
        self.assertIsNone(remise)

    @patch("apps.tariff_scraper.services.dp_verification._call_lmstudio")
    def test_garbage_response_is_not_ok(self, mock_llm):
        mock_llm.return_value = "I cannot help with that."
        remise, ok = _extract_llm_remise("some page text")
        self.assertFalse(ok)

    @patch("apps.tariff_scraper.services.dp_verification._call_lmstudio")
    def test_out_of_range_percentage_is_not_ok(self, mock_llm):
        mock_llm.return_value = '{"remise_percent": 150}'
        remise, ok = _extract_llm_remise("some page text")
        self.assertFalse(ok)
        self.assertIsNone(remise)


# ---------------------------------------------------------------------------
# End-to-end verify_dp_remise()
# ---------------------------------------------------------------------------

class VerifyEndToEndTest(TestCase):
    @patch("apps.tariff_scraper.services.dp_verification._call_lmstudio")
    def test_agreement_on_stated_page(self, mock_llm):
        mock_llm.return_value = '{"remise_percent": 15}'
        result = verify_dp_remise(STATED_HTML, "lacanau")
        self.assertTrue(result.checked)
        self.assertTrue(result.match)
        self.assertEqual(result.regex_remise, Decimal("0.15"))
        self.assertEqual(result.regex_derivation, DERIVATION_STATED)
        self.assertEqual(result.llm_remise, Decimal("0.15"))

    @patch("apps.tariff_scraper.services.dp_verification._call_lmstudio")
    def test_mismatch_when_llm_disagrees(self, mock_llm):
        mock_llm.return_value = '{"remise_percent": 25}'
        result = verify_dp_remise(STATED_HTML, "lacanau")
        self.assertTrue(result.checked)
        self.assertFalse(result.match)

    @patch("apps.tariff_scraper.services.dp_verification._call_lmstudio")
    def test_assumed_default_page_drift_is_caught(self, mock_llm):
        # Regex only sees "possible" -> assumes 15%. LLM finds the real
        # (now-explicit, different) number on the "same" page text.
        mock_llm.return_value = '{"remise_percent": 20}'
        result = verify_dp_remise(ASSUMED_HTML, "lacanau")
        self.assertTrue(result.checked)
        self.assertEqual(result.regex_derivation, DERIVATION_ASSUMED)
        self.assertFalse(result.match)

    @patch("apps.tariff_scraper.services.dp_verification._call_lmstudio")
    def test_no_mention_agrees_when_llm_also_finds_nothing(self, mock_llm):
        mock_llm.return_value = '{"remise_percent": null}'
        result = verify_dp_remise(NO_MENTION_HTML, "lacanau")
        self.assertTrue(result.checked)
        self.assertTrue(result.match)

    @patch("apps.tariff_scraper.services.dp_verification._call_lmstudio", return_value=None)
    def test_llm_unreachable_is_unable_to_verify_not_a_mismatch(self, _mock_llm):
        result = verify_dp_remise(STATED_HTML, "lacanau")
        self.assertFalse(result.checked)
        self.assertTrue(result.match)  # never a false-positive mismatch

    def test_never_raises_on_unexpected_error(self):
        with patch(
            "apps.tariff_scraper.services.dp_verification._extract_dp_remise_info",
            side_effect=RuntimeError("boom"),
        ):
            result = verify_dp_remise(STATED_HTML, "lacanau")
        self.assertFalse(result.checked)
        self.assertTrue(result.match)
        self.assertIn("errored", result.note.lower())


# ---------------------------------------------------------------------------
# scrape_village() integration — must not break existing scraping behaviour
# ---------------------------------------------------------------------------

class ScrapeVillageIntegrationTest(TestCase):
    def _pc_band(self, derivation="scraped"):
        return RawPriceBand(
            formule="PC",
            source_page="price_grid",
            date_label="25/07 au 15/08/26",
            date_start=date(2026, 7, 25),
            date_end=date(2026, 8, 15),
            scraped_price=Decimal("763"),
            is_available=True,
            nb_adults=1,
            derivation="scraped",
        )

    def _dp_band(self, derivation):
        return RawPriceBand(
            formule="DP",
            source_page="price_grid",
            date_label="25/07 au 15/08/26",
            date_start=date(2026, 7, 25),
            date_end=date(2026, 8, 15),
            scraped_price=Decimal("648"),
            is_available=True,
            nb_adults=1,
            derivation=derivation,
        )

    @patch("apps.tariff_scraper.services.dp_verification.verify_dp_remise")
    @patch("apps.tariff_scraper.services.scraper.scrape_price_grid_http")
    def test_verification_called_when_dp_was_derived(self, mock_http, mock_verify):
        mock_http.return_value = HttpGridScrapeResult(
            bands=[self._pc_band(), self._dp_band(DERIVATION_ASSUMED)],
            html_len=100,
            html=STATED_HTML,
            has_grille_markers=True,
        )
        mock_verify.return_value = DpVerificationResult(village_id="lacanau", checked=True, match=True)
        result = scrape_village("lacanau", "https://example.com/lacanau")
        mock_verify.assert_called_once()
        self.assertIsNotNone(result.dp_verification)
        self.assertTrue(result.dp_verification.match)

    @patch("apps.tariff_scraper.services.dp_verification.verify_dp_remise")
    @patch("apps.tariff_scraper.services.scraper.scrape_price_grid_http")
    def test_verification_not_called_when_dp_directly_scraped(self, mock_http, mock_verify):
        # DP came straight off the grille (derivation="scraped") — nothing
        # to verify, the static remise rule was never used.
        mock_http.return_value = HttpGridScrapeResult(
            bands=[self._pc_band(), self._dp_band("scraped")],
            html_len=100,
            html=STATED_HTML,
            has_grille_markers=True,
        )
        result = scrape_village("lacanau", "https://example.com/lacanau")
        mock_verify.assert_not_called()
        self.assertIsNone(result.dp_verification)

    @patch("apps.tariff_scraper.services.dp_verification.verify_dp_remise")
    @patch("apps.tariff_scraper.services.scraper.scrape_price_grid_http")
    def test_verification_error_never_breaks_the_scrape(self, mock_http, mock_verify):
        mock_http.return_value = HttpGridScrapeResult(
            bands=[self._pc_band(), self._dp_band(DERIVATION_ASSUMED)],
            html_len=100,
            html=STATED_HTML,
            has_grille_markers=True,
        )
        mock_verify.side_effect = RuntimeError("LM Studio exploded")
        result = scrape_village("lacanau", "https://example.com/lacanau")
        # Scrape itself must still succeed with its priced bands intact.
        self.assertIsNone(result.dp_verification)
        priced = [b for b in result.bands if b.is_available and b.scraped_price is not None]
        self.assertEqual(len(priced), 2)

    @patch("apps.tariff_scraper.services.dp_verification.verify_dp_remise")
    @patch("apps.tariff_scraper.services.scraper.scrape_price_grid_http")
    def test_verification_not_called_when_nothing_priced(self, mock_http, mock_verify):
        mock_http.return_value = HttpGridScrapeResult(
            bands=[],
            html_len=100,
            html=NO_MENTION_HTML,
            has_grille_markers=True,
        )
        import builtins
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in ("playwright.sync_api", "playwright"):
                raise ImportError("playwright disabled in test")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            scrape_village("lacanau", "https://example.com/lacanau")
        mock_verify.assert_not_called()


# ---------------------------------------------------------------------------
# tasks.py dispatch — additive alert, must not change `ok`
# ---------------------------------------------------------------------------

class TaskDispatchTest(TestCase):
    @patch("apps.tariff_scraper.services.alerts.notify_dp_remise_mismatch")
    @patch("apps.tariff_scraper.services.alerts.notify_scrape_success")
    @patch("apps.tariff_scraper.services.alerts.notify_format_change")
    @patch("apps.tariff_scraper.services.alerts.notify_scrape_failure")
    @patch("apps.tariff_scraper.services.tarif_builder.build_tarifs_from_scrape")
    @patch("apps.tariff_scraper.services.scraper.scrape_village")
    @patch("apps.tariff_scraper.tasks.get_village_url", return_value="https://example.com/lacanau")
    def test_mismatch_fires_alert_without_changing_ok(
        self, _mock_url, mock_scrape, mock_build, mock_fail, mock_fc, mock_success, mock_mismatch,
    ):
        from apps.tariff_scraper.tasks import task_scrape_village_tariffs
        from apps.tariff_scraper.services.scraper import VillageScrapeResult

        scrape_result = VillageScrapeResult(village_id="lacanau", url="https://example.com/lacanau")
        scrape_result.bands = [
            RawPriceBand(
                formule="PC", source_page="price_grid", date_label="x",
                date_start=date(2026, 7, 25), date_end=date(2026, 8, 15),
                scraped_price=Decimal("763"), is_available=True, nb_adults=1,
            )
        ]
        scrape_result.dp_verification = DpVerificationResult(
            village_id="lacanau", checked=True, match=False,
            regex_remise=Decimal("0.15"), regex_derivation=DERIVATION_ASSUMED,
            llm_remise=Decimal("0.20"), note="mismatch",
        )
        mock_scrape.return_value = scrape_result

        class _BuildResult:
            snapshots_created = 1
            approval_id = 42
            bands_proposed = 1
            tarifs_created = 0
            tarifs_deactivated = 0
            skipped_unavailable = 0
            skipped_no_price = 0
            skipped_no_dates = 0
            errors: list = []

        mock_build.return_value = _BuildResult()

        # Bound shared_task — calling it directly (not .delay()) runs
        # synchronously and Celery injects `self` for us.
        summary = task_scrape_village_tariffs("lacanau")

        self.assertTrue(summary["ok"])  # unaffected by the DP mismatch
        mock_mismatch.assert_called_once()
        mock_success.assert_called_once()  # normal success alert still fires

    @patch("apps.tariff_scraper.services.alerts.notify_dp_remise_mismatch")
    @patch("apps.tariff_scraper.services.alerts.notify_scrape_success")
    @patch("apps.tariff_scraper.services.alerts.notify_format_change")
    @patch("apps.tariff_scraper.services.alerts.notify_scrape_failure")
    @patch("apps.tariff_scraper.services.tarif_builder.build_tarifs_from_scrape")
    @patch("apps.tariff_scraper.services.scraper.scrape_village")
    @patch("apps.tariff_scraper.tasks.get_village_url", return_value="https://example.com/talloires")
    def test_success_without_dp_verification_does_not_retry(
        self, _mock_url, mock_scrape, mock_build, mock_fail, mock_fc, mock_success, mock_mismatch,
    ):
        from apps.tariff_scraper.tasks import task_scrape_village_tariffs
        from apps.tariff_scraper.services.scraper import VillageScrapeResult

        scrape_result = VillageScrapeResult(village_id="talloires", url="https://example.com/talloires")
        scrape_result.bands = [
            RawPriceBand(
                formule="PC", source_page="price_grid", date_label="x",
                date_start=date(2026, 7, 25), date_end=date(2026, 8, 15),
                scraped_price=Decimal("763"), is_available=True, nb_adults=1,
            )
        ]
        mock_scrape.return_value = scrape_result

        class _BuildResult:
            snapshots_created = 1
            approval_id = 69
            bands_proposed = 1
            tarifs_created = 0
            tarifs_deactivated = 0
            skipped_unavailable = 0
            skipped_no_price = 0
            skipped_no_dates = 0
            errors: list = []

        mock_build.return_value = _BuildResult()

        summary = task_scrape_village_tariffs("talloires")

        self.assertTrue(summary["ok"])
        self.assertIsNone(summary["dp_verification"])
        mock_mismatch.assert_not_called()
        mock_fail.assert_not_called()
        mock_success.assert_called_once()
