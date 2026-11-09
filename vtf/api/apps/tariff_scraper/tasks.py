"""Celery tasks for the tariff_scraper app.

Two tasks only (no cron scheduling here — that is done separately):
  task_scrape_village_tariffs   — scrape + stage pending approval for ONE village
  task_scrape_all_village_tariffs — queue the above for ALL 32 villages

ALERT HOOKS:
  - notify_scrape_failure()   — called when a village scrape returns ok=False
  - notify_format_change()    — called when format change is detected
  - notify_scrape_success()   — optional ping (off by default)
  - notify_batch_summary()    — called after all 32 villages finish via chord

ALERT COLOUR SCHEME:
  🔴 RED   — HTTP fetch failed / wrong URL / blocked
  🔴 RED   — Page loaded but zero prices found (layout changed)
  🟡 YELLOW — Prices scraped but dates/prices couldn't be parsed
  🟡 YELLOW — Some data got through but with errors
  🔴 RED   — Unhandled exception crash
"""
from __future__ import annotations

import logging

from celery import shared_task

from apps.tariff_scraper.services.village_urls import VILLAGE_URLS

logger = logging.getLogger("scraper")


def _is_actionable_format_change(summary: dict) -> bool:
    """True when a detected format change should notify/persist."""
    fc = summary.get("format_change") or {}
    if not fc.get("change_detected"):
        return False

    # Header alignment can be a harmless parser note when prices were still
    # extracted and staged. Keep it out of alerts/log rows unless it blocks data.
    if fc.get("change_type") == "header_misalignment" and summary.get("ok"):
        return False

    return True


def _log_format_change(summary: dict) -> None:
    """Persist a FormatChangeLog row when a format change is detected."""
    if not _is_actionable_format_change(summary):
        return

    try:
        from apps.tariff_scraper.models import FormatChangeLog

        fc = summary.get("format_change") or {}
        village_id = summary.get("village_id", "")
        if not village_id:
            return

        # Determine change_type for the model
        change_type = fc.get("change_type", "partial")
        model_type_map = {
            "marker_missing": "marker_missing",
            "zero_prices": "zero_prices",
            "parse_failure": "parse_failure",
            "hard_failure": "hard_failure",
            "partial": "partial",
        }
        model_change_type = model_type_map.get(change_type, "partial")

        # If this is a hard failure (no bands at all, scrape errors), use hard_failure
        if summary.get("bands_scraped", 0) == 0 and summary.get("scrape_errors"):
            model_change_type = "hard_failure"

        FormatChangeLog.objects.create(
            village_id=village_id,
            change_type=model_change_type,
            source_url=summary.get("url", ""),
            expected_markers=fc.get("expected_markers", []),
            found_markers=fc.get("found_markers", []),
            missing_markers=fc.get("missing_markers", []),
            html_length=fc.get("html_length", 0),
            table_count=fc.get("table_count", 0),
            bands_scraped=fc.get("bands_scraped", 0),
            priced_bands=fc.get("priced_bands", 0),
            errors=summary.get("scrape_errors", []) + summary.get("build_errors", []),
            html_snippet="",  # Could be populated from scrape result if needed
        )
        logger.info(
            "_log_format_change: logged format change for village=%s type=%s",
            village_id, model_change_type,
        )
    except Exception as exc:
        logger.warning("_log_format_change: failed to persist — %s", exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60, name="tariff_scraper.scrape_village")
def task_scrape_village_tariffs(self, village_id: str) -> dict:
    """Scrape and stage a pending TariffApproval for a single village.

    Live VillageTarif / Village.tarifs update only after staff approve.

    Args:
        village_id: Catalog Village.id, e.g. "lacanau".

    Returns a summary dict with snapshot/approval counts and any errors.
    """
    from apps.catalog.models import Village
    from apps.tariff_scraper.services.scraper import scrape_village_all_seasons
    from apps.tariff_scraper.services.tarif_builder import build_tarifs_from_scrape
    from apps.tariff_scraper.services.village_urls import get_village_scrape_urls
    from apps.tariff_scraper.services.alerts import (
        notify_scrape_failure,
        notify_scrape_success,
        notify_format_change,
        notify_dp_remise_mismatch,
    )

    scrape_urls = get_village_scrape_urls(village_id)
    if not scrape_urls:
        logger.error("task_scrape_village_tariffs: unknown village_id=%s", village_id)
        return {"error": f"No URL registered for village '{village_id}'"}
    url = scrape_urls[0][0]

    logger.info(
        "task_scrape_village_tariffs: START village=%s urls=%d", village_id, len(scrape_urls)
    )

    try:
        # PS-06: escalate cascade for formules the village is known to sell
        expected_formules = None
        village = Village.objects.filter(pk=village_id).only("tarifs").first()
        if village and isinstance(village.tarifs, dict):
            expected_formules = [
                f for f in ("PC", "DP", "LOC") if f in village.tarifs
            ] or None

        # Dual-season villages: this scrapes /summer/ AND /winter/, each
        # running the full Tier 1-4 cascade independently, then merges into
        # one result tagged per-band with scrape_source. Single-URL villages
        # are unaffected — identical to calling scrape_village directly.
        scrape_result = scrape_village_all_seasons(
            village_id, expected_formules=expected_formules
        )
        build_result  = build_tarifs_from_scrape(scrape_result)

        priced_bands = sum(
            1
            for b in scrape_result.bands
            if b.is_available and b.scraped_price is not None
        )

        # Build format change dict for summary
        format_change_dict = None
        if scrape_result.format_change:
            fc = scrape_result.format_change
            format_change_dict = {
                "change_detected": fc.change_detected,
                "change_type": fc.change_type,
                "expected_markers": fc.expected_markers,
                "found_markers": fc.found_markers,
                "missing_markers": fc.missing_markers,
                "html_length": fc.html_length,
                "table_count": fc.table_count,
                "bands_scraped": fc.bands_scraped,
                "priced_bands": fc.priced_bands,
            }

        # Build DP verification dict for summary (diagnostic only — never
        # affects "ok" below). None when verification was skipped/disabled.
        dp_verification_dict = None
        if scrape_result.dp_verification is not None:
            dpv = scrape_result.dp_verification
            dp_verification_dict = {
                "checked":          dpv.checked,
                "regex_remise":     float(dpv.regex_remise) if dpv.regex_remise is not None else None,
                "regex_derivation": dpv.regex_derivation,
                "llm_remise":       float(dpv.llm_remise) if dpv.llm_remise is not None else None,
                "match":            dpv.match,
                "note":             dpv.note,
            }

        summary = {
            "village_id":         village_id,
            "urls_scraped": [
                {"url": u, "scrape_source": src} for u, src in scrape_urls
            ],
            "scrape_errors":      scrape_result.errors,
            "bands_scraped":      len(scrape_result.bands),
            "priced_bands":       priced_bands,
            "snapshots_created":  build_result.snapshots_created,
            "approval_id":        build_result.approval_id,
            "bands_proposed":     build_result.bands_proposed,
            "tarifs_created":     build_result.tarifs_created,
            "tarifs_deactivated": build_result.tarifs_deactivated,
            "skipped_unavailable":build_result.skipped_unavailable,
            "skipped_no_price":   build_result.skipped_no_price,
            "skipped_no_dates":   build_result.skipped_no_dates,
            "build_errors":       build_result.errors,
            "format_change":      format_change_dict,
            "dp_verification":    dp_verification_dict,
            # ok=True when we got valid data, even if there were non-fatal errors
            # (e.g. HTTP fetch failed but Playwright fallback succeeded).
            # ok=False only when: zero priced bands, zero proposed, or no approval.
            "ok": (
                priced_bands > 0
                and build_result.bands_proposed > 0
                and build_result.approval_id is not None
                and not build_result.errors
            ),
        }

        # ── Alert dispatch ────────────────────────────────────────────────
        if not summary["ok"]:
            # Scrape failed — determine if it's a format change or hard failure
            if _is_actionable_format_change(summary):
                # Format changed — send format change alert + failure alert
                notify_format_change(summary)
                notify_scrape_failure(summary)
            else:
                # Hard failure (HTTP error, blocked, etc.)
                notify_scrape_failure(summary)

            # Persist format change to DB
            _log_format_change(summary)
        elif _is_actionable_format_change(summary):
            # Scrape got data but page format changed — warn the team
            notify_format_change(summary)
            _log_format_change(summary)
        else:
            # Scrape succeeded (priced_bands > 0, no format change)
            # Non-fatal errors (e.g. HTTP fallback failed) are just warnings,
            # not worth alerting about.
            notify_scrape_success(summary)

        # DP remise verification mismatch — diagnostic only, additive alert.
        # Does not change `ok` and fires independently of the branch above
        # (a scrape can succeed fully and still have a DP remise mismatch).
        if dp_verification_dict and dp_verification_dict["checked"] and not dp_verification_dict["match"]:
            notify_dp_remise_mismatch(summary)
        # ─────────────────────────────────────────────────────────────────────

        logger.info(
            "task_scrape_village_tariffs: DONE village=%s snapshots=%d "
            "approval_id=%s bands_proposed=%d",
            village_id,
            build_result.snapshots_created,
            build_result.approval_id,
            build_result.bands_proposed,
        )
        return summary

    except Exception as exc:
        logger.exception("task_scrape_village_tariffs: FAILED village=%s", village_id)
        # Alert on hard crash too (task will retry, but team should know now)
        notify_scrape_failure({
            "village_id":    village_id,
            "url":           url,
            "scrape_errors": [f"tasks.py → task_scrape_village_tariffs() | Unhandled exception: {exc}"],
            "bands_scraped":  0,
            "priced_bands":   0,
            "bands_proposed": 0,
            "build_errors":  [],
            "format_change": {
                "change_detected": True,
                "change_type": "hard_failure",
                "expected_markers": [],
                "found_markers": [],
                "missing_markers": [],
                "html_length": 0,
                "table_count": 0,
                "bands_scraped": 0,
                "priced_bands": 0,
            },
            "ok": False,
        })
        # Persist format change for hard crash
        _log_format_change({
            "village_id": village_id,
            "url": url,
            "scrape_errors": [f"tasks.py → task_scrape_village_tariffs() | Unhandled exception: {exc}"],
            "bands_scraped": 0,
            "priced_bands": 0,
            "format_change": {
                "change_detected": True,
                "change_type": "hard_failure",
                "expected_markers": [],
                "found_markers": [],
                "missing_markers": [],
                "html_length": 0,
                "table_count": 0,
                "bands_scraped": 0,
                "priced_bands": 0,
            },
        })
        raise self.retry(exc=exc)


@shared_task(name="tariff_scraper.scrape_all_villages")
def task_scrape_all_village_tariffs() -> dict:
    """Queue tariff scrape tasks for all 32 registered villages.

    Uses a Celery chord so that task_batch_summary_callback fires after
    all 32 villages finish, sending a single batch Discord summary.

    Per-village alerts fire inside task_scrape_village_tariffs.
    The batch summary alert is sent via the chord callback.
    """
    from celery import chord
    from apps.tariff_scraper.tasks import task_batch_summary_callback

    village_ids = list(VILLAGE_URLS.keys())

    # Wire up chord: run all village scrapes, then callback with summary
    chord(
        task_scrape_village_tariffs.s(vid) for vid in village_ids
    )(task_batch_summary_callback.s())

    logger.info(
        "task_scrape_all_village_tariffs: queued %d villages via chord", len(village_ids)
    )
    return {"queued": village_ids, "total": len(village_ids)}


# ---------------------------------------------------------------------------
# Chord callback: batch summary + format change report
# ---------------------------------------------------------------------------

@shared_task(name="tariff_scraper.batch_summary_callback")
def task_batch_summary_callback(results: list[dict]) -> dict:
    """
    Celery chord callback — receives all 32 village summaries at once
    and sends a single batch Discord embed with:
      - OK / Failed counts
      - List of failed villages
      - List of villages with format changes

    This fires automatically after task_scrape_all_village_tariffs completes.
    """
    from apps.tariff_scraper.services.alerts import notify_batch_summary

    # Filter out None / error dicts from any crashed tasks
    valid = [r for r in (results or []) if isinstance(r, dict) and "village_id" in r]
    notify_batch_summary(valid)

    ok    = sum(1 for r in valid if r.get("ok"))
    total = len(valid)
    logger.info("task_batch_summary_callback: ok=%d/%d", ok, total)
    return {"ok": ok, "total": total}
