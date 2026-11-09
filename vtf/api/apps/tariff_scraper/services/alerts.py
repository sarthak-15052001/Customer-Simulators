"""Discord alert service for the tariff_scraper app.

Sends a Discord embed when a village scrape succeeds or fails so the client
can see *exactly* which pipeline step failed, which file/function produced
the error, and why.

ALERT COLOUR SCHEME:
  🟢 GREEN  — Village scraped successfully (priced bands + approval staged)
  🟡 YELLOW — Partial success / parse failure / success with step warnings
  🔴 RED    — Hard failure (HTTP/blocked), layout change, zero prices, crash

Error format from scraper / tarif_builder:
  "Step N (Label) | file.py → function() | reason detail"

Usage (called from tasks.py after every scrape):
    if not summary["ok"]:
        notify_scrape_failure(summary)
    elif summary.get("format_change", {}).get("change_detected"):
        notify_format_change(summary)
    else:
        notify_scrape_success(summary)
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

import requests
from common.discord import add_origin_to_embeds
from django.conf import settings

logger = logging.getLogger("tariff_scraper.alerts")

# Discord embed colours
_RED    = 0xED4245   # failure / layout changed / crash
_YELLOW = 0xFEE75C   # warning (partial data / parse failure / fallback used)
_GREEN  = 0x57F287   # success

# "Step 1 (HTTP Fetch) | scraper.py → scrape_price_grid_http() | HTTP 404"
_STEP_ERROR_RE = re.compile(
    r"^(?P<step>Step\s+\d+\s*\([^)]+\))\s*\|\s*"
    r"(?P<source>[^|]+?)\s*\|\s*"
    r"(?P<reason>.+)$",
    re.DOTALL,
)


def _webhook_url() -> str:
    return getattr(settings, "DISCORD_WEBHOOK", "")


def _post(payload: dict) -> None:
    """POST a Discord embed payload. Silently logs on failure — never raises."""
    url = _webhook_url()
    if not url:
        logger.debug("alerts._post: DISCORD_WEBHOOK not set, skipping")
        return
    try:
        add_origin_to_embeds(payload)
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code != 204:
            logger.warning(
                "alerts._post: Discord returned %s — %s",
                resp.status_code, resp.text[:200],
            )
    except Exception as exc:
        logger.warning("alerts._post: failed to send Discord alert — %s", exc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _format_urls_field(summary: dict) -> str:
    """Render the URL(s) scraped for the Discord embed's URL field."""
    urls_scraped = summary.get("urls_scraped") or []
    if urls_scraped:
        lines = [
            f"[{u.get('scrape_source', '?')}] {u.get('url', '—')}"
            for u in urls_scraped
        ]
        return "\n".join(lines)[:1024]
    return (summary.get("url") or "—")[:1024]


def _notify_success_enabled() -> bool:
    """Green success alerts are ON by default (client requirement)."""
    return getattr(settings, "TARIFF_SCRAPER_NOTIFY_SUCCESS", True)


# ---------------------------------------------------------------------------
# Parse "Step N | file → function | reason" into structured parts
# ---------------------------------------------------------------------------

def parse_pipeline_error(error: Any) -> dict[str, str]:
    """
    Split a pipeline error string into step / source / reason.

    Expected shape:
      "Step 2 (HTML Grid Parse) | scraper.py → scrape_price_grid_http() | Page loaded..."

    Falls back gracefully for plain strings (e.g. unhandled exceptions).
    """
    text = str(error).strip()
    match = _STEP_ERROR_RE.match(text)
    if match:
        return {
            "step": match.group("step").strip(),
            "source": match.group("source").strip(),
            "reason": match.group("reason").strip(),
        }

    # "tasks.py → task_scrape_village_tariffs() | Unhandled exception: ..."
    if " | " in text and "→" in text:
        left, _, right = text.partition(" | ")
        return {
            "step": "Unhandled exception",
            "source": left.strip(),
            "reason": right.strip(),
        }

    return {
        "step": "Unknown step",
        "source": "—",
        "reason": text,
    }


def format_errors_by_step(errors: list, *, limit: int = 8) -> str:
    """
    Render errors as a client-readable step-by-step block for Discord.

    Example:
      **Step 1 (HTTP Fetch)**
      📍 `scraper.py → scrape_price_grid_http()`
      ❌ HTTP 403 Forbidden
    """
    blocks: list[str] = []
    for raw in errors[:limit]:
        parsed = parse_pipeline_error(raw)
        blocks.append(
            f"**{parsed['step']}**\n"
            f"📍 `{parsed['source']}`\n"
            f"❌ {parsed['reason']}"
        )
    text = "\n\n".join(blocks)
    if len(errors) > limit:
        text += f"\n\n… +{len(errors) - limit} more error(s)"
    return text[:1024]


def _all_errors(summary: dict) -> list:
    return list(summary.get("scrape_errors") or []) + list(summary.get("build_errors") or [])


def _primary_error(summary: dict) -> Optional[dict[str, str]]:
    """Prefer the final validation / builder error; else the first pipeline error."""
    errors = _all_errors(summary)
    if not errors:
        return None
    for err in reversed(errors):
        text = str(err)
        if "Step 7" in text or "Step 8" in text or "Unhandled exception" in text:
            return parse_pipeline_error(err)
    return parse_pipeline_error(errors[0])


def _reason_from_primary(primary: Optional[dict[str, str]], fallback: str) -> str:
    if not primary:
        return fallback
    return (
        f"{primary['step']}\n"
        f"Code: `{primary['source']}`\n"
        f"Reason: {primary['reason']}"
    )


def _has_step(errors: list, step_num: int) -> bool:
    needle = f"Step {step_num}"
    return any(needle in str(e) for e in errors)


# ---------------------------------------------------------------------------
# Determine failure reason and colour from the summary dict
# ---------------------------------------------------------------------------

def _classify_failure(summary: dict) -> tuple[str, str, int]:
    """
    Returns (title, reason_detail, embed_colour).

    Reason includes the failing step + code location + why.
    Full step list goes in the separate "Errors by Step" embed field.

    Colour scheme:
      🔴 RED   — HTTP fetch failed / wrong URL / blocked / crash / zero prices
      🟡 YELLOW — Prices scraped but dates/prices couldn't be parsed
      🟡 YELLOW — Some data got through but with errors
    """
    village_id    = summary.get("village_id", "unknown")
    priced_bands  = summary.get("priced_bands", 0)
    scrape_errors = list(summary.get("scrape_errors") or [])
    build_errors  = list(summary.get("build_errors") or [])
    bands_scraped = summary.get("bands_scraped", 0)
    bands_proposed = summary.get("bands_proposed", 0)
    all_errors    = scrape_errors + build_errors
    primary       = _primary_error(summary)

    # 0. Unhandled crash → 🔴 RED
    if any("Unhandled exception" in str(e) for e in all_errors):
        return (
            f"🚨 Scrape CRASHED — {village_id}",
            _reason_from_primary(
                primary,
                "Unhandled exception in the scrape task — see Errors by Step.",
            ),
            _RED,
        )

    # 1. Hard HTTP fetch failure (Step 1 only, nothing extracted) → 🔴 RED
    if (
        bands_scraped == 0
        and priced_bands == 0
        and _has_step(scrape_errors, 1)
        and not _has_step(scrape_errors, 2)
        and not _has_step(scrape_errors, 4)
        and not _has_step(scrape_errors, 7)
    ):
        return (
            f"🚨 Scrape FAILED — {village_id}",
            _reason_from_primary(
                primary,
                "HTTP fetch failed or page blocked — no data could be extracted.",
            ),
            _RED,
        )

    # 2. Page loaded / pipeline ran but zero prices → 🔴 RED (layout / empty)
    if priced_bands == 0 and bands_scraped == 0:
        return (
            f"🔴 Zero prices extracted — {village_id}",
            _reason_from_primary(
                primary,
                "Page loaded but no price grid was found — the VTF page layout may have changed.",
            ),
            _RED,
        )

    # 3. Some bands scraped but none proposed (date/price parse failure) → 🟡 YELLOW
    if bands_scraped > 0 and bands_proposed == 0:
        return (
            f"🟡 Bands scraped but none proposed — {village_id}",
            _reason_from_primary(
                primary,
                f"{bands_scraped} band(s) scraped but 0 proposed — price or date format may have changed.",
            ),
            _YELLOW,
        )

    # 4. Partial — some errors but still got some data → 🟡 YELLOW
    if all_errors:
        return (
            f"🟡 Partial scrape — {village_id}",
            _reason_from_primary(
                primary,
                f"{priced_bands} price band(s) extracted with errors — see 'Errors by Step' below.",
            ),
            _YELLOW,
        )

    # Fallback — should not reach here if ok=False, but be safe
    return (
        f"❓ Scrape marked not-OK — {village_id}",
        f"ok=False but no specific errors captured.\n{summary}",
        _YELLOW,
    )


# ---------------------------------------------------------------------------
# Determine format change type and colour
# ---------------------------------------------------------------------------

def _classify_format_change(summary: dict) -> tuple[str, str, int]:
    """
    Returns (title, reason_detail, embed_colour) for format change alerts.

    Format change types:
      marker_missing  → 🔴 RED (all markers gone, page restructured)
      zero_prices     → 🔴 RED (page loaded but no prices extracted)
      parse_failure   → 🟡 YELLOW (dates/prices couldn't be parsed)
      hard_failure    → 🔴 RED (HTTP fetch / exception)
    """
    village_id = summary.get("village_id", "unknown")
    fc = summary.get("format_change") or {}
    change_type = fc.get("change_type", "unknown")
    primary = _primary_error(summary)

    missing = fc.get("missing_markers", [])
    found   = fc.get("found_markers", [])
    html_len = fc.get("html_length", 0)
    table_count = fc.get("table_count", 0)
    bands_scraped = fc.get("bands_scraped", 0)
    priced_bands = fc.get("priced_bands", 0)

    step_block = ""
    if primary:
        step_block = (
            f"\n\n**Failed at:** {primary['step']}\n"
            f"**Code:** `{primary['source']}`\n"
            f"**Reason:** {primary['reason']}"
        )

    if change_type == "marker_missing":
        return (
            f"🔴 FORMAT CHANGE — {village_id}",
            (
                f"The VTF page for **{village_id}** appears to have changed layout.\n\n"
                f"**Expected markers:** {', '.join(fc.get('expected_markers', []))}\n"
                f"**Found markers:** {', '.join(found) or 'none'}\n"
                f"**Missing markers:** {', '.join(missing) or 'none'}\n\n"
                f"HTML length: {html_len:,} chars | Tables found: {table_count}\n"
                f"Bands scraped: {bands_scraped} | Priced: {priced_bands}"
                f"{step_block}\n\n"
                "The scraper needs to be updated to handle the new page format."
            ),
            _RED,
        )

    if change_type == "zero_prices":
        return (
            f"🔴 FORMAT CHANGE — {village_id}",
            (
                f"The VTF page for **{village_id}** loaded but no prices were extracted.\n\n"
                f"**Found markers:** {', '.join(found) or 'none'}\n"
                f"**Missing markers:** {', '.join(missing) or 'none'}\n"
                f"HTML length: {html_len:,} chars | Tables found: {table_count}\n"
                f"Bands scraped: {bands_scraped} | Priced: {priced_bands}"
                f"{step_block}\n\n"
                "The price grid structure may have changed."
            ),
            _RED,
        )

    if change_type == "parse_failure":
        return (
            f"🟡 PARSE FAILURE — {village_id}",
            (
                f"Prices were scraped from **{village_id}** but dates or prices "
                f"could not be parsed.\n\n"
                f"Bands scraped: {bands_scraped} | Priced: {priced_bands}\n"
                f"HTML length: {html_len:,} chars | Tables found: {table_count}"
                f"{step_block}\n\n"
                "The date/price format on the page may have changed."
            ),
            _YELLOW,
        )

    if change_type == "hard_failure":
        return (
            f"🚨 HARD FAILURE — {village_id}",
            (
                f"Hard scrape failure for **{village_id}** "
                f"(HTTP blocked, crash, or unreachable page)."
                f"{step_block}"
            ),
            _RED,
        )

    # partial / unknown
    return (
        f"🟡 PARTIAL FORMAT CHANGE — {village_id}",
        (
            f"Some data extracted from **{village_id}** but with errors.\n\n"
            f"**Found markers:** {', '.join(found) or 'none'}\n"
            f"**Missing markers:** {', '.join(missing) or 'none'}\n"
            f"Bands scraped: {bands_scraped} | Priced: {priced_bands}"
            f"{step_block}"
        ),
        _YELLOW,
    )


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def notify_scrape_failure(summary: dict) -> None:
    """
    Send a Discord alert when a single village scrape fails or returns
    incomplete data.  Called from task_scrape_village_tariffs when ok=False.

    Embed includes:
      • High-level Reason (step + code + why)
      • Errors by Step (full pipeline trail)
    """
    title, reason, colour = _classify_failure(summary)

    fields = [
        {"name": "Village",         "value": summary.get("village_id", "—"),   "inline": True},
        {"name": "URL",             "value": _format_urls_field(summary),     "inline": True},
        {"name": "Bands scraped",   "value": str(summary.get("bands_scraped", 0)),  "inline": True},
        {"name": "Priced bands",    "value": str(summary.get("priced_bands", 0)),   "inline": True},
        {"name": "Bands proposed",  "value": str(summary.get("bands_proposed", 0)), "inline": True},
        {"name": "Approval ID",     "value": str(summary.get("approval_id") or "—"), "inline": True},
        {"name": "Reason (step + code)", "value": reason[:1024],               "inline": False},
    ]

    all_errors = _all_errors(summary)
    if all_errors:
        fields.append({
            "name":   "Errors by Step (where it failed)",
            "value":  format_errors_by_step(all_errors),
            "inline": False,
        })

    _post({
        "embeds": [{
            "title":     title,
            "color":     colour,
            "timestamp": _now_iso(),
            "fields":    fields,
            "footer":    {"text": "VTF Tariff Scraper · Step-by-step failure report"},
        }]
    })
    logger.info("notify_scrape_failure: alert sent for village=%s colour=%s",
                summary.get("village_id"),
                "RED" if colour == _RED else "YELLOW")


def notify_format_change(summary: dict) -> None:
    """
    Send a Discord alert specifically for format change detection.
    Called when the scraper detects that the VTF page structure has changed.
    """
    title, reason, colour = _classify_format_change(summary)

    fc = summary.get("format_change") or {}
    fields = [
        {"name": "Village",         "value": summary.get("village_id", "—"),   "inline": True},
        {"name": "Change type",     "value": fc.get("change_type", "—"),       "inline": True},
        {"name": "HTML length",     "value": str(fc.get("html_length", 0)),    "inline": True},
        {"name": "Tables found",    "value": str(fc.get("table_count", 0)),    "inline": True},
        {"name": "Bands scraped",   "value": str(fc.get("bands_scraped", 0)),  "inline": True},
        {"name": "Priced bands",    "value": str(fc.get("priced_bands", 0)),   "inline": True},
        {"name": "Details",         "value": reason[:1024],                    "inline": False},
    ]

    scrape_errors = list(summary.get("scrape_errors") or [])
    if scrape_errors:
        fields.append({
            "name":   "Pipeline Errors (step + code)",
            "value":  format_errors_by_step(scrape_errors, limit=5),
            "inline": False,
        })

    _post({
        "embeds": [{
            "title":     title,
            "color":     colour,
            "timestamp": _now_iso(),
            "fields":    fields,
            "footer":    {"text": "VTF Tariff Scraper · Format-change detector"},
        }]
    })
    logger.info("notify_format_change: alert sent for village=%s type=%s",
                summary.get("village_id"), fc.get("change_type"))


def notify_scrape_success(summary: dict) -> None:
    """
    Green (or yellow-with-warnings) alert when a village scrape succeeds.

    Enabled by default (TARIFF_SCRAPER_NOTIFY_SUCCESS). Set to False to silence.

    Colour:
      🟢 GREEN  — clean success (no scrape/build step errors)
      🟡 YELLOW — success but some pipeline steps warned (e.g. HTTP failed,
                  Playwright/LLM fallback recovered)
    """
    if not _notify_success_enabled():
        return

    scrape_errors = list(summary.get("scrape_errors") or [])
    warnings = scrape_errors  # non-fatal step warnings (ok=True already excludes build_errors)

    if warnings:
        colour = _YELLOW
        title = f"🟡 Scrape OK (with warnings) — {summary.get('village_id')}"
        reason = (
            "Village scraped successfully (priced bands + approval staged), "
            "but some earlier pipeline steps reported errors. "
            "Fallback path recovered the data."
        )
    else:
        colour = _GREEN
        title = f"✅ Scrape OK — {summary.get('village_id')}"
        reason = "Village scraped successfully. Priced bands staged for approval."

    fields = [
        {"name": "Village",         "value": summary.get("village_id", "—"),   "inline": True},
        {"name": "URL",             "value": _format_urls_field(summary),     "inline": True},
        {"name": "Priced bands",    "value": str(summary.get("priced_bands", 0)),    "inline": True},
        {"name": "Bands proposed",  "value": str(summary.get("bands_proposed", 0)),  "inline": True},
        {"name": "Approval ID",     "value": str(summary.get("approval_id") or "—"), "inline": True},
        {"name": "Bands scraped",   "value": str(summary.get("bands_scraped", 0)),   "inline": True},
        {"name": "Result",          "value": reason[:1024],                         "inline": False},
    ]

    if warnings:
        fields.append({
            "name":   "Step warnings (recovered)",
            "value":  format_errors_by_step(warnings),
            "inline": False,
        })

    _post({
        "embeds": [{
            "title":     title,
            "color":     colour,
            "timestamp": _now_iso(),
            "fields":    fields,
            "footer":    {"text": "VTF Tariff Scraper · Success"},
        }]
    })
    logger.info(
        "notify_scrape_success: alert sent for village=%s colour=%s",
        summary.get("village_id"),
        "YELLOW" if warnings else "GREEN",
    )


def notify_batch_summary(results: list[dict]) -> None:
    """
    Send a single summary embed after task_scrape_all_village_tariffs
    finishes all villages.

    Colour:
      🟢 GREEN  — all villages OK
      🟡 YELLOW — some failed (< 50%)
      🔴 RED    — majority failed, or any format change detected
    """
    total   = len(results)
    ok      = sum(1 for r in results if r.get("ok"))
    failed  = total - ok

    failed_villages = [r.get("village_id", "?") for r in results if not r.get("ok")]

    format_changed = []
    for r in results:
        fc = r.get("format_change") or {}
        if fc.get("change_detected"):
            format_changed.append({
                "village_id": r.get("village_id", "?"),
                "change_type": fc.get("change_type", "unknown"),
            })

    colour = _GREEN if failed == 0 else (_RED if (total and failed > total // 2) else _YELLOW)
    title  = (
        f"✅ Batch scrape complete — {ok}/{total} OK"
        if failed == 0
        else f"⚠️ Batch scrape — {failed}/{total} villages FAILED"
    )

    fields = [
        {"name": "Total villages", "value": str(total),  "inline": True},
        {"name": "OK",             "value": str(ok),      "inline": True},
        {"name": "Failed",         "value": str(failed),  "inline": True},
    ]
    if failed_villages:
        # Include a short primary reason per failed village when available
        failed_lines = []
        for r in results:
            if r.get("ok"):
                continue
            vid = r.get("village_id", "?")
            primary = _primary_error(r)
            if primary:
                failed_lines.append(
                    f"**{vid}** — {primary['step']}: {primary['reason'][:120]}"
                )
            else:
                failed_lines.append(f"**{vid}**")
        fields.append({
            "name":   "Failed villages (step + reason)",
            "value":  "\n".join(failed_lines)[:1024] or ", ".join(failed_villages)[:1024],
            "inline": False,
        })

    if format_changed:
        by_type: dict[str, list[str]] = {}
        for fc in format_changed:
            by_type.setdefault(fc["change_type"], []).append(fc["village_id"])
        lines = []
        for ctype, villages in by_type.items():
            lines.append(f"**{ctype}**: {', '.join(villages)}")
        fields.append({
            "name":   "⚠️ Format changes detected",
            "value":  "\n".join(lines)[:1024],
            "inline": False,
        })
        colour = _RED

    _post({
        "embeds": [{
            "title":     title,
            "color":     colour,
            "timestamp": _now_iso(),
            "fields":    fields,
            "footer":    {"text": "VTF Tariff Scraper · Batch run"},
        }]
    })
    logger.info("notify_batch_summary: sent — ok=%d failed=%d format_changes=%d",
                ok, failed, len(format_changed))


def notify_dp_remise_mismatch(summary: dict) -> None:
    """
    Yellow alert when the LLM-based DP remise verification disagrees with
    the regex/static reading used to derive DP prices from PC.

    This is a diagnostic-only alert — it never blocks a scrape or an
    approval. It exists so staff can catch the VTF site changing its
    demi-pension discount wording/percentage before it silently goes stale.

    Called from task_scrape_village_tariffs when
    summary["dp_verification"]["checked"] is True and ["match"] is False.
    """
    dp = summary.get("dp_verification") or {}

    def _pct(v):
        return f"{float(v) * 100:.0f}%" if v is not None else "—"

    fields = [
        {"name": "Village",        "value": summary.get("village_id", "—"), "inline": True},
        {"name": "Regex remise",   "value": _pct(dp.get("regex_remise")),   "inline": True},
        {"name": "Regex source",   "value": dp.get("regex_derivation") or "—", "inline": True},
        {"name": "LLM remise",     "value": _pct(dp.get("llm_remise")),     "inline": True},
        {"name": "Details",        "value": (dp.get("note") or "—")[:1024], "inline": False},
    ]

    _post({
        "embeds": [{
            "title":     "🟡 DP remise mismatch — regex vs. LLM disagree",
            "color":     _YELLOW,
            "timestamp": _now_iso(),
            "fields":    fields,
            "footer":    {"text": "VTF Tariff Scraper · DP remise verification (diagnostic only)"},
        }]
    })
    logger.info(
        "notify_dp_remise_mismatch: alert sent for village=%s regex=%s llm=%s",
        summary.get("village_id"), dp.get("regex_remise"), dp.get("llm_remise"),
    )
