"""Phase 4 tests — Tariff scraper alerts + PS-01…PS-09 remediation.

Coverage:
  ALERTS / FORMAT CHANGE (moved from apps/tariff_scraper/tests.py):
  - FormatChangeInfo, alert classification, FormatChangeLog, notifications
  - Grille parsing parity (Lacanau PC / Carcans LOC)
  - Builder, approval, get_active_tarif, stay-estimate bridge

  PS DEFECTS:
  - PS-01 / F-01 / F-02  cross-year + year-less date parsing
  - PS-02  PC/LOC header right-alignment
  - PS-03  struck/promo price preference on grille HTML path
  - PS-04  not-offered vs parse-failed notes
  - PS-05  DP derivation markers
  - PS-06  per-formule scrape cascade
  - PS-07  unit strings must not parse as prices
  - PS-08  genuine 0 € is a valid price
  - PS-09  widget occupancy read (not hardcoded 2)

Run:
  cd vtf/api
  pytest tests/test_phase4.py -v
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings

from apps.tariff_scraper.models import (
    CHANGE_TYPE_CHOICES,
    FormatChangeLog,
    PriceSnapshot,
    TariffApproval,
    VillageTarif,
)
from apps.tariff_scraper.services.scraper import (
    EXPECTED_GRILLE_MARKERS,
    FormatChangeInfo,
    HttpGridScrapeResult,
    RawPriceBand,
    VillageScrapeResult,
    parse_grille_table,
    parse_vtf_period_cell,
)
from apps.tariff_scraper.services.alerts import (
    _RED,
    _YELLOW,
    _GREEN,
    _classify_failure as alert_classify_failure,
    _classify_format_change as alert_classify_format_change,
    format_errors_by_step,
    notify_batch_summary,
    notify_format_change,
    notify_scrape_failure,
    notify_scrape_success,
    parse_pipeline_error,
)
from apps.tariff_scraper.tasks import _is_actionable_format_change, _log_format_change


# ---------------------------------------------------------------------------
# FormatChangeInfo dataclass tests
# ---------------------------------------------------------------------------

class FormatChangeInfoTest(TestCase):
    """Test the FormatChangeInfo dataclass."""

    def test_defaults(self):
        fc = FormatChangeInfo()
        self.assertFalse(fc.change_detected)
        self.assertEqual(fc.change_type, "")
        self.assertEqual(fc.expected_markers, [])
        self.assertEqual(fc.found_markers, [])
        self.assertEqual(fc.missing_markers, [])
        self.assertEqual(fc.html_length, 0)
        self.assertEqual(fc.table_count, 0)
        self.assertEqual(fc.bands_scraped, 0)
        self.assertEqual(fc.priced_bands, 0)

    def test_with_values(self):
        fc = FormatChangeInfo(
            change_detected=True,
            change_type="marker_missing",
            expected_markers=["grille tarifaire", "pension complète"],
            found_markers=[],
            missing_markers=["grille tarifaire", "pension complète"],
            html_length=50000,
            table_count=0,
            bands_scraped=0,
            priced_bands=0,
        )
        self.assertTrue(fc.change_detected)
        self.assertEqual(fc.change_type, "marker_missing")
        self.assertEqual(len(fc.missing_markers), 2)


# ---------------------------------------------------------------------------
# Alert classification tests — colour scheme verification
# ---------------------------------------------------------------------------

class AlertClassificationTest(TestCase):
    """Test that alert classification returns correct colours.

    Colour scheme:
      🔴 RED   — HTTP fetch failed / wrong URL / blocked
      🔴 RED   — Page loaded but zero prices found (layout changed)
      🟡 YELLOW — Prices scraped but dates/prices couldn't be parsed
      🟡 YELLOW — Some data got through but with errors
      🔴 RED   — Unhandled exception crash
    """

    def test_hard_fetch_failure_is_red(self):
        """HTTP fetch failed / wrong URL / blocked → 🔴 RED."""
        summary = {
            "village_id": "test",
            "url": "http://bad-url",
            "bands_scraped": 0,
            "priced_bands": 0,
            "bands_proposed": 0,
            "scrape_errors": [
                "Step 1 (HTTP Fetch) | scraper.py → scrape_price_grid_http() | "
                "HTTP 404 Client Error"
            ],
            "build_errors": [],
        }
        title, reason, colour = alert_classify_failure(summary)
        self.assertEqual(colour, _RED)
        self.assertIn("FAILED", title)
        self.assertIn("Step 1", reason)
        self.assertIn("scrape_price_grid_http()", reason)
        self.assertIn("HTTP 404", reason)

    def test_zero_prices_is_red(self):
        """Page loaded but zero prices found (layout changed) → 🔴 RED."""
        summary = {
            "village_id": "test",
            "url": "http://valid-url",
            "bands_scraped": 0,
            "priced_bands": 0,
            "bands_proposed": 0,
            "scrape_errors": [
                "Step 2 (HTML Grid Parse) | scraper.py → scrape_price_grid_http() | "
                "Page loaded but no price grid markers found",
                "Step 7 (Validation) | scraper.py → scrape_village() | "
                "No priced tariff bands extracted from any source",
            ],
            "build_errors": [],
        }
        title, reason, colour = alert_classify_failure(summary)
        self.assertEqual(colour, _RED)
        self.assertIn("Zero prices", title)
        # Reason should point at the failing step + code, not a generic HTTP message
        self.assertIn("Step 7", reason)
        self.assertIn("scrape_village()", reason)

    def test_layout_change_with_multiple_steps_is_not_http_failed(self):
        """Multi-step empty scrape must not be mislabelled as HTTP fetch failure."""
        summary = {
            "village_id": "test",
            "url": "http://valid-url",
            "bands_scraped": 0,
            "priced_bands": 0,
            "bands_proposed": 0,
            "scrape_errors": [
                "Step 1 (HTTP Fetch) | scraper.py → scrape_price_grid_http() | timeout",
                "Step 2 (HTML Grid Parse) | scraper.py → scrape_price_grid_http() | "
                "no markers",
                "Step 7 (Validation) | scraper.py → scrape_village() | no priced bands",
            ],
            "build_errors": [],
        }
        title, reason, colour = alert_classify_failure(summary)
        self.assertEqual(colour, _RED)
        self.assertNotIn("FAILED", title)  # not the hard-fetch title
        self.assertIn("Zero prices", title)
        self.assertIn("Step 7", reason)

    def test_parse_failure_is_yellow(self):
        """Prices scraped but dates/prices couldn't be parsed → 🟡 YELLOW."""
        summary = {
            "village_id": "test",
            "url": "http://valid-url",
            "bands_scraped": 5,
            "priced_bands": 0,
            "bands_proposed": 0,
            "scrape_errors": [],
            "build_errors": [
                "Step 8 (Tariff Builder) | tarif_builder.py → build_tarifs_from_scrape() | "
                "Date parse failed"
            ],
        }
        title, reason, colour = alert_classify_failure(summary)
        self.assertEqual(colour, _YELLOW)
        self.assertIn("none proposed", title)
        self.assertIn("Step 8", reason)

    def test_partial_with_errors_is_yellow(self):
        """Some data got through but with errors → 🟡 YELLOW."""
        summary = {
            "village_id": "test",
            "url": "http://valid-url",
            "bands_scraped": 10,
            "priced_bands": 3,
            "bands_proposed": 2,
            "scrape_errors": [],
            "build_errors": [
                "Step 8 (Tariff Builder) | tarif_builder.py → build_tarifs_from_scrape() | "
                "Some skipped"
            ],
        }
        title, reason, colour = alert_classify_failure(summary)
        self.assertEqual(colour, _YELLOW)
        self.assertIn("Partial", title)

    def test_hard_crash_is_red(self):
        """Unhandled exception crash → 🔴 RED."""
        summary = {
            "village_id": "test",
            "url": "http://valid-url",
            "bands_scraped": 0,
            "priced_bands": 0,
            "bands_proposed": 0,
            "scrape_errors": [
                "Step 0 (Task Crash) | tasks.py → task_scrape_village_tariffs() | "
                "Unhandled exception: ConnectionResetError"
            ],
            "build_errors": [],
        }
        title, reason, colour = alert_classify_failure(summary)
        self.assertEqual(colour, _RED)
        self.assertIn("CRASHED", title)
        self.assertIn("task_scrape_village_tariffs()", reason)


class PipelineErrorFormattingTest(TestCase):
    """Step | source | reason parsing for Discord embeds."""

    def test_parse_standard_step_error(self):
        parsed = parse_pipeline_error(
            "Step 4 (Playwright Grid Parse) | scraper.py → scrape_price_grid() | "
            "Page rendered but no price table found in DOM."
        )
        self.assertEqual(parsed["step"], "Step 4 (Playwright Grid Parse)")
        self.assertEqual(parsed["source"], "scraper.py → scrape_price_grid()")
        self.assertIn("no price table", parsed["reason"])

    def test_format_errors_by_step_includes_source_and_reason(self):
        text = format_errors_by_step([
            "Step 1 (HTTP Fetch) | scraper.py → scrape_price_grid_http() | HTTP 403",
            "Step 7 (Validation) | scraper.py → scrape_village() | No priced bands",
        ])
        self.assertIn("**Step 1 (HTTP Fetch)**", text)
        self.assertIn("`scraper.py → scrape_price_grid_http()`", text)
        self.assertIn("HTTP 403", text)
        self.assertIn("**Step 7 (Validation)**", text)


# ---------------------------------------------------------------------------
# Format change classification tests
# ---------------------------------------------------------------------------

class FormatChangeClassificationTest(TestCase):
    """Test format change alert classification."""

    def test_marker_missing_is_red(self):
        """All markers missing → 🔴 RED."""
        summary = {
            "village_id": "test",
            "format_change": {
                "change_detected": True,
                "change_type": "marker_missing",
                "expected_markers": ["grille tarifaire", "pension complète"],
                "found_markers": [],
                "missing_markers": ["grille tarifaire", "pension complète"],
                "html_length": 50000,
                "table_count": 0,
                "bands_scraped": 0,
                "priced_bands": 0,
            },
        }
        title, reason, colour = alert_classify_format_change(summary)
        self.assertEqual(colour, _RED)
        self.assertIn("FORMAT CHANGE", title)

    def test_zero_prices_is_red(self):
        """Zero prices extracted → 🔴 RED."""
        summary = {
            "village_id": "test",
            "format_change": {
                "change_detected": True,
                "change_type": "zero_prices",
                "expected_markers": ["grille tarifaire"],
                "found_markers": ["grille tarifaire"],
                "missing_markers": [],
                "html_length": 50000,
                "table_count": 2,
                "bands_scraped": 0,
                "priced_bands": 0,
            },
        }
        title, reason, colour = alert_classify_format_change(summary)
        self.assertEqual(colour, _RED)
        self.assertIn("FORMAT CHANGE", title)

    def test_partial_is_yellow(self):
        """Partial format change → 🟡 YELLOW."""
        summary = {
            "village_id": "test",
            "format_change": {
                "change_detected": True,
                "change_type": "partial",
                "expected_markers": ["grille tarifaire"],
                "found_markers": ["grille tarifaire"],
                "missing_markers": [],
                "html_length": 50000,
                "table_count": 2,
                "bands_scraped": 5,
                "priced_bands": 2,
            },
        }
        title, reason, colour = alert_classify_format_change(summary)
        self.assertEqual(colour, _YELLOW)
        self.assertIn("PARTIAL", title)


# ---------------------------------------------------------------------------
# FormatChangeLog persistence tests
# ---------------------------------------------------------------------------

class FormatChangeLogPersistenceTest(TestCase):
    """Test that _log_format_change persists to the database."""

    def test_logs_marker_missing_change(self):
        """Format change with marker_missing should create a log entry."""
        summary = {
            "village_id": "lacanau",
            "url": "http://test-url",
            "scrape_errors": [],
            "build_errors": [],
            "format_change": {
                "change_detected": True,
                "change_type": "marker_missing",
                "expected_markers": ["grille tarifaire", "pension complète"],
                "found_markers": [],
                "missing_markers": ["grille tarifaire", "pension complète"],
                "html_length": 50000,
                "table_count": 0,
                "bands_scraped": 0,
                "priced_bands": 0,
            },
        }

        with patch("apps.tariff_scraper.models.FormatChangeLog.objects") as mock_objects:
            mock_objects.create.return_value = MagicMock()

            _log_format_change(summary)

            mock_objects.create.assert_called_once_with(
                village_id="lacanau",
                change_type="marker_missing",
                source_url="http://test-url",
                expected_markers=["grille tarifaire", "pension complète"],
                found_markers=[],
                missing_markers=["grille tarifaire", "pension complète"],
                html_length=50000,
                table_count=0,
                bands_scraped=0,
                priced_bands=0,
                errors=[],
                html_snippet="",
            )

    def test_logs_hard_failure_change(self):
        """Hard failure should be logged as hard_failure type."""
        summary = {
            "village_id": "test",
            "url": "http://bad",
            "scrape_errors": ["HTTP 404"],
            "build_errors": [],
            "bands_scraped": 0,
            "format_change": {
                "change_detected": True,
                "change_type": "partial",
                "expected_markers": [],
                "found_markers": [],
                "missing_markers": [],
                "html_length": 0,
                "table_count": 0,
                "bands_scraped": 0,
                "priced_bands": 0,
            },
        }

        with patch("apps.tariff_scraper.models.FormatChangeLog.objects") as mock_objects:
            mock_objects.create.return_value = MagicMock()

            _log_format_change(summary)

            call_kwargs = mock_objects.create.call_args[1]
            # When bands_scraped=0 and scrape_errors present, should be hard_failure
            self.assertEqual(call_kwargs["change_type"], "hard_failure")
            self.assertEqual(call_kwargs["errors"], ["HTTP 404"])

    def test_skips_when_no_format_change(self):
        """No format change detected → no log entry."""
        summary = {
            "village_id": "test",
            "format_change": None,
        }
        with patch("apps.tariff_scraper.models.FormatChangeLog.objects") as mock_objects:
            _log_format_change(summary)
            mock_objects.create.assert_not_called()

    def test_skips_when_change_not_detected(self):
        """change_detected=False → no log entry."""
        summary = {
            "village_id": "test",
            "format_change": {
                "change_detected": False,
                "change_type": "",
            },
        }
        with patch("apps.tariff_scraper.models.FormatChangeLog.objects") as mock_objects:
            _log_format_change(summary)
            mock_objects.create.assert_not_called()

    def test_successful_header_misalignment_is_not_actionable(self):
        """Successful priced scrapes should not alert/log header alignment notes."""
        summary = {
            "village_id": "lacanau",
            "ok": True,
            "priced_bands": 36,
            "format_change": {
                "change_detected": True,
                "change_type": "header_misalignment",
            },
        }

        self.assertFalse(_is_actionable_format_change(summary))
        with patch("apps.tariff_scraper.models.FormatChangeLog.objects") as mock_objects:
            _log_format_change(summary)
            mock_objects.create.assert_not_called()

    def test_failed_header_misalignment_is_still_actionable(self):
        """Header issues still alert/log when they block priced data."""
        summary = {
            "village_id": "lacanau",
            "ok": False,
            "scrape_errors": ["No priced tariff bands"],
            "build_errors": [],
            "bands_scraped": 0,
            "format_change": {
                "change_detected": True,
                "change_type": "header_misalignment",
                "expected_markers": [],
                "found_markers": [],
                "missing_markers": [],
                "html_length": 1000,
                "table_count": 1,
                "bands_scraped": 0,
                "priced_bands": 0,
            },
        }

        self.assertTrue(_is_actionable_format_change(summary))
        with patch("apps.tariff_scraper.models.FormatChangeLog.objects") as mock_objects:
            _log_format_change(summary)
            mock_objects.create.assert_called_once()


# ---------------------------------------------------------------------------
# VillageScrapeResult format change propagation tests
# ---------------------------------------------------------------------------

class VillageScrapeResultFormatChangeTest(TestCase):
    """Test that VillageScrapeResult correctly holds format change info."""

    def test_no_format_change_by_default(self):
        result = VillageScrapeResult(village_id="test", url="http://test")
        self.assertIsNone(result.format_change)

    def test_format_change_can_be_set(self):
        fc = FormatChangeInfo(
            change_detected=True,
            change_type="zero_prices",
            html_length=50000,
        )
        result = VillageScrapeResult(
            village_id="test",
            url="http://test",
            format_change=fc,
        )
        self.assertTrue(result.format_change.change_detected)
        self.assertEqual(result.format_change.change_type, "zero_prices")


# ---------------------------------------------------------------------------
# Expected markers tests
# ---------------------------------------------------------------------------

class ExpectedMarkersTest(TestCase):
    """Test the EXPECTED_GRILLE_MARKERS constant."""

    def test_markers_defined(self):
        self.assertIsInstance(EXPECTED_GRILLE_MARKERS, list)
        self.assertGreater(len(EXPECTED_GRILLE_MARKERS), 0)

    def test_contains_key_markers(self):
        self.assertIn("grille tarifaire", EXPECTED_GRILLE_MARKERS)
        self.assertIn("pension complète", EXPECTED_GRILLE_MARKERS)
        self.assertIn("location", EXPECTED_GRILLE_MARKERS)


# ---------------------------------------------------------------------------
# FormatChangeLog model tests
# ---------------------------------------------------------------------------

class FormatChangeLogModelTest(TestCase):
    """Test the FormatChangeLog model."""

    def test_change_type_choices(self):
        self.assertEqual(len(CHANGE_TYPE_CHOICES), 5)
        types = [c[0] for c in CHANGE_TYPE_CHOICES]
        self.assertIn("marker_missing", types)
        self.assertIn("zero_prices", types)
        self.assertIn("parse_failure", types)
        self.assertIn("partial", types)
        self.assertIn("hard_failure", types)

    def test_str_representation(self):
        """Test __str__ format."""
        # We can't create a real object without a Village FK,
        # but we can test the format
        from apps.tariff_scraper.models import FormatChangeLog
        # Just verify the model has __str__
        self.assertTrue(hasattr(FormatChangeLog, "__str__"))


# ---------------------------------------------------------------------------
# Notification function existence tests (smoke tests)
# ---------------------------------------------------------------------------

class NotificationFunctionsTest(TestCase):
    """Smoke tests that notification functions exist and are callable."""

    def test_notify_scrape_failure_exists(self):
        self.assertTrue(callable(notify_scrape_failure))

    def test_notify_format_change_exists(self):
        self.assertTrue(callable(notify_format_change))

    def test_notify_scrape_success_exists(self):
        self.assertTrue(callable(notify_scrape_success))

    def test_notify_batch_summary_exists(self):
        self.assertTrue(callable(notify_batch_summary))

    @override_settings(DISCORD_WEBHOOK="", TARIFF_SCRAPER_NOTIFY_SUCCESS=True)
    def test_notify_scrape_success_no_webhook(self):
        """Green success path should not raise when webhook is empty."""
        notify_scrape_success({
            "village_id": "lacanau",
            "url": "http://test",
            "priced_bands": 12,
            "bands_proposed": 10,
            "bands_scraped": 12,
            "approval_id": 1,
            "scrape_errors": [],
            "build_errors": [],
        })

    @override_settings(DISCORD_WEBHOOK="")
    def test_notify_scrape_failure_no_webhook(self):
        """Should not raise when DISCORD_WEBHOOK is empty."""
        summary = {
            "village_id": "test",
            "url": "http://test",
            "bands_scraped": 0,
            "priced_bands": 0,
            "bands_proposed": 0,
            "scrape_errors": [
                "Step 1 (HTTP Fetch) | scraper.py → scrape_price_grid_http() | test error"
            ],
            "build_errors": [],
        }
        # Should not raise
        notify_scrape_failure(summary)

    @override_settings(DISCORD_WEBHOOK="")
    def test_notify_batch_summary_no_webhook(self):
        """Should not raise when DISCORD_WEBHOOK is empty."""
        results = [
            {"village_id": "a", "ok": True, "priced_bands": 5},
            {"village_id": "b", "ok": False, "priced_bands": 0},
        ]
        # Should not raise
        notify_batch_summary(results)


# ---------------------------------------------------------------------------
# Colour constant tests
# ---------------------------------------------------------------------------

class ColourConstantsTest(TestCase):
    """Verify Discord embed colour constants."""

    def test_red(self):
        self.assertEqual(_RED, 0xED4245)

    def test_yellow(self):
        self.assertEqual(_YELLOW, 0xFEE75C)

    def test_green(self):
        self.assertEqual(_GREEN, 0x57F287)



################################################################################################
"""Tests for tariff_scraper: grille parsing, builder, query, pricing bridge.

Live website golden matrices (captured Jul 2026 from vtf-vacances.com):
  • Lacanau La Forestière — PC adult weekly grille + 15% DP remise
  • Carcans Les Oyats — LOC unit weekly grille
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Village
from apps.tariff_scraper.models import (
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    PriceSnapshot,
    TariffApproval,
    VillageTarif,
)
from apps.tariff_scraper.services.approval import (
    approve_tariff_approval,
    reject_tariff_approval,
)
from apps.tariff_scraper.services.scraper import (
    RawPriceBand,
    VillageScrapeResult,
    parse_grille_table,
    parse_vtf_period_cell,
)
from apps.tariff_scraper.services.tarif_builder import build_tarifs_from_scrape
from apps.tariff_scraper.services.tarif_query import get_active_tarif
from apps.tariff_scraper.services.village_urls import VILLAGE_URLS, get_village_url


def _build_and_approve(scrape: VillageScrapeResult, *, sync_fixture: bool = False):
    """Helper: stage scrape then apply pending approval (tests that need live tarifs)."""
    build = build_tarifs_from_scrape(scrape)
    assert not build.errors, build.errors
    assert build.approval_id is not None
    approval = TariffApproval.objects.get(pk=build.approval_id)
    return approve_tariff_approval(approval, sync_fixture=sync_fixture)


# ─── Live-site golden matrices ───────────────────────────────────────────────

LACANAU_PC_ROWS = [
    [
        "Séjour semaine en pension complète du 1er jour 17h au 8e jour 10h",
        "Adultes",
        "11 à - 16 ans",
        "6 à - 11 ans",
        "4 à - 6 ans",
        "1 à - 4 ans",
    ],
    ["Pâques", "11/04 au 2/05/26", "469 €", "420 €", "378 €", "Gratuit*"],
    [
        "Hors vacances",
        "2/05 au 4/07, 29/08 au 3/10/26",
        "581 €",
        "525 €",
        "462 €",
        "350 €",
        "Gratuit",
    ],
    ["Eté", "4 au 11/07, 22 au 29/08/26", "728 €", "658 €", "581 €", "434 €", "217 €"],
    ["11 au 25/07, 15 au 22/08/26", "903 €", "812 €", "721 €", "539 €", "273 €"],
    ["25/07 au 15/08/26", "945 €", "854 €", "756 €", "567 €", "287 €"],
    ["Toussaint", "17/10 au 1/11/26", "455 €", "413 €", "364 €", "Gratuit*"],
]
LACANAU_PAGE_TEXT = (
    "1/2 pension possible = 15% de remise sur le tarif en pension complète"
)

CARCANS_LOC_ROWS = [
    [
        "Séjour semaine en location du 1er jour 17h au 8e jour 10h",
        "2 pièces 4 pers.",
        "3 pièces 4/6 pers.",
        "Duplex 3 pièces 4/6 pers.",
    ],
    ["Hors vacances", "7/05 au 4/07, 29/08 au 20/09/26", "483 €", "553 €", "574 €"],
    ["Eté", "4 au 11/07/26", "714 €", "868 €", "924 €"],
    ["11/07 au 1/08/26", "1022 €", "1155 €", "1218 €"],
    ["1 au 15/08/26", "1260 €", "1540 €", "1617 €"],
    ["15 au 22/08/26", "1162 €", "1393 €", "1470 €"],
    ["22 au 29/08/26", "770 €", "931 €", "1008 €"],
]


class ParseVtfPeriodCellTests(TestCase):
    def test_single_range_with_year(self):
        ranges = parse_vtf_period_cell("11/04 au 2/05/26")
        self.assertEqual(ranges, [(date(2026, 4, 11), date(2026, 5, 2))])

    def test_comma_separated_ranges(self):
        ranges = parse_vtf_period_cell("2/05 au 4/07, 29/08 au 3/10/26")
        self.assertEqual(len(ranges), 2)
        self.assertEqual(ranges[0], (date(2026, 5, 2), date(2026, 7, 4)))
        self.assertEqual(ranges[1], (date(2026, 8, 29), date(2026, 10, 3)))

    def test_day_only_start(self):
        ranges = parse_vtf_period_cell("4 au 11/07/26")
        self.assertEqual(ranges, [(date(2026, 7, 4), date(2026, 7, 11))])


class ParseGrilleLacanauParityTests(TestCase):
    """Parser must reproduce live Lacanau PC adult prices from the grille."""

    def setUp(self):
        self.bands = parse_grille_table(LACANAU_PC_ROWS, page_text=LACANAU_PAGE_TEXT)
        self.pc = [b for b in self.bands if b.formule == "PC"]
        self.dp = [b for b in self.bands if b.formule == "DP"]

    def test_pc_peak_summer_matches_website(self):
        peak = next(
            b for b in self.pc
            if b.date_start == date(2026, 7, 25) and b.date_end == date(2026, 8, 15)
        )
        self.assertEqual(peak.scraped_price, Decimal("945"))

    def test_pc_paques_matches_website(self):
        band = next(b for b in self.pc if b.date_start == date(2026, 4, 11))
        self.assertEqual(band.scraped_price, Decimal("469"))

    def test_pc_paques_preserves_blank_and_gratuit_child_cells(self):
        blank_child = next(
            b for b in self.pc
            if b.date_start == date(2026, 4, 11) and b.unit_type.startswith("4 ")
        )
        free_child = next(
            b for b in self.pc
            if b.date_start == date(2026, 4, 11) and b.unit_type.startswith("1 ")
        )

        self.assertEqual(blank_child.scraped_price, Decimal("0"))
        self.assertEqual(blank_child.raw_cell_text, "")
        self.assertEqual(free_child.scraped_price, Decimal("0"))
        self.assertEqual(free_child.raw_cell_text, "Gratuit*")

    def test_pc_hors_vacances_expands_two_windows(self):
        # 581 € is both an Adultes price and the "6 à - 11 ans" child price on
        # this grid, and child columns now produce PC bands alongside adults
        # (see test_pc_uses_adultes_column_when_not_first_price_column below),
        # so filtering by price alone matches both unit types per window.
        # Restrict to the adult band to keep this test's original intent
        # (asserting the two hors-vacances window starts for the Adultes PC
        # price) — consumers that need "PC bands for a price" in general must
        # also filter on unit_type to avoid double-counting.
        hv = [
            b for b in self.pc
            if b.scraped_price == Decimal("581") and b.unit_type == "Adultes"
        ]
        self.assertEqual(len(hv), 2)
        starts = {b.date_start for b in hv}
        self.assertEqual(starts, {date(2026, 5, 2), date(2026, 8, 29)})

    def test_dp_derived_at_15_percent(self):
        self.assertEqual(len(self.dp), len(self.pc))
        paques_dp = next(b for b in self.dp if b.date_start == date(2026, 4, 11))
        # Nightly: round(469/7 * 0.85) * 7 = 399 (not weekly 469*0.85)
        self.assertEqual(paques_dp.scraped_price, Decimal("399"))

    def test_pc_uses_adultes_column_when_not_first_price_column(self):
        rows = [
            [
                "Séjour semaine en pension complète",
                "11 à - 16 ans",
                "Adultes",
                "6 à - 11 ans",
            ],
            ["Eté", "4 au 11/07/26", "658 €", "728 €", "581 €"],
        ]

        bands = parse_grille_table(rows)

        # Child age-group columns are now extracted alongside adults (see
        # test_pc_uses_adultes_column_when_not_first_price_column's sibling
        # test in test_tariff_scraper_regressions.py), so this now produces
        # 3 bands instead of 1. The original intent of this test — that the
        # Adultes column price is picked up correctly even when it isn't
        # the first price column — still holds via the Adultes band.
        self.assertEqual(len(bands), 3)
        adultes = next(b for b in bands if b.unit_type == "Adultes")
        self.assertEqual(adultes.formule, "PC")
        self.assertEqual(adultes.scraped_price, Decimal("728"))


class ParseGrilleCarcansParityTests(TestCase):
    """Parser must reproduce live Carcans Oyats LOC unit prices."""

    def setUp(self):
        self.bands = parse_grille_table(CARCANS_LOC_ROWS)
        self.loc = [b for b in self.bands if b.formule == "LOC"]

    def test_cheapest_unit_labelled_correctly(self):
        two_p = [b for b in self.loc if "2 pièces" in b.unit_type]
        self.assertTrue(two_p)
        peak = next(
            b for b in two_p
            if b.date_start == date(2026, 8, 1) and b.date_end == date(2026, 8, 15)
        )
        self.assertEqual(peak.scraped_price, Decimal("1260"))

    def test_hors_vacances_cheapest_matches_website(self):
        two_p = [
            b for b in self.loc
            if "2 pièces" in b.unit_type and b.scraped_price == Decimal("483")
        ]
        self.assertEqual(len(two_p), 2)  # two date windows share the rate

    def test_three_unit_types_per_week(self):
        week = [
            b for b in self.loc
            if b.date_start == date(2026, 7, 4) and b.date_end == date(2026, 7, 11)
        ]
        prices = {b.unit_type: b.scraped_price for b in week}
        self.assertEqual(prices["2 pièces 4 pers."], Decimal("714"))
        self.assertEqual(prices["3 pièces 4/6 pers."], Decimal("868"))
        self.assertEqual(prices["Duplex 3 pièces 4/6 pers."], Decimal("924"))


class HtmlTableExtractionTests(TestCase):
    """Hidden popin tables must parse from raw HTML (not Playwright inner_text)."""

    LACANAU_HTML_FRAGMENT = """
    <div class="nq-c-Popin" style="display:none">
      <div class="nq-c-Popin-head-title">Grille tarifaire</div>
      <table>
        <tr>
          <th>S&eacute;jour semaine en pension compl&egrave;te</th>
          <th>Adultes</th><th>11 &agrave; - 16 ans</th>
        </tr>
        <tr>
          <td>P&acirc;ques</td><td>11/04 au 2/05/26</td>
          <td>469 &euro;</td><td>420 &euro;</td>
        </tr>
        <tr>
          <td>25/07 au 15/08/26</td>
          <td>945 &euro;</td><td>854 &euro;</td>
        </tr>
      </table>
      <p>1/2 pension possible = 15% de remise sur le tarif en pension compl&egrave;te</p>
    </div>
    """

    def test_extract_and_parse_hidden_popin(self):
        from apps.tariff_scraper.services.scraper import parse_bands_from_html

        bands = parse_bands_from_html(self.LACANAU_HTML_FRAGMENT)
        pc = [b for b in bands if b.formule == "PC"]
        self.assertTrue(pc)
        self.assertTrue(any(b.scraped_price == Decimal("469") for b in pc))
        self.assertTrue(any(b.scraped_price == Decimal("945") for b in pc))
        dp = [b for b in bands if b.formule == "DP"]
        self.assertTrue(dp)  # 15% remise derived


class VillageUrlRegistryTests(TestCase):
    def test_catalog_pks_not_slug_keys(self):
        # Critical: keys must be Village.pk values, not VTF path slugs
        self.assertIn("lacanau", VILLAGE_URLS)
        self.assertNotIn("la-forestiere", VILLAGE_URLS)
        self.assertIn("carcans-les-oyats", VILLAGE_URLS)
        self.assertNotIn("les-oyats", VILLAGE_URLS)
        self.assertTrue(VILLAGE_URLS["lacanau"].endswith("/la-forestiere"))

    def test_get_village_url(self):
        self.assertIsNotNone(get_village_url("lacanau"))
        self.assertIsNone(get_village_url("not-a-village"))


class ScrapeVillageEmptyResultTests(TestCase):
    """Empty scrapes must surface errors (never silent ok with 0 bands)."""

    def _install_fake_playwright(self):
        import sys
        from types import ModuleType

        pw = ModuleType("playwright")
        pw_sync = ModuleType("playwright.sync_api")
        mock_cm = MagicMock()
        mock_sync_pw = MagicMock()
        mock_sync_pw.return_value.__enter__.return_value = mock_cm
        mock_sync_pw.return_value.__exit__.return_value = None
        pw_sync.sync_playwright = mock_sync_pw
        return patch.dict(sys.modules, {"playwright": pw, "playwright.sync_api": pw_sync})

    def test_empty_html_reports_error(self):
        from apps.tariff_scraper.services.scraper import (
            HttpGridScrapeResult,
            scrape_village,
        )

        empty = HttpGridScrapeResult(
            bands=[], html_len=1200, fetch_error=None, has_grille_markers=False
        )

        with self._install_fake_playwright(), patch(
            "apps.tariff_scraper.services.scraper.scrape_price_grid_http",
            return_value=empty,
        ), patch(
            "apps.tariff_scraper.services.scraper.scrape_price_grid",
            return_value=[],
        ), patch(
            "apps.tariff_scraper.services.scraper.scrape_booking_widget",
            return_value=[],
        ), patch(
            "apps.tariff_scraper.services.llm_fallback.llm_fallback_enabled",
            return_value=False,
        ), patch(
            "apps.tariff_scraper.services.scraper.fetch_village_html",
            return_value="",
        ):
            result = scrape_village("lacanau", VILLAGE_URLS["lacanau"])

        self.assertEqual(result.bands, [])
        self.assertTrue(result.errors)
        self.assertTrue(
            any(
                "No priced tariff bands" in e or "grille markers" in e
                for e in result.errors
            )
        )

    def test_recovered_http_fetch_failure_is_not_reported_as_scrape_error(self):
        from apps.tariff_scraper.services.scraper import scrape_village

        recovered_band = RawPriceBand(
            formule="PC",
            source_page="price_grid",
            date_label="04/07 au 11/07/26",
            date_start=date(2026, 7, 4),
            date_end=date(2026, 7, 11),
            scraped_price=Decimal("812.00"),
        )
        failed_http = HttpGridScrapeResult(
            bands=[],
            fetch_error="HTTP fetch failed for http://test: set object expected; got frozenset",
        )

        with self._install_fake_playwright(), patch(
            "apps.tariff_scraper.services.scraper.scrape_price_grid_http",
            return_value=failed_http,
        ), patch(
            "apps.tariff_scraper.services.scraper.scrape_price_grid",
            return_value=[recovered_band],
        ), patch(
            "apps.tariff_scraper.services.scraper.scrape_booking_widget",
            return_value=[],
        ):
            result = scrape_village("lacanau", VILLAGE_URLS["lacanau"])

        self.assertEqual(result.bands, [recovered_band])
        self.assertEqual(result.errors, [])

    def test_http_loc_prices_do_not_open_booking_widget(self):
        from apps.tariff_scraper.services.scraper import scrape_village

        loc_band = RawPriceBand(
            formule="LOC",
            source_page="price_grid",
            date_label="04/07 au 11/07/26",
            date_start=date(2026, 7, 4),
            date_end=date(2026, 7, 11),
            scraped_price=Decimal("714.00"),
            unit_type="2 pièces 4 pers.",
        )
        http_result = HttpGridScrapeResult(bands=[loc_band], html_len=1000)

        with patch(
            "apps.tariff_scraper.services.scraper.scrape_price_grid_http",
            return_value=http_result,
        ), patch(
            "apps.tariff_scraper.services.scraper.scrape_price_grid"
        ) as mock_grid, patch(
            "apps.tariff_scraper.services.scraper.scrape_booking_widget"
        ) as mock_widget:
            result = scrape_village("carcans-les-oyats", VILLAGE_URLS["carcans-les-oyats"])

        self.assertEqual(result.bands, [loc_band])
        self.assertEqual(result.errors, [])
        mock_grid.assert_not_called()
        mock_widget.assert_not_called()

    def test_partial_grille_prices_do_not_open_fallback_tiers(self):
        from apps.tariff_scraper.services.scraper import scrape_village

        pc_band = RawPriceBand(
            formule="PC",
            source_page="price_grid",
            date_label="04/07 au 11/07/26",
            date_start=date(2026, 7, 4),
            date_end=date(2026, 7, 11),
            scraped_price=Decimal("812.00"),
        )
        http_result = HttpGridScrapeResult(bands=[pc_band], html_len=1000)

        with self._install_fake_playwright(), patch(
            "apps.tariff_scraper.services.scraper.scrape_price_grid_http",
            return_value=http_result,
        ), patch(
            "apps.tariff_scraper.services.scraper.scrape_price_grid",
            return_value=[],
        ) as mock_grid, patch(
            "apps.tariff_scraper.services.scraper.scrape_booking_widget"
        ) as mock_widget:
            result = scrape_village(
                "lacanau",
                VILLAGE_URLS["lacanau"],
                expected_formules={"PC", "DP"},
            )

        self.assertEqual(result.bands, [pc_band])
        self.assertEqual(result.errors, [])
        mock_grid.assert_not_called()
        mock_widget.assert_not_called()


class TarifBuilderAndQueryTests(TestCase):
    fixtures = ["villages", "pricing_rules"]

    def _lacanau_scrape(self) -> VillageScrapeResult:
        bands = parse_grille_table(LACANAU_PC_ROWS, page_text=LACANAU_PAGE_TEXT)
        return VillageScrapeResult(village_id="lacanau", url=VILLAGE_URLS["lacanau"], bands=bands)

    def test_build_stages_pending_approval_not_active_tarifs(self):
        result = build_tarifs_from_scrape(self._lacanau_scrape())
        self.assertFalse(result.errors)
        self.assertIsNotNone(result.approval_id)
        self.assertGreater(result.bands_proposed, 0)
        self.assertEqual(result.tarifs_created, 0)
        self.assertFalse(
            VillageTarif.objects.filter(village_id="lacanau", is_active=True).exists()
        )
        approval = TariffApproval.objects.get(pk=result.approval_id)
        self.assertEqual(approval.status, STATUS_PENDING)
        self.assertTrue(approval.proposed_bands)
        self.assertIn("PC", approval.proposed_season_tarifs)

    def test_approve_activates_tarifs_and_updates_village(self):
        build = build_tarifs_from_scrape(self._lacanau_scrape())
        approval = TariffApproval.objects.get(pk=build.approval_id)
        before = Village.objects.get(pk="lacanau").tarifs

        approved = approve_tariff_approval(approval, sync_fixture=False)
        self.assertEqual(approved.status, STATUS_APPROVED)
        self.assertEqual(approved.previous_village_tarifs, before)
        self.assertTrue(
            VillageTarif.objects.filter(village_id="lacanau", is_active=True).exists()
        )
        # Stay-estimate bridge: peak summer week must resolve to grille 945€
        # (season JSON may coincidentally match the fixture after setdefault).
        self.assertEqual(
            get_active_tarif("lacanau", "PC", date(2026, 8, 1)),
            Decimal("945"),
        )
        self.assertTrue(approved.proposed_bands)
        self.assertIn("PC", approved.proposed_season_tarifs)

    def test_reject_leaves_pricing_untouched(self):
        build = build_tarifs_from_scrape(self._lacanau_scrape())
        before = Village.objects.get(pk="lacanau").tarifs
        approval = TariffApproval.objects.get(pk=build.approval_id)
        reject_tariff_approval(approval, reason="bad scrape")
        approval.refresh_from_db()
        self.assertEqual(approval.status, STATUS_REJECTED)
        self.assertEqual(approval.reject_reason, "bad scrape")
        self.assertFalse(
            VillageTarif.objects.filter(village_id="lacanau", is_active=True).exists()
        )
        self.assertEqual(Village.objects.get(pk="lacanau").tarifs, before)

    def test_newer_scrape_supersedes_pending(self):
        first = build_tarifs_from_scrape(self._lacanau_scrape())
        second = build_tarifs_from_scrape(self._lacanau_scrape())
        old = TariffApproval.objects.get(pk=first.approval_id)
        new = TariffApproval.objects.get(pk=second.approval_id)
        self.assertEqual(old.status, STATUS_REJECTED)
        self.assertIn("Superseded", old.reject_reason)
        self.assertEqual(new.status, STATUS_PENDING)

    def test_snapshot_accepts_missing_dates(self):
        scrape = VillageScrapeResult(
            village_id="lacanau",
            url=VILLAGE_URLS["lacanau"],
            bands=[
                RawPriceBand(
                    formule="PC",
                    source_page="widget",
                    date_label="unknown",
                    date_start=None,
                    date_end=None,
                    scraped_price=Decimal("100"),
                    is_available=True,
                )
            ],
        )
        result = build_tarifs_from_scrape(scrape)
        self.assertFalse(result.errors)
        self.assertEqual(result.snapshots_created, 1)
        self.assertEqual(result.bands_proposed, 0)
        self.assertEqual(result.skipped_no_dates, 1)
        snap = PriceSnapshot.objects.get(village_id="lacanau")
        self.assertIsNone(snap.date_start)

    def test_get_active_tarif_peak_week(self):
        _build_and_approve(self._lacanau_scrape())
        price = get_active_tarif("lacanau", "PC", date(2026, 8, 1))
        self.assertEqual(price, Decimal("945"))

    def test_get_active_tarif_paques(self):
        _build_and_approve(self._lacanau_scrape())
        price = get_active_tarif("lacanau", "PC", date(2026, 4, 20))
        self.assertEqual(price, Decimal("469"))

    def test_loc_returns_cheapest_unit_when_unspecified(self):
        bands = parse_grille_table(CARCANS_LOC_ROWS)
        scrape = VillageScrapeResult(
            village_id="carcans-les-oyats",
            url=VILLAGE_URLS["carcans-les-oyats"],
            bands=bands,
        )
        _build_and_approve(scrape)
        # Peak week cheapest unit = 1260 (2 pièces)
        price = get_active_tarif("carcans-les-oyats", "LOC", date(2026, 8, 5))
        self.assertEqual(price, Decimal("1260"))
        # Specific unit
        duplex = get_active_tarif(
            "carcans-les-oyats",
            "LOC",
            date(2026, 8, 5),
            unit_type="Duplex 3 pièces 4/6 pers.",
        )
        self.assertEqual(duplex, Decimal("1617"))


class PricingBridgeTests(TestCase):
    """estimate_sejour_total must prefer scraped VillageTarif over fixtures."""

    fixtures = ["villages", "pricing_rules"]

    def test_resolve_uses_scraped_price(self):
        from apps.pricing.services.stay_estimate import _resolve_base_tarif

        bands = parse_grille_table(LACANAU_PC_ROWS, page_text=LACANAU_PAGE_TEXT)
        _build_and_approve(
            VillageScrapeResult(village_id="lacanau", url=VILLAGE_URLS["lacanau"], bands=bands)
        )

        village = {
            "id": "lacanau",
            "tarifs": {"PC": {"hs": 455, "vs": 540, "ete": 570, "fetes": 555}},
        }
        # Peak summer week on website is 945€, fixture ete is 570€
        base, coef, is_per_night = _resolve_base_tarif(
            village=village,
            formule="PC",
            stay_date=date(2026, 8, 1),
            saison="ete",
            pricing_rules={"formulaCoefficients": {"DP": 0.82}},
        )
        self.assertEqual(base, 945.0)
        self.assertEqual(coef, 1.0)
        self.assertFalse(is_per_night)

    def test_fallback_to_fixture_when_no_scrape(self):
        from apps.pricing.services.stay_estimate import _resolve_base_tarif

        village = {
            "id": "lacanau",
            "tarifs": {"PC": {"hs": 455, "vs": 540, "ete": 570, "fetes": 555}},
        }
        base, coef, is_per_night = _resolve_base_tarif(
            village=village,
            formule="PC",
            stay_date=date(2026, 8, 1),
            saison="ete",
            pricing_rules={"formulaCoefficients": {"DP": 0.82}},
        )
        self.assertEqual(base, 570.0)
        self.assertEqual(coef, 1.0)
        self.assertFalse(is_per_night)

    def test_estimate_matches_website_weekly_adult_base(self):
        from apps.catalog.models import PricingRules
        from apps.pricing.services.stay_estimate import estimate_sejour_total

        bands = parse_grille_table(LACANAU_PC_ROWS, page_text=LACANAU_PAGE_TEXT)
        _build_and_approve(
            VillageScrapeResult(village_id="lacanau", url=VILLAGE_URLS["lacanau"], bands=bands)
        )
        rules = PricingRules.active()
        # 1 adult, 7 nights, no promos — stay should be ~945€ + adhesion
        result = estimate_sejour_total(
            family={"adultes": 1, "enfants": [], "qfVal": None, "maxiFamily": False},
            sejour={
                "formule": "PC",
                "dateDebut": "2026-08-01",
                "dateFin": "2026-08-08",
                "promos": {},
                "extras": {},
            },
            village={
                "id": "lacanau",
                "region": "Aquitaine / Landes",
                "bebeClub": False,
                "qfExc": False,
                "tarifs": {"PC": {"ete": 570}},
            },
            pricing_rules=rules,
        )
        self.assertIsNotNone(result)
        # Per-adult weekly base after duration coef 1.0 = 945; no discounts
        self.assertEqual(result.per_adult_base, 945)

    def test_estimate_uses_scraped_child_age_band_price(self):
        from apps.catalog.models import PricingRules
        from apps.pricing.services.stay_estimate import estimate_sejour_total

        bands = parse_grille_table(LACANAU_PC_ROWS, page_text=LACANAU_PAGE_TEXT)
        _build_and_approve(
            VillageScrapeResult(village_id="lacanau", url=VILLAGE_URLS["lacanau"], bands=bands)
        )
        rules = PricingRules.active()

        result = estimate_sejour_total(
            family={
                "adultes": 2,
                "enfants": [{"age": 12}],
                "qfVal": None,
                "maxiFamily": False,
            },
            sejour={
                "formule": "PC",
                "dateDebut": "2026-08-01",
                "dateFin": "2026-08-08",
                "promos": {},
                "extras": {},
            },
            village={
                "id": "lacanau",
                "region": "Aquitaine / Landes",
                "bebeClub": False,
                "qfExc": False,
                "tarifs": {"PC": {"ete": 570}},
            },
            pricing_rules=rules,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.per_adult_base, 945)
        self.assertEqual(result.child_lines[0].amount, 854)
        self.assertEqual(result.total_children, 854)

    def test_estimate_falls_back_to_child_discount_without_age_band(self):
        from apps.catalog.models import PricingRules
        from apps.pricing.services.stay_estimate import estimate_sejour_total

        VillageTarif.objects.create(
            village_id="lacanau",
            formule="PC",
            date_start=date(2026, 8, 1),
            date_end=date(2026, 8, 8),
            unit_type="Adultes",
            price=Decimal("945"),
            is_active=True,
        )
        rules = PricingRules.active()

        result = estimate_sejour_total(
            family={
                "adultes": 2,
                "enfants": [{"age": 8}],
                "qfVal": None,
                "maxiFamily": False,
            },
            sejour={
                "formule": "PC",
                "dateDebut": "2026-08-01",
                "dateFin": "2026-08-08",
                "promos": {},
                "extras": {},
            },
            village={
                "id": "lacanau",
                "region": "Aquitaine / Landes",
                "bebeClub": False,
                "qfExc": False,
                "tarifs": {"PC": {"ete": 570}},
            },
            pricing_rules=rules,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.per_adult_base, 945)
        self.assertEqual(result.child_lines[0].amount, 756)

################################################################################################
# PS-01 … PS-09 remediation tests
################################################################################################

from unittest.mock import MagicMock, patch

from apps.tariff_scraper.services.scraper import (
    DERIVATION_ASSUMED,
    DERIVATION_SCRAPED,
    DERIVATION_STATED,
    _parse_price,
    _prefer_regular_price_from_cell_html,
    _read_nb_adults_from_widget,
    _read_widget_state,
    parse_bands_from_html,
)


class PS01DateParsingTests(TestCase):
    """Cross-year bands + year-less cells (PS-01 / F-01 / F-02)."""

    def test_cross_year_pulls_start_back(self):
        with patch("apps.tariff_scraper.services.scraper._today", return_value=date(2026, 7, 24)):
            self.assertEqual(
                parse_vtf_period_cell("27/12 au 3/01/26"),
                [(date(2025, 12, 27), date(2026, 1, 3))],
            )
            self.assertEqual(
                parse_vtf_period_cell("31/12 au 7/01/27"),
                [(date(2026, 12, 31), date(2027, 1, 7))],
            )

    def test_same_season_ranges_unchanged(self):
        with patch("apps.tariff_scraper.services.scraper._today", return_value=date(2026, 7, 24)):
            self.assertEqual(
                parse_vtf_period_cell("11/04 au 2/05/26"),
                [(date(2026, 4, 11), date(2026, 5, 2))],
            )
            ranges = parse_vtf_period_cell("2/05 au 4/07, 29/08 au 3/10/26")
            self.assertEqual(ranges[0], (date(2026, 5, 2), date(2026, 7, 4)))
            self.assertEqual(ranges[1], (date(2026, 8, 29), date(2026, 10, 3)))

    def test_yearless_uses_today_year_not_month_as_year(self):
        # Freeze before the band so F-02 roll-forward does not fire
        with patch("apps.tariff_scraper.services.scraper._today", return_value=date(2026, 3, 1)):
            # F-01: must NOT become 2005 / 2007 / 2001
            self.assertEqual(
                parse_vtf_period_cell("11/04 au 2/05"),
                [(date(2026, 4, 11), date(2026, 5, 2))],
            )
            self.assertEqual(
                parse_vtf_period_cell("4 au 11/07"),
                [(date(2026, 7, 4), date(2026, 7, 11))],
            )

    def test_yearless_past_rolls_forward(self):
        # F-02: year-less band already past → roll forward one year
        with patch("apps.tariff_scraper.services.scraper._today", return_value=date(2026, 7, 24)):
            self.assertEqual(
                parse_vtf_period_cell("11/04 au 2/05"),
                [(date(2027, 4, 11), date(2027, 5, 2))],
            )


class PS02ColumnAlignmentTests(TestCase):
    def test_period_column_does_not_steal_adult_price(self):
        rows = [
            ["Pension complète", "Période", "Adultes", "Enfants 2-11"],
            ["Basse", "11/04 au 2/05/26", "469 €", "329 €"],
        ]
        notes: list[str] = []
        bands = parse_grille_table(rows, notes=notes)
        pc = [b for b in bands if b.formule == "PC"]
        self.assertEqual(len(pc), 1)
        self.assertEqual(pc[0].scraped_price, Decimal("469"))
        self.assertEqual(pc[0].unit_type, "Adultes")

    def test_no_period_column_still_correct(self):
        rows = [
            ["Pension complète", "Adultes", "Enfants"],
            ["Basse", "11/04 au 2/05/26", "469 €", "329 €"],
        ]
        bands = parse_grille_table(rows)
        self.assertEqual(bands[0].scraped_price, Decimal("469"))

    def test_empty_spacer_does_not_drift(self):
        rows = [
            ["Pension complète", "Période", "Adultes", ""],
            ["Basse", "11/04 au 2/05/26", "469 €", "329 €"],
        ]
        bands = parse_grille_table(rows)
        self.assertEqual(bands[0].scraped_price, Decimal("469"))

    def test_header_only_period_flags_misalignment(self):
        rows = [
            ["Pension complète", "Période"],
            ["Basse", "11/04 au 2/05/26", "469 €", "329 €"],
        ]
        notes: list[str] = []
        parse_grille_table(rows, notes=notes)
        self.assertTrue(any(n.startswith("header_misalignment") for n in notes))


class PS03PromoPriceTests(TestCase):
    def test_struck_price_preferred_regardless_of_order(self):
        a = _prefer_regular_price_from_cell_html(
            "<td><del>469 €</del><span>399 €</span></td>"
        )
        b = _prefer_regular_price_from_cell_html(
            "<td><span>399 €</span><del>469 €</del></td>"
        )
        self.assertEqual(_parse_price(a), Decimal("469"))
        self.assertEqual(_parse_price(b), Decimal("469"))

    def test_prix_barre_class_on_td(self):
        text = _prefer_regular_price_from_cell_html(
            '<td class="prix-barre">469 €</td>'
        )
        self.assertEqual(_parse_price(text), Decimal("469"))

    def test_parse_bands_from_html_uses_struck(self):
        html = """
        <div>grille tarifaire pension complète</div>
        <table>
          <tr><th>Pension complète</th><th>Adultes</th></tr>
          <tr>
            <td>Pâques</td><td>11/04 au 2/05/26</td>
            <td><span>399 €</span><del>469 €</del></td>
          </tr>
        </table>
        """
        bands = parse_bands_from_html(html)
        pc = [b for b in bands if b.formule == "PC"]
        self.assertTrue(pc)
        self.assertEqual(pc[0].scraped_price, Decimal("469"))


class PS04NotOfferedTests(TestCase):
    def test_dash_cells_produce_notes_not_silent_empty(self):
        rows = [
            ["Séjour semaine en location", "Studio 4 pers.", "2 pièces"],
            ["Basse", "11/04 au 2/05/26", "—", "—"],
        ]
        notes: list[str] = []
        bands = parse_grille_table(rows, notes=notes)
        self.assertEqual(bands, [])
        self.assertTrue(any(n.startswith("not_offered") for n in notes))


class PS05DerivationTests(TestCase):
    def test_stated_remise_marked(self):
        bands = parse_grille_table(
            LACANAU_PC_ROWS,
            page_text="1/2 pension possible = 15% de remise sur le tarif en pension complète",
        )
        dp = [b for b in bands if b.formule == "DP"]
        self.assertTrue(dp)
        self.assertTrue(all(b.derivation == DERIVATION_STATED for b in dp))
        pc = [b for b in bands if b.formule == "PC"]
        self.assertTrue(all(b.derivation == DERIVATION_SCRAPED for b in pc))

    def test_assumed_remise_marked(self):
        rows = [
            ["Pension complète", "Adultes"],
            ["Eté", "25/07 au 15/08/26", "945 €"],
        ]
        bands = parse_grille_table(
            rows, page_text="Demi-pension possible sur demande"
        )
        dp = [b for b in bands if b.formule == "DP"]
        self.assertEqual(len(dp), 1)
        self.assertEqual(dp[0].derivation, DERIVATION_ASSUMED)
        self.assertEqual(dp[0].scraped_price, Decimal("805"))  # round(945/7*0.85)*7


class PS06CascadeTests(TestCase):
    def _install_fake_playwright(self):
        import sys
        from types import ModuleType

        pw = ModuleType("playwright")
        pw_sync = ModuleType("playwright.sync_api")
        mock_cm = MagicMock()
        mock_sync_pw = MagicMock()
        mock_sync_pw.return_value.__enter__.return_value = mock_cm
        mock_sync_pw.return_value.__exit__.return_value = None
        pw_sync.sync_playwright = mock_sync_pw
        return patch.dict(sys.modules, {"playwright": pw, "playwright.sync_api": pw_sync})

    def test_partial_pc_does_not_escalate_when_loc_expected(self):
        from apps.tariff_scraper.services.scraper import (
            HttpGridScrapeResult,
            scrape_village,
        )

        pc_band = RawPriceBand(
            formule="PC",
            source_page="price_grid",
            date_label="11/04 au 2/05/26",
            date_start=date(2026, 4, 11),
            date_end=date(2026, 5, 2),
            scraped_price=Decimal("469"),
        )
        loc_band = RawPriceBand(
            formule="LOC",
            source_page="price_grid",
            date_label="11/04 au 2/05/26",
            date_start=date(2026, 4, 11),
            date_end=date(2026, 5, 2),
            scraped_price=Decimal("714"),
            unit_type="2 pièces",
        )
        http_result = HttpGridScrapeResult(bands=[pc_band], html_len=1000)

        with self._install_fake_playwright(), patch(
            "apps.tariff_scraper.services.scraper.scrape_price_grid_http",
            return_value=http_result,
        ), patch(
            "apps.tariff_scraper.services.scraper.scrape_price_grid",
            return_value=[loc_band],
        ) as mock_grid, patch(
            "apps.tariff_scraper.services.scraper.scrape_booking_widget",
            return_value=[],
        ):
            result = scrape_village(
                "carcans-les-oyats",
                VILLAGE_URLS["carcans-les-oyats"],
                expected_formules={"PC", "LOC"},
            )

        mock_grid.assert_not_called()
        formules = {b.formule for b in result.bands}
        self.assertIn("PC", formules)
        self.assertNotIn("LOC", formules)


class PS07PS08PriceParseTests(TestCase):
    def test_unit_strings_rejected(self):
        self.assertIsNone(_parse_price("6 pers."))
        self.assertIsNone(_parse_price("7 nuits"))
        self.assertEqual(_parse_price("Studio 4 pers. 469 €"), Decimal("469"))

    def test_french_formats_still_work(self):
        self.assertEqual(_parse_price("1 234,00 €"), Decimal("1234.00"))
        self.assertEqual(_parse_price("469"), Decimal("469"))
        self.assertEqual(_parse_price("469 &euro;"), Decimal("469"))
        self.assertEqual(_parse_price("1 234 €"), Decimal("1234"))

    def test_zero_euro_is_valid(self):
        self.assertEqual(_parse_price("0 €"), Decimal("0"))
        self.assertEqual(_parse_price("Gratuit"), Decimal("0"))


class PS09WidgetOccupancyTests(TestCase):
    def test_reads_adult_count_from_body_text(self):
        page = MagicMock()
        page.query_selector.return_value = None
        page.inner_text.return_value = "Votre réservation — 3 adultes — 938 €"
        self.assertEqual(_read_nb_adults_from_widget(page), 3)

    def test_per_adult_uses_read_occupancy(self):
        header = MagicMock()
        header.inner_text.return_value = "04/07 au 11/07/26"

        label = MagicMock()
        label.inner_text.return_value = "Pension complète"

        price_cell = MagicMock()
        price_cell.inner_text.return_value = "938 €"

        row = MagicMock()
        row.inner_text.return_value = "Pension complète\n938 €"

        def row_qs(sel: str):
            if any(k in sel for k in ("label", "name", "first-child")):
                return label
            return None  # no struck-through node

        row.query_selector.side_effect = row_qs
        row.query_selector_all.return_value = [price_cell]

        page = MagicMock()

        def page_qs(sel: str):
            if any(k in sel for k in ("date", "week", "semaine")):
                return header
            return None

        page.query_selector.side_effect = page_qs
        page.query_selector_all.return_value = [row]

        with patch(
            "apps.tariff_scraper.services.scraper._read_nb_adults_from_widget",
            return_value=3,
        ):
            bands = _read_widget_state(page, "lacanau")

        self.assertEqual(len(bands), 1)
        self.assertEqual(bands[0].nb_adults, 3)
        self.assertEqual(bands[0].scraped_price, Decimal("312.67"))

# ---------------------------------------------------------------------------
# V4 API Tests (Tariff Scraper)
# ---------------------------------------------------------------------------

from django.contrib.auth.models import User
from rest_framework.test import APIClient
from apps.tariff_scraper.models import TariffApproval
from apps.catalog.models import Village

class TariffScraperV4APITests(TestCase):
    fixtures = ["villages", "pricing_rules"]

    def setUp(self):
        self.client = APIClient()
        self.staff_user = User.objects.create_user(
            username="staff_api", password="password", is_staff=True
        )
        self.client.force_authenticate(user=self.staff_user)

    @patch("apps.tariff_scraper.tasks.task_scrape_village_tariffs.delay")
    def test_scrape_single_village(self, mock_delay):
        mock_delay.return_value.id = "fake-task"
        resp = self.client.post("/api/v4/tariff-scraper/scrape/", {"village_id": "lacanau"}, format="json")
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json()["data"]["task_id"], "fake-task")
        mock_delay.assert_called_with("lacanau")

    @patch("apps.tariff_scraper.tasks.task_scrape_all_village_tariffs.delay")
    def test_scrape_all_villages(self, mock_delay):
        mock_delay.return_value.id = "fake-task-all"
        resp = self.client.post("/api/v4/tariff-scraper/scrape/", {}, format="json")
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json()["data"]["task_id"], "fake-task-all")
        mock_delay.assert_called_once()

    def test_scrape_invalid_village(self):
        resp = self.client.post("/api/v4/tariff-scraper/scrape/", {"village_id": "invalid-id"}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_list_all_tariffs(self):
        resp = self.client.get("/api/v4/tariff-scraper/tariffs/")
        self.assertEqual(resp.status_code, 200)

    def test_list_all_tariffs_with_filters(self):
        resp = self.client.get("/api/v4/tariff-scraper/tariffs/?village_id=lacanau&formule=PC")
        self.assertEqual(resp.status_code, 200)

    def test_village_tariffs_list(self):
        resp = self.client.get("/api/v4/tariff-scraper/tariffs/lacanau/")
        self.assertEqual(resp.status_code, 200)

    def test_village_tariffs_invalid_village(self):
        resp = self.client.get("/api/v4/tariff-scraper/tariffs/invalid-id/")
        self.assertEqual(resp.status_code, 400)

    def test_format_change_log(self):
        resp = self.client.get("/api/v4/tariff-scraper/format-changes/")
        self.assertEqual(resp.status_code, 200)

    def test_format_change_log_filter(self):
        resp = self.client.get("/api/v4/tariff-scraper/format-changes/?change_type=zero_prices&village_id=lacanau")
        self.assertEqual(resp.status_code, 200)

    @patch("apps.tariff_scraper.services.alerts.notify_scrape_success")
    def test_dry_run_alert_success(self, mock_notify):
        resp = self.client.post(
            "/api/v4/tariff-scraper/dry-run/",
            {"scenario": "success", "village_id": "lacanau"},
            format="json"
        )
        self.assertEqual(resp.status_code, 200)
        mock_notify.assert_called_once()

    def test_approvals_list(self):
        resp = self.client.get("/api/v4/admin/tariff-scraper/approvals/")
        self.assertEqual(resp.status_code, 200)

    def _create_approval(self):
        return TariffApproval.objects.create(
            village=Village.objects.get(pk="lacanau"),
            status="pending",
            proposed_bands=[],
            proposed_season_tarifs={}
        )

    def test_approval_detail(self):
        app = self._create_approval()
        resp = self.client.get(f"/api/v4/admin/tariff-scraper/approvals/{app.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["id"], app.id)

    @patch("apps.tariff_scraper.views.approve_tariff_approval")
    def test_approval_action_approve(self, mock_approve):
        app = self._create_approval()
        mock_approve.return_value = app
        resp = self.client.post(
            f"/api/v4/admin/tariff-scraper/approvals/{app.id}/",
            {"action": "approve"},
            format="json"
        )
        self.assertEqual(resp.status_code, 200)
        mock_approve.assert_called_once()

    @patch("apps.tariff_scraper.views.reject_tariff_approval")
    def test_approval_action_reject(self, mock_reject):
        app = self._create_approval()
        mock_reject.return_value = app
        resp = self.client.post(
            f"/api/v4/admin/tariff-scraper/approvals/{app.id}/",
            {"action": "reject", "reject_reason": "test"},
            format="json"
        )
        self.assertEqual(resp.status_code, 200)
        mock_reject.assert_called_once()
