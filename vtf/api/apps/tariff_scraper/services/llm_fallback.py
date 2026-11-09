"""LLM fallback — extracts tariff bands when deterministic scraping fails.

Activated only when HTTP + Playwright both return zero priced bands.
Uses a tiny local LLM (~350M) via LM Studio's OpenAI-compatible API
at ``localhost:1234/v1``. Successful scrapes never call this module.

Design rules (mirrored from scraper.py — same fields only):
  • PC       → adult weekly rate from grille, plus any recognized child
               age-band columns (e.g. "6 à - 11 ans") via
               scraper._is_child_column_header — same detection scraper.py
               uses. Header row must align 1:1 with price cells or it falls
               back to adult-only (legacy behavior for unrecognized layouts).
  • DP       → direct rate from grille when present, else derived from the
               matching PC band (adult or child alike) using the ½-pension
               remise (via _extract_dp_remise) — mirrors
               scraper._derive_dp_bands_from_pc.
  • LOC      → flat weekly unit rate per column
  • Dates    → Python chunker only (LLM must not invent dates)
  • Never    → generic/unlabeled child columns, supplements, or commercial
               discounts (only age-range labels like "2-5 ans" are trusted)
  • LLM only copies price numbers — dates, colspan, Gratuit→0 all done in Python
  • LLM never activates pricing directly — goes through TariffApproval

Env vars (set in .env):
  LLM_FALLBACK_ENABLED   — master switch (default: false)
  LMSTUDIO_BASE_URL      — LM Studio API base (default: http://localhost:1234/v1)
  LMSTUDIO_MODEL         — model name (default: luth-lfm2-350m)
  LLM_MAX_RETRIES        — max LLM retries before regex fallback (default: 2)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from apps.tariff_scraper.services.scraper import (
    RawPriceBand,
    _parse_price,
    parse_vtf_period_cell,
    _extract_dp_remise,
    _expand_colspan_text,
    _is_adult_column_header,
    _is_child_column_header,
    _detect_grid_formule,
    DEFAULT_DP_REMISE,
    DERIVATION_SCRAPED,
)

logger = logging.getLogger("scraper")

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _setting(name: str, default: str = "") -> str:
    """Read a Django setting with fallback to env."""
    try:
        from django.conf import settings
        val = getattr(settings, name, None)
        if val is not None:
            return str(val)
    except Exception:
        pass
    import os
    return os.environ.get(name, default)


def llm_fallback_enabled() -> bool:
    return _setting("LLM_FALLBACK_ENABLED", "false").lower() in ("true", "1", "yes")


def _base_url() -> str:
    return _setting("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")


def _model() -> str:
    return _setting("LMSTUDIO_MODEL", "luth-lfm2-350m")


def _max_retries() -> int:
    try:
        return int(_setting("LLM_MAX_RETRIES", "2"))
    except (ValueError, TypeError):
        return 2


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RowPayload:
    """One preprocessed row ready to send to the LLM."""
    row_index: int
    season: str
    period_text: str
    date_start: Optional[date]
    date_end: Optional[date]
    cells: list[str]          # pre-cleaned price cell texts (€ stripped, Gratuit→0)
    formule_hint: str = ""    # "PC" or "LOC" if detectable from header
    unit_type: str = ""       # scraped Adultes header for PC; blank for LOC rows
                              # (LOC unit labels live in cells)
    column_labels: list[str] = field(default_factory=list)
                              # PC/DP only: header label per `cells` index (e.g.
                              # "Adultes", "6 à - 11 ans"), aligned 1:1 with
                              # `cells` when the header row was recognized.
                              # Empty when alignment couldn't be established —
                              # callers must fall back to adult-only (index 0).


@dataclass
class FootnoteInfo:
    """DP remise only — never supplements or commercial discounts."""
    dp_remise: Optional[Decimal] = None   # e.g. 0.15 for 15% off
    raw_text: str = ""                     # demi-pension context for logging


# ---------------------------------------------------------------------------
# Step 1: Chunker — split HTML table into row payloads
# ---------------------------------------------------------------------------

# Regex patterns for price cell preprocessing
_GRATUIT_RE = re.compile(r"gratuit", re.IGNORECASE)
_EURO_RE = re.compile(r"\s*€\s*")
_NON_BREAKING_SPACE_RE = re.compile(r"[\xa0\u202f]")


def _preprocess_cell(text: str) -> str:
    """Clean a price cell: strip €, convert Gratuit→0, normalize spaces."""
    text = _NON_BREAKING_SPACE_RE.sub("", text)
    text = _EURO_RE.sub("", text)
    text = _GRATUIT_RE.sub("0", text)
    text = text.strip()
    return text


def _parse_period_text(text: str) -> tuple[Optional[date], Optional[date]]:
    """Extract start/end dates from a period cell."""
    ranges = parse_vtf_period_cell(text)
    if ranges:
        return ranges[0]
    return None, None


def chunk_grille_html(html: str) -> list[RowPayload]:
    """Parse HTML and split into one RowPayload per data row.

    Handles colspan expansion on price cells only (period cells are never
    duplicated into the price matrix — that would steal the adult column).
    """
    import html as html_lib

    rows_out: list[RowPayload] = []

    for table_m in re.finditer(r"<table\b[^>]*>([\s\S]*?)</table>", html, re.I):
        block = table_m.group(0)

        tr_list = list(re.finditer(r"<tr\b[^>]*>([\s\S]*?)</tr>", block, re.I))
        if not tr_list:
            continue

        row_idx = 0
        formule_hint = ""
        pension_unit_type = ""  # scraped Adultes header text from the page
        formule_column_labels: list[str] = []  # header label per price column
                                                 # (PC/DP only), colspan-expanded
        for tr_m in tr_list:
            tr_html = tr_m.group(0)

            # (text, colspan, attrs) — expand price cells later using align
            cells_meta: list[tuple[str, int, str]] = []
            for td_m in re.finditer(
                r"<t[hd]\b([^>]*)>([\s\S]*?)</t[hd]>", tr_html, re.I
            ):
                attrs = td_m.group(1) or ""
                inner = td_m.group(2)
                colspan_m = re.search(r'colspan=["\']?(\d+)', attrs)
                colspan = int(colspan_m.group(1)) if colspan_m else 1
                text = re.sub(r"<br\s*/?>", " ", inner, flags=re.I)
                text = re.sub(r"<[^>]+>", " ", text)
                text = html_lib.unescape(text)
                text = re.sub(r"\s+", " ", text).strip()
                if text:
                    cells_meta.append((text, colspan, attrs))

            # A row only counts as a section header (PC/DP/LOC) if it looks
            # like one: at least two real cells (label + period/unit
            # columns, e.g. "Pension complète | Période | Adultes"), and
            # none of its cells parse as a date period. Without these
            # guards, a single-cell footnote row like "Demi-pension = 15%
            # de remise" — which collapses to one cells_meta entry even
            # with colspan — matches the same keywords as a real header
            # and hijacks formule_hint for every row that follows it.
            has_period = any(_parse_period_text(text)[0] for text, _, _ in cells_meta)
            if len(cells_meta) >= 2 and not has_period:
                header_text = " ".join(text for text, _, _ in cells_meta)
                detected = _detect_grid_formule(header_text)
                if detected:
                    formule_hint = detected
                    pension_unit_type = ""
                    formule_column_labels = []
                    if formule_hint in {"PC", "DP"}:
                        # Colspan-expand header cells (skip the leading group
                        # label and any "Période" cell) so labels line up
                        # 1:1 with the colspan-expanded price cells below.
                        labels: list[str] = []
                        for cell, cs, _attrs in cells_meta[1:]:
                            low = cell.strip().lower()
                            if "période" in low or "periode" in low:
                                continue
                            for _ in range(max(cs, 1)):
                                labels.append(cell.strip())
                        formule_column_labels = labels
                        for cell in labels:
                            if _is_adult_column_header(cell):
                                pension_unit_type = cell
                                break
                    continue

            if len(cells_meta) < 2:
                continue

            joined_lower = " ".join(t for t, _, _ in cells_meta).lower()
            if any(kw in joined_lower for kw in [
                "séjour semaine", "sejour semaine", "adultes", "logement",
            ]):
                continue

            period_text = ""
            period_idx = -1
            for ci, (cell, _cs, _attrs) in enumerate(cells_meta):
                start, end = _parse_period_text(cell)
                if start and end:
                    period_text = cell.strip()
                    period_idx = ci
                    break

            if period_idx < 0 or not period_text:
                continue

            start, end = _parse_period_text(period_text)
            if not start or not end:
                continue

            # Expand colspan only on price cells; skip further date-like cells.
            # Respect align so right-aligned merged Gratuit* leaves a blank
            # older age column (Lacanau) while center duplicates (Agde).
            price_cells: list[str] = []
            for cell, cs, attrs in cells_meta[period_idx + 1:]:
                if _parse_period_text(cell)[0]:
                    continue
                cleaned = _preprocess_cell(cell)
                expanded_slots = _expand_colspan_text(cleaned, cs, attrs)
                # Each slot is already either `cleaned` or "" (blank
                # placeholders from right/left align on a free-child cell);
                # append it as-is instead of re-deriving it from `cleaned`.
                price_cells.extend(expanded_slots)

            if not price_cells:
                continue

            # Only trust column_labels when it lines up 1:1 with the
            # colspan-expanded price cells — otherwise leave it empty so
            # callers fall back to the legacy adult-only behavior.
            row_column_labels = (
                list(formule_column_labels)
                if formule_hint in {"PC", "DP"}
                and len(formule_column_labels) == len(price_cells)
                else []
            )

            rows_out.append(RowPayload(
                row_index=row_idx,
                season="",
                period_text=period_text,
                date_start=start,
                date_end=end,
                cells=price_cells,
                formule_hint=formule_hint,
                unit_type=pension_unit_type if formule_hint in {"PC", "DP"} else "",
                column_labels=row_column_labels,
            ))
            row_idx += 1

    return rows_out


# ---------------------------------------------------------------------------
# Step 2: Footnotes extractor
# ---------------------------------------------------------------------------

def extract_footnotes(html: str) -> FootnoteInfo:
    """Extract ½-pension remise only (same source as scraper._extract_dp_remise).

    Does not extract age-group rules, supplements, or commercial discounts.
    """
    import html as html_lib

    page_text = re.sub(r"<[^>]+>", " ", html)
    page_text = html_lib.unescape(page_text)

    info = FootnoteInfo(raw_text="")
    remise = _extract_dp_remise(page_text)
    if remise is not None:
        info.dp_remise = remise

    m = re.search(r"(?:1/2|½|demi)[-\s]?pension[^.]{0,200}", page_text, re.IGNORECASE)
    if m:
        info.raw_text = m.group(0).strip()

    return info


# ---------------------------------------------------------------------------
# Step 3: LLM price extraction (LM Studio API)
# ---------------------------------------------------------------------------

def _recognized_columns(row: RowPayload) -> list[tuple[int, str, str]]:
    """PC/DP only: (cell index, label, role) for the adult + child columns.

    role is "adults" or "child". Uses ``row.column_labels`` when the chunker
    could align header labels to price cells 1:1. Falls back to the legacy
    adult-only column (index 0) when alignment wasn't established or no
    recognized labels were found — this is what every pre-existing page
    (and test) already relied on, so behavior there is unchanged.
    """
    if row.formule_hint == "LOC" or not row.cells:
        return []
    if row.column_labels and len(row.column_labels) == len(row.cells):
        cols: list[tuple[int, str, str]] = []
        for i, label in enumerate(row.column_labels):
            if _is_adult_column_header(label):
                cols.append((i, label, "adults"))
            elif _is_child_column_header(label):
                cols.append((i, label, "child"))
        if cols:
            return cols
    # Legacy fallback: adult weekly rate only (first price cell)
    label = row.unit_type or "Adultes"
    return [(0, label, "adults")]


def _cells_for_llm(row: RowPayload) -> list[str]:
    """Cells sent to the LLM.

    LOC: all unit columns. PC/DP: the adult column plus any recognized
    child age-band columns (order follows ``_recognized_columns``). Pages
    where the header row couldn't be aligned fall back to adult-only, same
    as before.
    """
    if not row.cells:
        return []
    if row.formule_hint == "LOC":
        return list(row.cells)
    return [row.cells[i] for i, _label, _role in _recognized_columns(row)]


def _build_prompt(row: RowPayload) -> str:
    """Build the LLM prompt for a single row.

    The LLM's only job: copy the price numbers from the pre-cleaned cells.
    """
    cells = _cells_for_llm(row)
    cells_str = ", ".join(cells) if cells else "empty"
    if row.formule_hint == "LOC" or len(cells) > 1:
        return (
            f"Extract the price numbers from these cells: [{cells_str}]\n"
            f"Return a JSON array of numbers, in the same order. Example: [469, 399]\n"
            f"If a cell is empty or 0, include 0.\n"
            f"JSON:"
        )
    return (
        f"Extract the adult price number from this cell: [{cells_str}]\n"
        f"Return a JSON array with one number. Example: [637]\n"
        f"If the cell is empty or 0, include 0.\n"
        f"JSON:"
    )


def _prices_match_payload(
    prices: list[Optional[Decimal]],
    cells: list[str],
) -> bool:
    """Reject hallucinations: every non-null price must appear in the cell text."""
    if len(prices) != len(cells):
        return False
    if not any(p is not None for p in prices):
        return False
    for price, cell in zip(prices, cells):
        if price is None:
            continue
        nums = {Decimal(n) for n in re.findall(r"\d+\.?\d*", cell)}
        if price not in nums and int(price) not in {int(n) for n in nums}:
            return False
    return True


def _call_lmstudio(prompt: str, temperature: float = 0.0) -> Optional[str]:
    """Call the LM Studio local API and return the response text."""
    import requests

    base = _base_url()
    model = _model()

    try:
        resp = requests.post(
            f"{base}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": 128,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
        return None


def _parse_prices_from_response(response: str) -> list[Optional[Decimal]]:
    """Extract price numbers from LLM response text.

    Tries JSON parsing first, then regex fallback.
    """
    # Try JSON array parsing
    try:
        # Find JSON array in response
        m = re.search(r"\[[\d\s,.\-]+\]", response)
        if m:
            arr = json.loads(m.group(0))
            result = []
            for v in arr:
                try:
                    d = Decimal(str(v))
                    result.append(d if d >= 0 else None)
                except Exception:
                    result.append(None)
            return result
    except Exception:
        pass

    # Regex fallback: find all numbers
    numbers = re.findall(r"\d+\.?\d*", response)
    result = []
    for n in numbers:
        try:
            d = Decimal(n)
            result.append(d if d >= 0 else None)
        except Exception:
            result.append(None)
    return result


def _regex_fallback_prices(cells: list[str]) -> list[Optional[Decimal]]:
    """Deterministic regex extraction when LLM fails."""
    results = []
    for cell in cells:
        results.append(_parse_price(cell))
    return results


def extract_row_prices(row: RowPayload) -> list[Optional[Decimal]]:
    """Extract prices from a row using LLM with regex fallback.

    For PC/DP: returns prices aligned to full row cells — the adult column
    plus any recognized child age-band columns are filled in; everything
    else (unrecognized columns) stays None. For LOC: returns one price per
    unit column.
    """
    cells = _cells_for_llm(row)
    if not cells:
        return []

    prompt = _build_prompt(row)
    max_retries = _max_retries()
    llm_prices: Optional[list[Optional[Decimal]]] = None

    for attempt in range(max_retries + 1):
        response = _call_lmstudio(prompt)
        if response:
            prices = _parse_prices_from_response(response)
            if prices and _prices_match_payload(prices, cells):
                llm_prices = prices
                break
            logger.debug(
                "LLM row %d attempt %d: invalid response (got %s prices, need %d)",
                row.row_index, attempt, len(prices) if prices else 0, len(cells),
            )
        else:
            logger.debug("LLM row %d attempt %d: no response", row.row_index, attempt)

    if llm_prices is None:
        logger.info(
            "LLM row %d: using regex fallback after %d attempts",
            row.row_index, max_retries,
        )
        llm_prices = _regex_fallback_prices(cells)

    if row.formule_hint == "LOC":
        return llm_prices

    # PC/DP: expand the (adult + child) result back to full row.cells
    # positions — everything not in `_recognized_columns` stays None.
    out: list[Optional[Decimal]] = [None] * len(row.cells)
    for (idx, _label, _role), price in zip(_recognized_columns(row), llm_prices or []):
        if idx < len(out):
            out[idx] = price
    return out


# ---------------------------------------------------------------------------
# Step 4: Map LLM output → RawPriceBand
# ---------------------------------------------------------------------------

def _derive_dp_bands(
    pc_bands: list[RawPriceBand],
    remise: Decimal,
    *,
    derivation: str = "derived_assumed",
) -> list[RawPriceBand]:
    """Derive DP bands from PC using ½-pension remise (same logic as scraper.py)."""
    dp_bands = []
    factor = (Decimal("1") - remise).quantize(Decimal("0.01"))
    for band in pc_bands:
        if band.formule != "PC" or band.scraped_price is None:
            continue
        pc_nightly = band.scraped_price / Decimal(7)
        dp_nightly = (pc_nightly * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        dp_price = dp_nightly * Decimal(7)
        dp_bands.append(RawPriceBand(
            formule="DP",
            source_page="llm_fallback",
            date_label=band.date_label,
            date_start=band.date_start,
            date_end=band.date_end,
            scraped_price=dp_price,
            is_available=True,
            unit_type=band.unit_type,  # same scraped Adultes header as PC
            nb_adults=1,
            derivation=derivation,
        ))
    return dp_bands


def llm_bands_to_raw_price_bands(
    rows: list[RowPayload],
    all_prices: list[list[Optional[Decimal]]],
    footnotes: FootnoteInfo,
) -> list[RawPriceBand]:
    """Map LLM-extracted prices to RawPriceBand list.

    Produces the exact same fields as scraper.py:
      • PC bands (adult weekly rate + any recognized child age-band rates)
        with source_page="llm_fallback"
      • DP bands (direct rate when present, else derived from each PC band —
        adult and child alike, same as scraper.py's _derive_dp_bands_from_pc)
      • LOC bands (flat unit rate per column)
    """
    bands: list[RawPriceBand] = []
    pc_bands: list[RawPriceBand] = []
    direct_dp_bands: list[RawPriceBand] = []

    for row, prices in zip(rows, all_prices):
        ranges = parse_vtf_period_cell(row.period_text) or []
        if not ranges and row.date_start and row.date_end:
            ranges = [(row.date_start, row.date_end)]
        if not ranges:
            continue

        if row.formule_hint == "LOC":
            for cell_text, price in zip(row.cells, prices):
                if price is None:
                    continue
                for start, end in ranges:
                    bands.append(RawPriceBand(
                        formule="LOC",
                        source_page="llm_fallback",
                        date_label=row.period_text,
                        date_start=start,
                        date_end=end,
                        scraped_price=price,
                        is_available=True,
                        unit_type=cell_text if cell_text else "",
                    ))
        else:
            # PC/DP — one band per recognized column: adult, plus any child
            # age-band columns detected via _is_child_column_header(). Pages
            # without a resolvable header row fall back to adult-only,
            # matching the previous behavior exactly.
            for idx, label, role in _recognized_columns(row):
                price = prices[idx] if idx < len(prices) else None
                if price is None:
                    continue
                for start, end in ranges:
                    band = RawPriceBand(
                        formule=row.formule_hint if row.formule_hint in {"PC", "DP"} else "PC",
                        source_page="llm_fallback",
                        date_label=row.period_text,
                        date_start=start,
                        date_end=end,
                        scraped_price=price,
                        is_available=True,
                        unit_type=label,  # scraped Adultes / child age-band header
                        nb_adults=1 if role == "adults" else None,
                        derivation=DERIVATION_SCRAPED,
                    )
                    bands.append(band)
                    if band.formule == "DP":
                        direct_dp_bands.append(band)
                    else:
                        pc_bands.append(band)

    # Only derive DP for PC date bands that don't already have a directly
    # scraped DP band. direct_dp_bands used to gate this per-page, which
    # meant one scraped DP band anywhere silently disabled derivation for
    # every other PC period on the page.
    direct_dp_keys = {(b.date_start, b.date_end) for b in direct_dp_bands}
    pc_needing_dp = [
        b for b in pc_bands if (b.date_start, b.date_end) not in direct_dp_keys
    ]
    if pc_needing_dp:
        # Derive DP from PC using footnote remise (or default 15%)
        stated = footnotes.dp_remise is not None
        remise = footnotes.dp_remise if stated else DEFAULT_DP_REMISE
        dp_bands = _derive_dp_bands(
            pc_needing_dp,
            remise,
            derivation="derived_stated" if stated else "derived_assumed",
        )
        bands.extend(dp_bands)

    return bands


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_grille_with_llm(
    html: str,
    village_id: str,
) -> list[RawPriceBand]:
    """Parse a VTF grille page using the LLM fallback pipeline.

    Returns a list of RawPriceBand (same shape as scraper.py produces).
    Called only when HTTP + Playwright both failed.

    Pipeline:
      1. Chunk HTML into row payloads (colspan expansion, Gratuit→0)
      2. Extract DP remise only (no supplements/discounts)
      3. For each row, call LLM to copy adult (PC) or unit (LOC) prices
      4. Map to RawPriceBand (PC + derived DP + LOC) — same fields as scraper
    """
    if not llm_fallback_enabled():
        logger.debug("LLM fallback disabled (LLM_FALLBACK_ENABLED=false)")
        return []

    if not html:
        logger.warning("parse_grille_with_llm: empty html for village=%s", village_id)
        return []

    # Step 1: Chunk HTML into rows
    rows = chunk_grille_html(html)
    if not rows:
        logger.info("parse_grille_with_llm: village=%s no rows extracted from HTML", village_id)
        return []

    logger.info("parse_grille_with_llm: village=%s chunked %d rows", village_id, len(rows))

    # Step 2: Extract footnotes
    footnotes = extract_footnotes(html)

    # Step 3: Extract prices for each row
    all_prices: list[list[Optional[Decimal]]] = []
    succeeded = 0
    for row in rows:
        prices = extract_row_prices(row)
        all_prices.append(prices)
        if any(p is not None for p in prices):
            succeeded += 1

    # Step 4: Map to RawPriceBand
    bands = llm_bands_to_raw_price_bands(rows, all_prices, footnotes)

    priced = [b for b in bands if b.is_available and b.scraped_price is not None]
    logger.info(
        "parse_grille_with_llm: village=%s rows=%d succeeded=%d bands=%d priced=%d",
        village_id, len(rows), succeeded, len(bands), len(priced),
    )

    return bands
