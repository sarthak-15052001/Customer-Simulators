"""Discord alert service for the header_scraper app.

Sends a Discord embed when a homepage banner scrape succeeds, fails, or is
unchanged, so the client can see *exactly* which pipeline step failed, which
file/function produced the error, and why — same approach used for the
tariff_scraper alerts (apps/tariff_scraper/services/alerts.py).

ALERT COLOUR SCHEME:
  🟢 GREEN  — Banner scraped and published successfully (content changed)
  🟡 YELLOW — Parse failure (banner HTML found but 0 segments parsed)
  🔴 RED    — Hard failure (HTTP/Playwright/LLM all failed — nothing scraped)

Error format from scrape.py / sync.py:
  "Step N (Label) | file.py → function() | reason detail"

Usage (called from tasks.py after every scrape):
    if result["status"] == HeaderBannerSnapshot.STATUS_SUCCESS:
        notify_scrape_success(result)
    elif result["status"] in (STATUS_FETCH_FAILED, STATUS_PARSE_FAILED):
        notify_scrape_failure(result)
    # STATUS_UNCHANGED is intentionally silent — no alert noise on no-ops.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from common.discord import add_origin_to_embeds
from django.conf import settings

logger = logging.getLogger("header_scraper.alerts")

# Discord embed colours
_RED = 0xED4245  # failure / crash
_YELLOW = 0xFEE75C  # warning (parse failure)
_GREEN = 0x57F287  # success

# "Step 1 (HTTP Fetch) | scrape.py → scrape_header_banner_html_http() | HTTP 404"
_STEP_ERROR_RE = re.compile(
    r"^(?P<step>Step\s+\d+\s*\([^)]+\))\s*\|\s*"
    r"(?P<source>[^|]+?)\s*\|\s*"
    r"(?P<reason>.+)$",
    re.DOTALL,
)

# Splits a cascaded error string ("Step 1 ... | Step 2 ... | Step 3 ...")
# back into one entry per step, without splitting inside a single step's
# own "source | reason" separators.
_STEP_SPLIT_RE = re.compile(r"(?=Step\s+\d+\s*\()")


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


def _notify_success_enabled() -> bool:
    """Green success alerts are ON by default (client requirement)."""
    return getattr(settings, "HEADER_SCRAPER_NOTIFY_SUCCESS", True)


# ---------------------------------------------------------------------------
# Parse "Step N | file → function | reason" into structured parts
# ---------------------------------------------------------------------------

def parse_pipeline_error(error: Any) -> dict[str, str]:
    """
    Split a pipeline error string into step / source / reason.

    Expected shape:
      "Step 2 (Playwright Scrape) | scrape.py → scrape_header_banner_html_playwright() | ..."

    Falls back gracefully for plain strings (e.g. "Unsupported language 'XX'.").
    """
    text = str(error).strip()
    match = _STEP_ERROR_RE.match(text)
    if match:
        return {
            "step": match.group("step").strip(),
            "source": match.group("source").strip(),
            "reason": match.group("reason").strip(),
        }

    # "tasks.py → task_scrape_header_banner() | Unhandled exception: ..."
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


def split_error_cascade(error_text: str) -> list[str]:
    """
    Split a combined cascade string (HTTP → Playwright → LLM fallback, each
    joined by " | " in scrape_header_banner_html) back into one error per
    tier, so each tier can be rendered as its own step block.
    """
    text = (error_text or "").strip()
    if not text:
        return []
    parts = [p.strip(" |") for p in _STEP_SPLIT_RE.split(text) if p.strip(" |")]
    return parts or [text]


def format_errors_by_step(errors: list, *, limit: int = 8) -> str:
    """
    Render errors as a client-readable step-by-step block for Discord.

    Example:
      **Step 1 (HTTP Fetch)**
      📍 `scrape.py → scrape_header_banner_html_http()`
      ❌ HTTP fetch failed: 403 Forbidden
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


def _primary_error(steps: list[str]) -> Optional[dict[str, str]]:
    """The final tier's error is the ultimate reason the scrape gave up."""
    if not steps:
        return None
    return parse_pipeline_error(steps[-1])


def _reason_from_primary(primary: Optional[dict[str, str]], fallback: str) -> str:
    if not primary:
        return fallback
    return (
        f"{primary['step']}\n"
        f"Code: `{primary['source']}`\n"
        f"Reason: {primary['reason']}"
    )


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def notify_scrape_failure(result: dict) -> None:
    """
    Send a Discord alert when a header-banner scrape fails (fetch_failed —
    HTTP + Playwright + LLM fallback all failed — or parse_failed — banner
    HTML found but 0 segments parsed).

    Called from tasks.py whenever sync_language()/sync_all_languages()
    returns a non-success, non-unchanged status.

    Embed includes:
      • High-level Reason (step + code + why)
      • Errors by Step (full pipeline trail — HTTP → Playwright → LLM)
    """
    language = result.get("language", "—")
    status = result.get("status", "—")
    steps = split_error_cascade(result.get("error", ""))
    primary = _primary_error(steps)

    if status == "parse_failed":
        title = f"🟡 Banner PARSE FAILED — {language}"
        colour = _YELLOW
        fallback_reason = "Banner HTML was scraped but 0 segments could be parsed."
    else:
        title = f"🚨 Banner SCRAPE FAILED — {language}"
        colour = _RED
        fallback_reason = "HTTP fetch, Playwright, and LLM fallback all failed — no banner extracted."

    reason = _reason_from_primary(primary, fallback_reason)

    fields = [
        {"name": "Language", "value": language, "inline": True},
        {"name": "Status", "value": status, "inline": True},
        {"name": "URL", "value": (result.get("source_url") or "—")[:1024], "inline": True},
        {"name": "Reason (step + code)", "value": reason[:1024], "inline": False},
    ]

    if steps:
        fields.append({
            "name": "Errors by Step (where it broke)",
            "value": format_errors_by_step(steps),
            "inline": False,
        })

    _post({
        "embeds": [{
            "title": title,
            "color": colour,
            "timestamp": _now_iso(),
            "fields": fields,
            "footer": {"text": "VTF Header Scraper · Step-by-step failure report"},
        }]
    })
    logger.info(
        "notify_scrape_failure: alert sent for language=%s status=%s",
        language, status,
    )


def notify_scrape_success(result: dict) -> None:
    """
    Green alert when a header banner is scraped and published with new
    content. Enabled by default (HEADER_SCRAPER_NOTIFY_SUCCESS).

    Not called for STATUS_UNCHANGED — that happens on almost every poll
    and would flood the channel.
    """
    if not _notify_success_enabled():
        return

    language = result.get("language", "—")
    fields = [
        {"name": "Language", "value": language, "inline": True},
        {"name": "URL", "value": (result.get("source_url") or "—")[:1024], "inline": True},
        {"name": "Content hash", "value": (result.get("content_hash") or "—")[:12], "inline": True},
        {
            "name": "Banner text",
            "value": (result.get("plain_text") or "—")[:1024],
            "inline": False,
        },
        {"name": "Result", "value": "Banner content changed and was published.", "inline": False},
    ]

    _post({
        "embeds": [{
            "title": f"✅ Banner updated — {language}",
            "color": _GREEN,
            "timestamp": _now_iso(),
            "fields": fields,
            "footer": {"text": "VTF Header Scraper · Success"},
        }]
    })
    logger.info("notify_scrape_success: alert sent for language=%s", language)


def notify_batch_summary(results: list[dict]) -> None:
    """
    Send a single summary embed after task_scrape_header_banner finishes
    scraping all languages (FR + GB).

    Colour:
      🟢 GREEN  — all languages OK (success or unchanged)
      🟡 YELLOW — some parse failures, none hard-failed
      🔴 RED    — any language hard fetch-failed
    """
    total = len(results)
    fetch_failed = [r for r in results if r.get("status") == "fetch_failed"]
    parse_failed = [r for r in results if r.get("status") == "parse_failed"]
    ok = total - len(fetch_failed) - len(parse_failed)

    if fetch_failed:
        colour = _RED
    elif parse_failed:
        colour = _YELLOW
    else:
        colour = _GREEN

    title = (
        f"✅ Header scrape complete — {ok}/{total} OK"
        if not fetch_failed and not parse_failed
        else f"⚠️ Header scrape — {len(fetch_failed) + len(parse_failed)}/{total} language(s) FAILED"
    )

    fields = [
        {"name": "Total languages", "value": str(total), "inline": True},
        {"name": "OK", "value": str(ok), "inline": True},
        {"name": "Failed", "value": str(len(fetch_failed) + len(parse_failed)), "inline": True},
    ]

    failing = fetch_failed + parse_failed
    if failing:
        lines = []
        for r in failing:
            steps = split_error_cascade(r.get("error", ""))
            primary = _primary_error(steps)
            lang = r.get("language", "?")
            if primary:
                lines.append(f"**{lang}** — {primary['step']}: {primary['reason'][:120]}")
            else:
                lines.append(f"**{lang}** — {r.get('status', '?')}")
        fields.append({
            "name": "Failed languages (step + reason)",
            "value": "\n".join(lines)[:1024],
            "inline": False,
        })

    _post({
        "embeds": [{
            "title": title,
            "color": colour,
            "timestamp": _now_iso(),
            "fields": fields,
            "footer": {"text": "VTF Header Scraper · Batch run"},
        }]
    })
    logger.info(
        "notify_batch_summary: sent — ok=%d fetch_failed=%d parse_failed=%d",
        ok, len(fetch_failed), len(parse_failed),
    )
