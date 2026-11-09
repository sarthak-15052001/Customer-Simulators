"""DP remise verification — cross-checks the regex/static remise reading
against an independent LLM read of the same page.

Client request (verbatim intent): DP is currently derived from PC using a
½-pension "remise" percentage that ``scraper._extract_dp_remise_info`` reads
with a regex. When the regex finds an explicit "= X% de remise" on the page
it uses that number (``DERIVATION_STATED``); when it only sees "demi-pension
possible" with no number, it silently assumes the static default of 15%
(``DEFAULT_DP_REMISE`` in scraper.py, ``DERIVATION_ASSUMED``).

The client's worry: if VTF changes how that footnote is worded, the regex
may stop matching (or keep matching something stale) and the assumed 15%
would then be *wrong* — with nothing surfacing the drift.

This module does NOT replace the regex and does NOT change any prices. It
runs a **second, independent** extraction of the same remise percentage
using the local LLM already wired up for tariff_scraper (LM Studio), then
compares the two readings:

  • Both agree (same %, or both "no explicit remise stated")  → silent, logged
  • They disagree                                              → Discord alert
                                                                   (does not
                                                                   block the
                                                                   scrape or
                                                                   the pending
                                                                   TariffApproval)

Design rules (mirrors llm_fallback.py):
  • Verification only — never writes prices, never blocks a scrape
  • Runs automatically whenever a DP band was *derived* (not directly
    scraped) — no separate on/off switch, it's part of the normal scrape
  • Any failure (LLM down, bad JSON, etc.) is caught and reported as
    "unable to verify" — never raised, never treated as a mismatch
  • Uses the exact same local model / LM Studio config as llm_fallback.py

Env vars (set in .env):
  DP_VERIFICATION_TOLERANCE_PP — allowed drift in percentage points before
                                  it counts as a mismatch (default: 0, i.e.
                                  any difference is reported)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from apps.tariff_scraper.services.llm_fallback import _call_lmstudio, _setting
from apps.tariff_scraper.services.scraper import (
    DERIVATION_ASSUMED,
    DERIVATION_STATED,
    DpRemiseInfo,
    _extract_dp_remise_info,
)

logger = logging.getLogger("scraper")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _tolerance_pp() -> Decimal:
    """Allowed drift, in percentage points, before flagging a mismatch."""
    try:
        return Decimal(_setting("DP_VERIFICATION_TOLERANCE_PP", "0"))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class DpVerificationResult:
    """Outcome of comparing the regex-derived remise vs. the LLM's reading."""
    village_id: str
    checked: bool = False                       # False if skipped/disabled/errored
    regex_remise: Optional[Decimal] = None       # fraction, e.g. 0.15
    regex_derivation: str = ""                   # derived_stated | derived_assumed | ""
    llm_remise: Optional[Decimal] = None         # fraction, e.g. 0.15, or None = "no remise found"
    match: bool = True                           # True unless a real mismatch is found
    note: str = ""                                # human-readable explanation


# ---------------------------------------------------------------------------
# LLM prompt + parsing
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """You are reading text extracted from a French vacation-village \
pricing page. Find the discount percentage ("remise") that applies to the \
"demi-pension" (half-board) option compared to "pension complète" (full-board).

Only report a number if the text EXPLICITLY states a percentage discount for \
demi-pension (e.g. "1/2 pension = 15% de remise"). If demi-pension is merely \
mentioned as available/possible with NO percentage given, or not mentioned at \
all, report null.

Respond with ONLY a JSON object, nothing else, in this exact shape:
{{"remise_percent": <number or null>}}

TEXT:
{page_text}
"""

_JSON_RE = re.compile(r"\{[^{}]*\}")


def _extract_llm_remise(page_text: str) -> tuple[Optional[Decimal], bool]:
    """Call the LLM and parse its remise reading.

    Returns (remise_fraction_or_None, call_succeeded).
    call_succeeded=False means the LLM couldn't be reached or returned
    something unparseable — caller should treat this as "unable to verify",
    not as a mismatch.
    """
    # Keep the prompt small — the LLM only needs the footnote area, but we
    # don't have a reliable footnote-only excerpt here, so cap total length.
    excerpt = page_text[:4000]
    prompt = _PROMPT_TEMPLATE.format(page_text=excerpt)

    response = _call_lmstudio(prompt, temperature=0.0)
    if response is None:
        return None, False

    m = _JSON_RE.search(response)
    if not m:
        logger.warning("dp_verification: no JSON object in LLM response: %r", response[:200])
        return None, False

    try:
        data = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        logger.warning("dp_verification: unparseable JSON from LLM: %r", m.group(0)[:200])
        return None, False

    raw = data.get("remise_percent", None)
    if raw is None:
        return None, True

    try:
        pct = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        logger.warning("dp_verification: non-numeric remise_percent from LLM: %r", raw)
        return None, False

    if pct < 0 or pct > 100:
        logger.warning("dp_verification: out-of-range remise_percent from LLM: %s", pct)
        return None, False

    return (pct / Decimal(100)).quantize(Decimal("0.01")), True


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def _compare(
    regex_info: Optional[DpRemiseInfo],
    llm_remise: Optional[Decimal],
) -> tuple[bool, str]:
    """Returns (match, note)."""
    regex_remise = regex_info.remise if regex_info else None
    tolerance = _tolerance_pp() / Decimal(100)

    if regex_remise is None and llm_remise is None:
        return True, "Neither regex nor LLM found an explicit remise — consistent."

    if regex_remise is None and llm_remise is not None:
        return False, (
            f"LLM found an explicit remise of {llm_remise * 100}% on the page, "
            "but the regex found none (no DP derivation would have used it correctly)."
        )

    if regex_remise is not None and llm_remise is None:
        derivation_note = (
            "an explicitly stated value" if regex_info.derivation == DERIVATION_STATED
            else "the static default (page only said 'possible', no % given)"
        )
        return False, (
            f"Regex is using {regex_remise * 100}% ({derivation_note}), "
            "but the LLM could not find any explicit remise percentage on the page."
        )

    diff = abs(regex_remise - llm_remise)
    if diff > tolerance:
        return False, (
            f"Regex reads {regex_remise * 100}% "
            f"({'explicit' if regex_info.derivation == DERIVATION_STATED else 'assumed default'}), "
            f"LLM independently reads {llm_remise * 100}% — mismatch of "
            f"{diff * 100} percentage points."
        )

    return True, f"Regex and LLM agree on {regex_remise * 100}% remise."


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def verify_dp_remise(html: str, village_id: str) -> DpVerificationResult:
    """Independently verify the DP remise % using the LLM, and compare it
    against the regex-derived value already used for this scrape.

    Never raises. Never touches prices/derivation — read-only diagnostic.
    """
    result = DpVerificationResult(village_id=village_id)

    if not html:
        result.note = "No HTML available to verify"
        return result

    try:
        import html as html_lib
        page_text = re.sub(r"<[^>]+>", " ", html)
        page_text = html_lib.unescape(page_text)

        regex_info = _extract_dp_remise_info(page_text)
        result.regex_remise = regex_info.remise if regex_info else None
        result.regex_derivation = regex_info.derivation if regex_info else ""

        llm_remise, ok = _extract_llm_remise(page_text)
        if not ok:
            result.note = "Could not get a usable reading from the LLM (unable to verify)"
            return result

        result.llm_remise = llm_remise
        result.checked = True
        result.match, result.note = _compare(regex_info, llm_remise)

        logger.info(
            "verify_dp_remise: village=%s regex=%s llm=%s match=%s",
            village_id, result.regex_remise, result.llm_remise, result.match,
        )
        return result

    except Exception as exc:
        logger.exception("verify_dp_remise: village=%s unexpected error", village_id)
        result.note = f"Verification errored: {exc}"
        result.checked = False
        result.match = True  # never flag a mismatch on our own error
        return result
