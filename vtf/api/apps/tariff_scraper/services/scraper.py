"""Low-level VTF page scraper.

Primary source of truth: the "Grille tarifaire" table embedded in each
village page HTML (inside a hidden ``nq-c-Popin`` modal). HTTP fetch +
HTML table parse is the fast path — Playwright ``inner_text()`` returns
empty on ``display:none`` popins, which previously yielded 0 bands.

Playwright is reserved for:
  • a secondary grille pass if HTTP fetch fails or finds no prices
  • opening the booking widget only when no grille prices are available

Design rules:
  • PC       → adult weekly rate from grille (or widget_total / nb_adults)
  • DP       → adult weekly rate from grille when present; otherwise derived
               from PC when the page advertises ½-pension remise, else widget
  • LOC      → flat weekly unit rate per column of the location grille
  • INDISPONIBLE widget windows → is_available=False
  • Struck-through price next to a promo → use the struck-through (regular) price
"""
from __future__ import annotations

import html as html_lib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

logger = logging.getLogger("scraper")  


def _today() -> date:
    """Clock helper — patchable in tests (freezegun not required)."""
    return date.today()

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ---------------------------------------------------------------------------
# Scraping pipeline steps — used for structured error messages
# Each step has a label and a source location for Discord alerts
# ---------------------------------------------------------------------------
STEP_1_HTTP_FETCH      = "Step 1 (HTTP Fetch)"
STEP_1_SRC             = "scraper.py → scrape_price_grid_http()"

STEP_2_HTML_GRID_PARSE = "Step 2 (HTML Grid Parse)"
STEP_2_SRC             = "scraper.py → scrape_price_grid_http()"

STEP_3_PLAYWRIGHT_INIT = "Step 3 (Browser Launch)"
STEP_3_SRC             = "scraper.py → scrape_village()"

STEP_4_PW_GRID_PARSE   = "Step 4 (Playwright Grid Parse)"
STEP_4_SRC             = "scraper.py → scrape_price_grid()"

STEP_5_WIDGET_SCRAPE   = "Step 5 (Widget Scrape)"
STEP_5_SRC             = "scraper.py → scrape_booking_widget()"

STEP_6_LLM_FALLBACK    = "Step 6 (LLM Fallback)"
STEP_6_SRC             = "llm_fallback.py → parse_grille_with_llm()"

STEP_7_VALIDATION      = "Step 7 (Validation)"
STEP_7_SRC             = "scraper.py → scrape_village()"

# Adults count used when reading the widget to derive per-adult weekly price
DEFAULT_NB_ADULTS = 2

# Polite delay between widget page navigations (seconds)
INTER_PAGE_DELAY = 1.5

# Maximum date windows to page through in the booking widget (safety cap)
MAX_WIDGET_PAGES = 52

# Default DP discount vs PC when the page advertises ½-pension (Lacanau: 15%)
DEFAULT_DP_REMISE = Decimal("0.15")


# ---------------------------------------------------------------------------
# Expected markers on a healthy VTF village page
# ---------------------------------------------------------------------------

EXPECTED_GRILLE_MARKERS = [
    "grille tarifaire",
    "pension complète",
    "pension complete",
    "demi-pension",
    "location",
    "séjour semaine",
    "sejour semaine",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FormatChangeInfo:
    """Diagnostics about page format changes detected during a scrape."""
    change_detected: bool = False
    expected_markers: list[str] = field(default_factory=list)
    found_markers: list[str] = field(default_factory=list)
    missing_markers: list[str] = field(default_factory=list)
    html_length: int = 0
    table_count: int = 0
    bands_scraped: int = 0
    priced_bands: int = 0
    change_type: str = ""  # marker_missing | zero_prices | parse_failure | hard_failure


# Derivation markers for RawPriceBand (PS-05)
DERIVATION_SCRAPED = "scraped"
DERIVATION_STATED = "derived_stated"    # DP from an explicit % remise on the page
DERIVATION_ASSUMED = "derived_assumed"  # DP from DEFAULT_DP_REMISE ("possible on request")


@dataclass
class RawPriceBand:
    """One date band as read off the page."""
    formule: str                     # PC | DP | LOC
    source_page: str                 # widget | price_grid
    date_label: str
    date_start: Optional[date]
    date_end: Optional[date]
    scraped_price: Optional[Decimal]
    is_available: bool = True
    unit_type: str = ""              # scraped header label (LOC units or PC/DP Adultes)
    nb_adults: Optional[int] = None  # widget only (PC/DP)
    derivation: str = DERIVATION_SCRAPED  # scraped | derived_stated | derived_assumed
    raw_cell_text: str = ""          # exact table-cell text as scraped, e.g. "Gratuit*",
                                      # "581 €", or "" for a blank cell — audit only,
                                      # scraped_price is still what pricing/calculations use
    scrape_source: str = ""          # "summer" | "winter" — which product URL season this
                                      # band came from (dual-season villages only; "" elsewhere,
                                      # persisted as "summer" default). Not to be confused with
                                      # `source_page`, which is the scrape TIER (grid/widget/llm).


@dataclass
class VillageScrapeResult:
    village_id: str
    url: str
    bands: list[RawPriceBand] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    format_change: Optional[FormatChangeInfo] = None
    dp_verification: object | None = None
    parse_notes: list[str] = field(default_factory=list)


@dataclass
class DpRemiseInfo:
    """½-pension remise extracted from page footnotes."""
    remise: Decimal
    derivation: str  # DERIVATION_STATED | DERIVATION_ASSUMED


# ---------------------------------------------------------------------------
# Pure-Python helpers (no HTML parser needed)
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?"
    r"\s*[–\-à]\s*"
    r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?"
)

# Single VTF period fragment: "11/04 au 2/05/26" or "4 au 11/07/26"
_VTF_RANGE_FULL = re.compile(
    r"(?P<d1>\d{1,2})/(?P<m1>\d{1,2})(?:/(?P<y1>\d{2,4}))?"
    r"\s*au\s*"
    r"(?P<d2>\d{1,2})/(?P<m2>\d{1,2})(?:/(?P<y2>\d{2,4}))?",
    re.IGNORECASE,
)
_VTF_RANGE_DAY_ONLY_START = re.compile(
    r"(?P<d1>\d{1,2})\s*au\s*"
    r"(?P<d2>\d{1,2})/(?P<m2>\d{1,2})(?:/(?P<y2>\d{2,4}))?",
    re.IGNORECASE,
)

# Maps French/English formule labels (lowercased) to our codes
FORMULE_LABEL_MAP = {
    "pension complète": "PC",
    "pension complete": "PC",
    "full board": "PC",
    "demi-pension": "DP",
    "demi pension": "DP",
    "half board": "DP",
}


_CURRENCY_PRICE_RE = re.compile(
    r"(?P<num>\d{1,3}(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?|\d+[.,]\d+|\d+)"
    r"\s*(?:€|&euro;|euros?\b)",
    re.IGNORECASE,
)
_CURRENCY_PREFIX_RE = re.compile(
    r"(?:€|&euro;|euros?)\s*"
    r"(?P<num>\d{1,3}(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?|\d+[.,]\d+|\d+)",
    re.IGNORECASE,
)
_PURE_NUMBER_RE = re.compile(
    r"^\s*(?P<num>\d{1,3}(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?|\d+[.,]\d+|\d+)\s*$"
)
_NOT_OFFERED_RE = re.compile(
    r"^[\s—–\-−/.]*$|^(?:n/?a|nd|indisponible|non\s+propos[ée])\.?$",
    re.IGNORECASE,
)


def _normalize_price_token(num: str) -> Optional[Decimal]:
    cleaned = (
        num.replace("\xa0", "")
        .replace("\u202f", "")
        .replace(" ", "")
        .replace(",", ".")
    )
    try:
        val = Decimal(cleaned)
    except Exception:
        return None
    if val < 0:
        return None
    return val  # 0 € is a valid price (PS-08)


def _parse_price(text: str) -> Optional[Decimal]:
    """Extract a decimal price from a raw text string.

    Handles French formatting: '1 234,00 €', '1234.00', '1 234 €', '469 &euro;',
    '0 €', 'Gratuit'. Rejects unit/occupancy strings like '6 pers.' (PS-07).
    """
    if not text:
        return None
    raw = html_lib.unescape(text)
    if re.search(r"\bgratuit\b", raw, re.IGNORECASE):
        return Decimal("0")

    # Prefer a number anchored to a currency marker (avoids "Studio 4 pers. 469 €" → 4)
    for pattern in (_CURRENCY_PRICE_RE, _CURRENCY_PREFIX_RE):
        m = pattern.search(raw)
        if m:
            return _normalize_price_token(m.group("num"))

    # Bare numeric cell only — whole string must be the number (no "pers.", "nuits", …)
    m = _PURE_NUMBER_RE.match(raw.replace("\xa0", " ").replace("\u202f", " "))
    if m:
        return _normalize_price_token(m.group("num"))
    return None


def _is_not_offered_cell(text: str) -> bool:
    """True for em-dash / blank cells meaning the formule is not offered (PS-04)."""
    if text is None:
        return True
    return bool(_NOT_OFFERED_RE.match(html_lib.unescape(text).strip()))


def _is_priced(band: RawPriceBand) -> bool:
    """Available band with a parsed price, including genuine 0 € (PS-08)."""
    return bool(band.is_available and band.scraped_price is not None)


def _right_align_headers(headers: list[str], n_prices: int) -> list[str]:
    """Align header labels to the trailing price columns (PS-02)."""
    if n_prices <= 0:
        return []
    if len(headers) >= n_prices:
        return headers[-n_prices:]
    return [""] * (n_prices - len(headers)) + list(headers)


def _align_pension_price_cells(headers: list[str], price_cells: list[str]) -> list[str]:
    """Restore omitted blank child cells before mapping PC/DP prices to headers."""
    if len(price_cells) >= len(headers):
        return price_cells

    deficit = len(headers) - len(price_cells)
    blanks = [""] * deficit
    if (
        price_cells
        and re.search(r"\bgratuit\b", html_lib.unescape(price_cells[-1]), re.IGNORECASE)
        and headers
        and _is_child_column_header(headers[-1])
    ):
        return price_cells[:-1] + blanks + [price_cells[-1]]
    return price_cells + blanks


def _headers_misaligned(raw_headers: list[str], n_prices: int) -> bool:
    """Detect header/price column count mismatch (PS-02)."""
    if n_prices <= 0:
        return False
    if len(raw_headers) < n_prices:
        return True
    aligned = _right_align_headers(raw_headers, n_prices)
    # Period / season labels sitting in the price-header window → drift
    for h in aligned:
        lowered = h.lower().strip()
        if not lowered:
            continue
        if "période" in lowered or "periode" in lowered:
            return True
        if lowered in {"basse", "haute", "été", "ete", "pâques", "paques"}:
            return True
    return False


def _normalize_year(raw: Optional[str], fallback_year: int) -> int:
    """Accept 2-digit ('25' → 2025) or 4-digit ('2025') year fragments."""
    if not raw:
        return fallback_year
    year = int(raw)
    if year < 100:
        return 2000 + year
    return year


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_date_range(text: str) -> tuple[Optional[date], Optional[date]]:
    """Parse a simple French date-range string into (start, end).

    Examples: '28/06 – 05/07', '28/06/25 – 05/07/25', '28/06/2025–05/07/2025'
    Prefer ``parse_vtf_period_cell`` for grille cells that may list several
    comma-separated ranges.
    """
    ranges = parse_vtf_period_cell(text)
    if ranges:
        return ranges[0]
    m = _DATE_RE.search(text)
    if not m:
        return None, None

    d1, m1, y1_raw = int(m.group(1)), int(m.group(2)), m.group(3)
    d2, m2, y2_raw = int(m.group(4)), int(m.group(5)), m.group(6)

    this_year = _today().year
    year_was_omitted = not y1_raw and not y2_raw
    y2 = _normalize_year(y2_raw, this_year)
    # PS-01: when start month is after end month and start year omitted, start is prior year
    if y1_raw:
        y1 = _normalize_year(y1_raw, this_year)
    elif m1 > m2:
        y1 = y2 - 1
    else:
        y1 = y2

    start = _safe_date(y1, m1, d1)
    end = _safe_date(y2, m2, d2)
    if not start or not end:
        return None, None
    if end < start:
        # Cross-year: pull start back (do not push end forward)
        start = _safe_date(end.year - 1, start.month, start.day) or start
    if year_was_omitted and end < _today():
        start = _safe_date(start.year + 1, start.month, start.day) or start
        end = _safe_date(end.year + 1, end.month, end.day) or end
    return start, end


def parse_vtf_period_cell(text: str) -> list[tuple[date, date]]:
    """Parse a VTF grille period cell into one or more (start, end) dates.

    Handles real website formats, e.g.:
      '11/04 au 2/05/26'
      '2/05 au 4/07, 29/08 au 3/10/26'
      '4 au 11/07, 22 au 29/08/26'
      '25/07 au 15/08/26'
      '27/12 au 3/01/26'  → crosses year boundary (PS-01)
    """
    if not text:
        return []

    this_year = _today().year
    # F-01: year hint must be a full d/m/y fragment — not a trailing month like /05
    year_hint_m = re.search(r"\d{1,2}/\d{1,2}/(\d{2,4})\s*$", text.strip())
    default_year = _normalize_year(year_hint_m.group(1) if year_hint_m else None, this_year)
    cell_has_year = year_hint_m is not None or bool(
        re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", text)
    )

    results: list[tuple[date, date]] = []
    # Split on commas that separate multiple ranges (not decimal commas)
    parts = re.split(r"\s*,\s*", text.strip())

    for part in parts:
        part = part.strip()
        if not part:
            continue

        start = end = None
        part_has_year = bool(re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", part))
        m = _VTF_RANGE_FULL.search(part)
        if m:
            y2 = _normalize_year(m.group("y2"), default_year)
            m1, m2 = int(m.group("m1")), int(m.group("m2"))
            if m.group("y1"):
                y1 = _normalize_year(m.group("y1"), default_year)
            elif m1 > m2:
                # PS-01: Dec→Jan style — start year is the year before end year
                y1 = y2 - 1
            else:
                y1 = y2
            start = _safe_date(y1, m1, int(m.group("d1")))
            end = _safe_date(y2, m2, int(m.group("d2")))
        else:
            m2 = _VTF_RANGE_DAY_ONLY_START.search(part)
            if m2:
                y2 = _normalize_year(m2.group("y2"), default_year)
                month = int(m2.group("m2"))
                start = _safe_date(y2, month, int(m2.group("d1")))
                end = _safe_date(y2, month, int(m2.group("d2")))

        if not start or not end:
            continue
        if end < start:
            # Safety net: pull start back one year (never push end forward)
            start = _safe_date(end.year - 1, start.month, start.day) or start
        # F-02: year-less band already in the past → roll forward one year
        if not part_has_year and not cell_has_year and end < _today():
            start = _safe_date(start.year + 1, start.month, start.day) or start
            end = _safe_date(end.year + 1, end.month, end.day) or end
        results.append((start, end))

    return results


def _match_formule(label_text: str) -> Optional[str]:
    """Return 'PC' or 'DP' if the label matches a known formule, else None."""
    lowered = label_text.lower().strip()
    for key, code in FORMULE_LABEL_MAP.items():
        if key in lowered:
            return code
    return None


def _detect_grid_formule(header_text: str) -> Optional[str]:
    """Detect PC / DP / LOC from a grille tarifaire header row."""
    lowered = header_text.lower()
    if "location" in lowered:
        return "LOC"
    if "demi-pension" in lowered or "demi pension" in lowered:
        return "DP"
    if "pension" in lowered:
        return "PC"
    return None


def _is_adult_column_header(header: str) -> bool:
    """True for the Adults / Adultes price column (not age-group columns)."""
    lowered = header.lower().strip()
    # French "Adultes" / English "Adults" — avoid matching age labels.
    return "adulte" in lowered or lowered == "adults" or lowered.startswith("adult")


def _is_child_column_header(header: str) -> bool:
    """True for age-range child price columns (e.g. '2-5 ans', '6-11 ans').

    Typical VTF formats:
      - "11 à - 16 ans"  → 11 to under 16
      - "6 à - 11 ans"   → 6 to under 11
      - "4 à - 6 ans"    → 4 to under 6
      - "1 à - 4 ans"    → 1 to under 4
      - "- 3 ans"         → under 3 (Talloires-style column)
      - "2-5 ans", "12-17 ans", etc.

    Note: Generic labels like "Enfants" or "Children" without age ranges are
    NOT matched — they are too vague to map to a specific age band.
    """
    lowered = header.lower().strip()
    # Match age-range patterns: "2-5 ans", "11 à - 16 ans", "6 a 11 ans"
    if re.search(r"\d+\s*[–\-àa]\s*-?\s*\d+\s*ans?\b", lowered):
        return True
    # Match explicit under-age headers: "- 3 ans", "< 3 ans", "moins de 3 ans".
    if re.search(r"^(?:[<≤]\s*|-+\s*|moins\s+de\s+)\d+\s*ans?\b", lowered):
        return True
    # Note: Generic "enfant/child" labels without age ranges are intentionally
    # excluded — they are too vague to map to a specific pricing band.
    return False


def _extract_dp_remise_info(page_text: str) -> Optional[DpRemiseInfo]:
    """Return DP remise + derivation kind if the page advertises ½-pension off PC."""
    m = re.search(
        r"(?:1/2|½|demi)[-\s]?pension[^=]{0,40}?=\s*(\d+)\s*%\s*(?:de\s+)?remise",
        page_text,
        re.IGNORECASE,
    )
    if m:
        remise = (Decimal(m.group(1)) / Decimal(100)).quantize(Decimal("0.01"))
        return DpRemiseInfo(remise=remise, derivation=DERIVATION_STATED)
    if re.search(r"(?:1/2|½|demi)[-\s]?pension\s+possible", page_text, re.IGNORECASE):
        return DpRemiseInfo(remise=DEFAULT_DP_REMISE, derivation=DERIVATION_ASSUMED)
    return None


def _extract_dp_remise(page_text: str) -> Optional[Decimal]:
    """Return DP remise fraction if the page advertises ½-pension off PC."""
    info = _extract_dp_remise_info(page_text)
    return info.remise if info else None


def parse_grille_table(
    rows: list[list[str]],
    *,
    page_text: str = "",
    notes: Optional[list[str]] = None,
    derive_dp: bool = True,
) -> list[RawPriceBand]:
    """Parse a grille tarifaire matrix (list of cell-text rows) into bands.

    PC/DP grids: prices from all recognized columns (Adultes + child age bands);
    unit_type is the scraped column header text (e.g. "Adultes", "6 à - 11 ans").
    Child columns are detected via _is_child_column_header(). DP is derived from
    PC only when no direct DP grid was scraped and a remise footnote is present
    (unit_type copied from the PC band). LOC grids: one band per unit-type
    column. Multi-range period cells expand into one band per (start, end) pair.
    """
    bands: list[RawPriceBand] = []
    parse_notes = notes if notes is not None else []
    if not rows:
        return bands

    formule: Optional[str] = None
    unit_headers: list[str] = []
    pension_headers: list[str] = []
    pension_unit_type = ""  # scraped Adultes header, or Adultes when fallback is selected
    header_idx = -1
    misalignment_noted = False

    for idx, cells in enumerate(rows):
        joined = " ".join(cells).lower()
        detected = _detect_grid_formule(joined)
        if detected:
            formule = detected
            header_idx = idx
            # Keep empty spacer cells so indices stay aligned with data rows (PS-02).
            # Price columns are right-aligned against these headers per data row.
            if formule == "LOC":
                unit_headers = [c.strip() for c in cells[1:]]
            elif formule in {"PC", "DP"}:
                pension_headers = [c.strip() for c in cells[1:]]
            break

    if not formule:
        return bands

    for cells in rows[header_idx + 1:]:
        if len(cells) < 2:
            continue
        joined = " ".join(cells).lower()
        # Skip repeated header / legend rows (not price rows)
        if any(kw in joined for kw in ["séjour semaine", "adultes", "logement"]):
            continue

        # period is usually column 1; some continuation rows put dates in col 0
        period_text = ""
        price_cells: list[str] = []
        if len(cells) > 1 and parse_vtf_period_cell(cells[1]):
            period_text = cells[1]
            price_cells = cells[2:]
        elif parse_vtf_period_cell(cells[0]):
            period_text = cells[0]
            price_cells = cells[1:]
        else:
            continue

        ranges = parse_vtf_period_cell(period_text)
        if not ranges:
            continue

        if formule in {"PC", "DP"}:
            raw_headers = pension_headers
            if _headers_misaligned(raw_headers, len(price_cells)):
                if not misalignment_noted:
                    parse_notes.append(
                        f"header_misalignment: {formule} header columns do not align with price cells"
                    )
                    misalignment_noted = True

            # Some VTF header rows carry a literal "Période"/"Periode" label
            # cell even though period/date data is already parsed out of a
            # separate column (period_text above) — that header cell has no
            # corresponding price cell at all. Drop it before aligning
            # headers to price cells, otherwise every column after it reads
            # one price cell off from its real label.
            data_headers = [
                h for h in raw_headers
                if "période" not in h.lower() and "periode" not in h.lower()
            ]

            original_price_cell_count = len(price_cells)
            data_headers = [h for h in data_headers if h.strip()]
            if len(price_cells) > len(data_headers):
                surplus = len(price_cells) - len(data_headers)
                leading = price_cells[:surplus]
                if all(_parse_price(cell) is None for cell in leading):
                    price_cells = price_cells[surplus:]
                    original_price_cell_count = len(price_cells)
            # Colspan expansion already respects align (center → Gratuit* on
            # every covered column; right → blank then Gratuit*). Restore
            # omitted trailing blanks when HTML skipped an empty child cell.
            price_cells = _align_pension_price_cells(data_headers, price_cells)

            # Collect all recognized columns: adults + child age bands
            # First pass: identify which headers are recognized price columns
            target_cols: list[tuple[int, str, str]] = []  # (col_i, label, role)
            recognized_indices: list[int] = []  # indices of recognized headers
            for col_i, header in enumerate(data_headers):
                if _is_adult_column_header(header):
                    recognized_indices.append(col_i)
                elif _is_child_column_header(header):
                    recognized_indices.append(col_i)

            if recognized_indices:
                # Map recognized headers to price cells by the header's own
                # column index (within data_headers, which is now aligned
                # 1:1 with price_cells from the left) — NOT by position
                # within recognized_indices. Using enumerate() position
                # there desynchronises label and price as soon as an
                # unrecognized column (e.g. a generic "Enfants" header,
                # which _is_child_column_header rejects on purpose) sits
                # between two recognized ones.
                for col_i in recognized_indices:
                    if col_i >= len(price_cells):
                        continue
                    header = data_headers[col_i]
                    role = "adults" if _is_adult_column_header(header) else "child"
                    target_cols.append((col_i, header.strip(), role))
            else:
                # Fallback: use col 0 as adult column
                fallback_label = raw_headers[0].strip() if raw_headers else "Adultes"
                target_cols = [(0, fallback_label, "adults")]
                if raw_headers and not misalignment_noted:
                    parse_notes.append(
                        "header_misalignment: no Adultes column after right-align"
                    )
                    misalignment_noted = True

            # Extract prices from all recognized columns
            row_free_marker = next(
                (
                    cell.strip()
                    for cell in price_cells
                    if re.search(r"\bgratuit\b", html_lib.unescape(cell), re.IGNORECASE)
                ),
                "",
            )
            for col_i, col_label, col_role in target_cols:
                cell = price_cells[col_i] if col_i < len(price_cells) else ""
                raw_cell_text = cell.strip() if cell else ""
                if (
                    col_role == "child"
                    and col_i >= original_price_cell_count
                    and not row_free_marker
                ):
                    continue

                # Blank / dash / n-a cells in an Adultes column mean the
                # formule isn't offered for this period — skip. For a child
                # age-band column, a blank cell is just another way of
                # saying "free at this age" (the site leaves it empty
                # instead of literally printing "Gratuit"), so store 0
                # instead of dropping the band. "Gratuit"/"Gratuit*" cells
                # already come out as Decimal("0") from _parse_price() below,
                # so both spellings of "free" end up stored the same way.
                if _is_not_offered_cell(cell):
                    if col_role == "child":
                        price = Decimal("0")
                    else:
                        parse_notes.append(
                            f"not_offered: {formule} {col_label} cell empty/dash for period '{period_text.strip()}'"
                        )
                        continue
                else:
                    price = _parse_price(cell)
                    if price is None:
                        parse_notes.append(
                            f"parse_failed: could not parse {formule} {col_label} price '{cell}' for '{period_text.strip()}'"
                        )
                        continue

                for start, end in ranges:
                    bands.append(RawPriceBand(
                        formule=formule,
                        source_page="price_grid",
                        date_label=period_text.strip(),
                        date_start=start,
                        date_end=end,
                        scraped_price=price,
                        is_available=True,
                        unit_type=col_label,
                        nb_adults=1 if col_role == "adults" else None,
                        derivation=DERIVATION_SCRAPED,
                        raw_cell_text=raw_cell_text,
                    ))
        else:
            # LOC — one price per unit column (right-aligned with header unit labels)
            if _headers_misaligned(unit_headers, len(price_cells)):
                if not misalignment_noted:
                    parse_notes.append(
                        "header_misalignment: LOC header columns do not align with price cells"
                    )
                    misalignment_noted = True
            aligned_units = _right_align_headers(unit_headers, len(price_cells))
            for col_i, cell in enumerate(price_cells):
                if _is_not_offered_cell(cell):
                    parse_notes.append(
                        f"not_offered: LOC cell for "
                        f"'{aligned_units[col_i] if col_i < len(aligned_units) else col_i}' "
                        f"period '{period_text.strip()}'"
                    )
                    continue
                price = _parse_price(cell)
                if price is None:
                    parse_notes.append(
                        f"parse_failed: LOC price '{cell}' for period '{period_text.strip()}'"
                    )
                    continue
                unit_type = (
                    aligned_units[col_i]
                    if col_i < len(aligned_units) and aligned_units[col_i]
                    else f"unit_{col_i}"
                )
                for start, end in ranges:
                    bands.append(RawPriceBand(
                        formule="LOC",
                        source_page="price_grid",
                        date_label=period_text.strip(),
                        date_start=start,
                        date_end=end,
                        scraped_price=price,
                        is_available=True,
                        unit_type=unit_type,
                        derivation=DERIVATION_SCRAPED,
                        raw_cell_text=cell.strip() if cell else "",
                    ))

    if derive_dp:
        bands.extend(_derive_dp_bands_from_pc(bands, page_text))

    return bands


def _derive_dp_bands_from_pc(
    bands: list[RawPriceBand],
    page_text: str,
) -> list[RawPriceBand]:
    """Derive DP bands from PC only when no direct DP grid prices were scraped."""
    if any(b.formule == "DP" and _is_priced(b) for b in bands):
        return []

    remise_info = _extract_dp_remise_info(page_text)
    if remise_info is None:
        return []

    derived: list[RawPriceBand] = []
    factor = (Decimal("1") - remise_info.remise).quantize(Decimal("0.01"))
    for band in list(bands):
        if band.formule != "PC" or band.scraped_price is None:
            continue
        # VTF's grille always quotes PC as a fixed weekly rate
        # ("Prix pour 8 jours et 7 nuits"). The real site applies the
        # ½-pension remise to the NIGHTLY rate and rounds there before
        # re-multiplying by 7 — not to the weekly total. Match that
        # exactly (confirmed against live booking-widget prices).
        pc_nightly = band.scraped_price / Decimal(7)
        dp_nightly = (pc_nightly * factor).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        dp_price = dp_nightly * Decimal(7)
        derived.append(RawPriceBand(
            formule="DP",
            source_page="price_grid",
            date_label=band.date_label,
            date_start=band.date_start,
            date_end=band.date_end,
            scraped_price=dp_price,
            is_available=True,
            unit_type=band.unit_type,  # same scraped Adultes header as PC
            nb_adults=1,
            derivation=remise_info.derivation,
            raw_cell_text="-",
        ))
    return derived


# ---------------------------------------------------------------------------
# Booking widget scraper — PC / DP (secondary)
# ---------------------------------------------------------------------------

def scrape_booking_widget(village_id: str, url: str, page) -> list[RawPriceBand]:
    """Scrape PC/DP from the on-page booking widget when available.

    Tries the village page itself first (widget lives there on vtf-vacances),
    then ``{url}/reservation`` as a legacy fallback.
    """
    from playwright.sync_api import TimeoutError as PWTimeout

    bands: list[RawPriceBand] = []
    candidates = [url.rstrip("/"), url.rstrip("/") + "/reservation"]

    # Keep selectors tight — `[class*='booking']` matches marketing chrome and
    # previously caused a 50-page empty pagination walk (~90s) with 0 bands.
    _WIDGET_READY = (
        ".booking-widget__date, .week-label, "
        "[class*='booking-widget'], [class*='formule-row'], "
        "text=/Votre réservation/i"
    )

    loaded = False
    for widget_url in candidates:
        try:
            page.goto(widget_url, wait_until="networkidle", timeout=30_000)
            if page.query_selector(_WIDGET_READY):
                loaded = True
                break
        except Exception as exc:
            logger.warning("scrape_booking_widget: could not load %s — %s", widget_url, exc)

    if not loaded:
        logger.info(
            "scrape_booking_widget: village=%s bands_found=0 (widget not found)",
            village_id,
        )
        return bands

    seen_labels: set[str] = set()
    empty_streak = 0

    for _ in range(MAX_WIDGET_PAGES):
        time.sleep(INTER_PAGE_DELAY)

        new_bands = _read_widget_state(page, village_id)
        new_labels = {b.date_label for b in new_bands if b.date_label}

        if not new_labels:
            empty_streak += 1
            if empty_streak >= 2:
                break
        else:
            empty_streak = 0

        if new_labels and new_labels.issubset(seen_labels):
            break

        for band in new_bands:
            if band.date_label and band.date_label not in seen_labels:
                bands.append(band)

        seen_labels.update(new_labels)

        next_btn = page.query_selector(
            "button[aria-label*='suivant'], "
            "button[aria-label*='next'], "
            ".booking-widget__next, "
            "[data-direction='next']"
        )
        if not next_btn or not next_btn.is_enabled():
            break
        try:
            next_btn.click()
            page.wait_for_load_state("networkidle", timeout=10_000)
        except PWTimeout:
            break

    logger.info(
        "scrape_booking_widget: village=%s bands_found=%d",
        village_id, len(bands),
    )
    return bands


def _read_nb_adults_from_widget(page) -> int:
    """Read occupancy from the booking widget; fall back to DEFAULT_NB_ADULTS (PS-09)."""
    selectors = [
        "select[name*='adult' i]",
        "select[id*='adult' i]",
        "input[name*='adult' i]",
        "input[id*='adult' i]",
        "[class*='adult'] select",
        "[class*='occupancy'] select",
        "[data-adults]",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
        except Exception:
            el = None
        if not el:
            continue
        try:
            attr = el.get_attribute("data-adults") or el.get_attribute("value")
            if attr and attr.strip().isdigit():
                n = int(attr.strip())
                if 1 <= n <= 20:
                    return n
        except Exception:
            pass
        try:
            if hasattr(el, "input_value"):
                val = (el.input_value() or "").strip()
                if val.isdigit():
                    n = int(val)
                    if 1 <= n <= 20:
                        return n
        except Exception:
            pass
        try:
            txt = (el.inner_text() or "").strip()
            m = re.search(r"(\d+)", txt)
            if m:
                n = int(m.group(1))
                if 1 <= n <= 20:
                    return n
        except Exception:
            pass

    try:
        body = page.inner_text("body") or ""
    except Exception:
        body = ""
    m = re.search(r"(\d+)\s*adultes?", body, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 20:
            return n
    return DEFAULT_NB_ADULTS


def _read_widget_state(page, village_id: str) -> list[RawPriceBand]:
    """Read PC / DP price rows from the current visible state of the widget."""
    bands: list[RawPriceBand] = []
    nb_adults = _read_nb_adults_from_widget(page)

    date_label = ""
    date_start: Optional[date] = None
    date_end: Optional[date] = None

    header_el = page.query_selector(
        ".booking-widget__date, "
        ".week-label, "
        "[class*='semaine'], "
        "[class*='week-header'], "
        "[class*='date-range']"
    )
    if header_el:
        date_label = header_el.inner_text().strip()
        date_start, date_end = _parse_date_range(date_label)

    if not date_label:
        page_text = page.inner_text("body")
        m = _DATE_RE.search(page_text) or _VTF_RANGE_FULL.search(page_text)
        if m:
            date_label = m.group(0)
            date_start, date_end = _parse_date_range(date_label)

    rows = page.query_selector_all("tr, [class*='formule-row'], [class*='pension-row']")

    for row in rows:
        label_el = row.query_selector(
            "td:first-child, th:first-child, [class*='label'], [class*='name']"
        )
        if not label_el:
            continue

        formule = _match_formule(label_el.inner_text())
        if not formule:
            continue

        row_text = row.inner_text().lower()

        if "indisponible" in row_text or "unavailable" in row_text:
            if date_label:
                bands.append(RawPriceBand(
                    formule=formule,
                    source_page="widget",
                    date_label=date_label,
                    date_start=date_start,
                    date_end=date_end,
                    scraped_price=None,
                    is_available=False,
                    nb_adults=nb_adults,
                    derivation=DERIVATION_SCRAPED,
                ))
            continue

        regular_price: Optional[Decimal] = None

        struck = row.query_selector(
            "del, s, strike, [class*='original-price'], [class*='prix-barre']"
        )
        if struck:
            regular_price = _parse_price(struck.inner_text())

        if regular_price is None:
            price_cells = row.query_selector_all(
                "td:not(:first-child), "
                "[class*='price'], "
                "[class*='prix'], "
                "[class*='tarif']"
            )
            for cell in price_cells:
                regular_price = _parse_price(cell.inner_text())
                if regular_price is not None:
                    break

        if regular_price is None or not date_label:
            continue

        per_adult = (regular_price / Decimal(nb_adults)).quantize(Decimal("0.01"))

        bands.append(RawPriceBand(
            formule=formule,
            source_page="widget",
            date_label=date_label,
            date_start=date_start,
            date_end=date_end,
            scraped_price=per_adult,
            is_available=True,
            nb_adults=nb_adults,
            derivation=DERIVATION_SCRAPED,
        ))

    return bands


# ---------------------------------------------------------------------------
# Price grid scraper — PC / LOC (primary)
# ---------------------------------------------------------------------------

def _cell_text_from_html(raw: str) -> str:
    """Strip tags / entities from a ``<td>``/``<th>`` inner HTML fragment."""
    text = re.sub(r"<br\s*/?>", " ", raw, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _prefer_regular_price_from_cell_html(cell_html: str) -> str:
    """Prefer struck-through / prix-barre regular price over promo (PS-03).

    ``cell_html`` must be the full ``<td>…</td>`` / ``<th>…</th>`` tag so
    cell-level classes like ``prix-barre`` are visible.
    """
    open_m = re.match(r"<t[hd]\b([^>]*)>", cell_html, re.I)
    attrs = open_m.group(1) if open_m else ""
    inner_m = re.search(r"<t[hd]\b[^>]*>([\s\S]*?)</t[hd]>", cell_html, re.I)
    inner = inner_m.group(1) if inner_m else cell_html

    if re.search(r"prix-barre|original-price|prix-original", attrs, re.I):
        return _cell_text_from_html(inner)

    struck = re.search(
        r"<(?:del|s|strike)\b[^>]*>([\s\S]*?)</(?:del|s|strike)>",
        cell_html,
        re.I,
    )
    if struck:
        return _cell_text_from_html(struck.group(1))

    barre_child = re.search(
        r"<[^>]+class=[\"'][^\"']*(?:prix-barre|original-price|prix-original)"
        r"[^\"']*[\"'][^>]*>([\s\S]*?)</",
        cell_html,
        re.I,
    )
    if barre_child:
        return _cell_text_from_html(barre_child.group(1))

    return _cell_text_from_html(inner)


def _cell_horizontal_align(attrs: str) -> str:
    """Return ``left`` / ``right`` / ``center`` / ```` from td/th attributes."""
    align_m = re.search(
        r"""\balign\s*=\s*['"]?(left|right|center|middle)\b""",
        attrs,
        re.I,
    )
    if align_m:
        value = align_m.group(1).lower()
        return "center" if value == "middle" else value
    style_m = re.search(
        r"""text-align\s*:\s*(left|right|center)\b""",
        attrs,
        re.I,
    )
    if style_m:
        return style_m.group(1).lower()
    return ""


_FREE_CHILD_MARKER_RE = re.compile(r"\bgratuit\b", re.I)


def _expand_colspan_text(text: str, colspan: int, attrs: str = "") -> list[str]:
    """Expand a colspan cell the way it appears across covered columns.

    Ordinary merged price cells keep the original, broadly-correct
    behavior: duplicate the text into every covered column, regardless of
    any ``align``/``text-align`` styling (which is usually just cosmetic
    right-alignment of numbers and does not mean the value belongs to a
    single column).

    The align-dependent placement below only applies to the specific
    merged free-child ``Gratuit*`` cell, where VTF grids genuinely use
    alignment to show which age column the free price belongs to:
    - ``align="center"`` (Agde/Biarritz): text is centered across both age
      columns → each covered column keeps the text.
    - ``align="right"`` (Lacanau): text sits in the rightmost column and the
      older age column looks blank → leading covered columns stay empty.
    - ``align="left"``: text sits in the leftmost column.
    Unspecified alignment on a ``Gratuit*`` cell duplicates the text
    (center-like), matching the common merged free-child presentation.
    """
    colspan = max(1, min(int(colspan), 20))
    if colspan == 1:
        return [text]
    if not _FREE_CHILD_MARKER_RE.search(text):
        return [text] * colspan
    align = _cell_horizontal_align(attrs)
    if align == "right":
        return [""] * (colspan - 1) + [text]
    if align == "left":
        return [text] + [""] * (colspan - 1)
    return [text] * colspan


def extract_tables_from_html(html: str) -> list[list[list[str]]]:
    """Return every HTML ``<table>`` as a list of row cell-text matrices."""
    tables: list[list[list[str]]] = []
    for m in re.finditer(r"<table\b[^>]*>([\s\S]*?)</table>", html, re.I):
        block = m.group(0)
        rows: list[list[str]] = []
        for tr in re.finditer(r"<tr\b[^>]*>([\s\S]*?)</tr>", block, re.I):
            cells: list[str] = []
            for c in re.finditer(r"<t[hd]\b([^>]*)>([\s\S]*?)</t[hd]>", tr.group(0), re.I):
                cell_html = c.group(0)
                attrs = c.group(1) or ""
                text = _prefer_regular_price_from_cell_html(cell_html)
                colspan_m = re.search(r"\bcolspan\s*=\s*['\"]?(\d+)", attrs, re.I)
                colspan = int(colspan_m.group(1)) if colspan_m else 1
                colspan = max(1, min(colspan, 20))

                if colspan == 1:
                    cells.append(text)
                    continue

                # Formula title cells commonly span the season+period columns.
                # Keep one title plus empty spacers so following price headers
                # stay in their real columns. Merged price cells expand by
                # horizontal alignment (center → duplicate text, right → blank
                # then text) so raw_cell_text matches what the site shows.
                if not cells and _detect_grid_formule(text):
                    cells.append(text)
                    cells.extend([""] * (colspan - 1))
                else:
                    cells.extend(_expand_colspan_text(text, colspan, attrs))
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def _split_grille_sections(rows: list[list[str]]) -> list[list[list[str]]]:
    """Split a table that contains several formule sections into parse units."""
    sections: list[list[list[str]]] = []
    current: list[list[str]] = []

    for cells in rows:
        joined = " ".join(cells).lower()
        if _detect_grid_formule(joined):
            if current:
                sections.append(current)
            current = [cells]
        elif current:
            current.append(cells)

    if current:
        sections.append(current)
    return sections or [rows]


def parse_bands_from_html(html: str, notes: Optional[list[str]] = None) -> list[RawPriceBand]:
    """Parse all grille tables from a village-page HTML document."""
    page_text = _cell_text_from_html(html)
    bands: list[RawPriceBand] = []
    parse_notes = notes if notes is not None else []
    for matrix in extract_tables_from_html(html):
        for section in _split_grille_sections(matrix):
            bands.extend(
                parse_grille_table(
                    section,
                    page_text=page_text,
                    notes=parse_notes,
                    derive_dp=False,
                )
            )
    bands.extend(_derive_dp_bands_from_pc(bands, page_text))
    if not bands:
        bands.extend(_parse_grille_from_plaintext(page_text, notes=parse_notes))
    return bands


def fetch_village_html(url: str, timeout: float = 40.0) -> str:
    """HTTP GET the village page HTML (grille lives in a hidden popin)."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util import Retry

    retry = Retry(
        total=2,
        connect=2,
        read=1,
        status=1,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        # urllib3 stores the default as a frozenset. Some runtime stacks around
        # requests expect a mutable set here, so pass our own copy explicitly.
        allowed_methods=set(Retry.DEFAULT_ALLOWED_METHODS),
    )
    adapter = HTTPAdapter(max_retries=retry)

    with requests.Session() as session:
        session.headers.update(HTTP_HEADERS)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        # Do not call resp.apparent_encoding here. In some environments,
        # requests delegates that to charset_normalizer, which can crash on
        # VTF pages with "set object expected; got frozenset".
        if not resp.encoding:
            resp.encoding = "utf-8"
        return resp.text


@dataclass
class HttpGridScrapeResult:
    """Outcome of the HTTP grille fetch (bands + diagnostics)."""
    bands: list[RawPriceBand] = field(default_factory=list)
    html_len: int = 0
    html: str = ""  # retained for LLM fallback only when scrape yields no prices
    fetch_error: Optional[str] = None
    has_grille_markers: bool = False
    format_change: Optional[FormatChangeInfo] = None
    parse_notes: list[str] = field(default_factory=list)


def scrape_price_grid_http(village_id: str, url: str) -> HttpGridScrapeResult:
    """Primary grille scrape: HTTP fetch + HTML table parse (no browser)."""
    out = HttpGridScrapeResult()
    grid_url = url.rstrip("/")
    try:
        html = fetch_village_html(grid_url)
    except Exception as exc:
        out.fetch_error = f"HTTP fetch failed for {grid_url}: {exc}"
        logger.warning("scrape_price_grid_http: could not fetch %s — %s", grid_url, exc)
        return out

    out.html = html
    out.html_len = len(html)
    lowered = html.lower()

    # ── Marker detection ──────────────────────────────────────────────────
    found = [m for m in EXPECTED_GRILLE_MARKERS if m in lowered]
    missing = [m for m in EXPECTED_GRILLE_MARKERS if m not in lowered]
    out.has_grille_markers = bool(found)

    # Count <table> elements for structural diagnostics
    table_count = len(re.findall(r"<table\b", html, re.I))

    out.bands = parse_bands_from_html(html, notes=out.parse_notes)

    # ── Build FormatChangeInfo when markers are missing ───────────────────
    out.format_change = FormatChangeInfo(
        expected_markers=list(EXPECTED_GRILLE_MARKERS),
        found_markers=found,
        missing_markers=missing,
        html_length=out.html_len,
        table_count=table_count,
        bands_scraped=len(out.bands),
        priced_bands=sum(1 for b in out.bands if _is_priced(b)),
    )

    # If page loaded but ALL markers are missing → likely format change or blocked
    if not found and out.html_len > 0:
        out.format_change.change_detected = True
        out.format_change.change_type = "marker_missing"
    elif any(n.startswith("header_misalignment") for n in out.parse_notes):
        out.format_change.change_detected = True
        out.format_change.change_type = "header_misalignment"

    logger.info(
        "scrape_price_grid_http: village=%s bands_found=%d html_len=%d "
        "grille_markers=%s found=%d missing=%d tables=%d",
        village_id, len(out.bands), out.html_len, out.has_grille_markers,
        len(found), len(missing), table_count,
    )
    return out


def _dismiss_cookie_banners(page) -> None:
    """Best-effort click through common cookie consent UIs."""
    selectors = [
        "#onetrust-accept-btn-handler",
        "button:has-text('Tout accepter')",
        "button:has-text('Accepter')",
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=2_000)
                page.wait_for_timeout(400)
                return
        except Exception:
            continue


def scrape_price_grid(village_id: str, url: str, page) -> list[RawPriceBand]:
    """Playwright grille scrape (fallback when HTTP parse finds nothing).

    Important: VTF embeds the grille in a ``display:none`` popin. Browser
    ``innerText`` is empty for hidden nodes — always read ``text_content``
    or parse ``page.content()`` HTML instead.
    """
    from playwright.sync_api import TimeoutError as PWTimeout

    bands: list[RawPriceBand] = []
    grid_url = url.rstrip("/")

    try:
        page.goto(grid_url, wait_until="domcontentloaded", timeout=45_000)
    except Exception as exc:
        logger.info("scrape_price_grid: could not load %s — %s", grid_url, exc)
        # Still try whatever HTML landed
        try:
            bands = parse_bands_from_html(page.content())
        except Exception:
            pass
        return bands

    try:
        page.wait_for_load_state("networkidle", timeout=12_000)
    except PWTimeout:
        pass

    _dismiss_cookie_banners(page)

    # Open the Grille tarifaire popin when possible (visibility not required to parse)
    for sel in (
        "text=Grille tarifaire",
        "a:has-text('Grille tarifaire')",
        "button:has-text('Grille tarifaire')",
        "a:has-text('Voir les tarifs')",
        "button:has-text('Voir les tarifs')",
        "a:has-text('Tarifs')",
    ):
        try:
            el = page.query_selector(sel)
            if el:
                el.click(timeout=2_000, force=True)
                page.wait_for_timeout(600)
                break
        except Exception:
            continue

    # Prefer raw HTML parse — works even if the popin stays hidden
    try:
        bands = parse_bands_from_html(page.content())
    except Exception as exc:
        logger.warning("scrape_price_grid: HTML parse failed — %s", exc)

    # Secondary: walk <table> nodes via text_content (not inner_text)
    if not bands:
        page_text = ""
        try:
            page_text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
        except Exception:
            pass
        for table in page.query_selector_all("table"):
            matrix: list[list[str]] = []
            for row in table.query_selector_all("tr"):
                cells = row.query_selector_all("th, td")
                matrix.append([(c.text_content() or "").strip() for c in cells])
            bands.extend(parse_grille_table(matrix, page_text=page_text))

    # Tertiary: Playwright DOM expansion for colspan/rowspan
    if not bands:
        try:
            expanded_tables = page.evaluate("""() => {
                const tables = document.querySelectorAll('table');
                const result = [];
                for (const table of tables) {
                    const rows = [];
                    for (const tr of table.querySelectorAll('tr')) {
                        const cells = [];
                        for (const cell of tr.querySelectorAll('th, td')) {
                            const text = (cell.textContent || '').trim();
                            const colspan = parseInt(cell.getAttribute('colspan') || '1', 10);
                            const rowspan = parseInt(cell.getAttribute('rowspan') || '1', 10);
                            let align = (cell.getAttribute('align') || '').toLowerCase();
                            if (align === 'middle') align = 'center';
                            if (!align) {
                                const styleAlign = ((cell.style && cell.style.textAlign) || '').toLowerCase();
                                if (styleAlign === 'left' || styleAlign === 'right' || styleAlign === 'center') {
                                    align = styleAlign;
                                }
                            }
                            // Only the merged free-child "Gratuit*" cell has
                            // alignment-dependent placement; ordinary merged
                            // price cells duplicate into every covered column
                            // regardless of (often cosmetic) align styling.
                            const isFreeChildCell = /\\bgratuit\\b/i.test(text);
                            for (let c = 0; c < colspan; c++) {
                                let cellText = text;
                                if (colspan > 1 && isFreeChildCell) {
                                    if (align === 'right') {
                                        cellText = (c === colspan - 1) ? text : '';
                                    } else if (align === 'left') {
                                        cellText = (c === 0) ? text : '';
                                    }
                                }
                                cells.push({text: cellText, rowspan: rowspan, colspan: c === 0 ? colspan : 0});
                            }
                        }
                        if (cells.length > 0) {
                            rows.push(cells);
                        }
                    }
                    if (rows.length > 0) {
                        result.push(rows);
                    }
                }
                return result;
            }""")
            for table_rows in expanded_tables:
                matrix = []
                for row_cells in table_rows:
                    matrix.append([c["text"] for c in row_cells])
                if matrix:
                    bands.extend(parse_grille_table(matrix))
        except Exception as exc:
            logger.debug("scrape_price_grid: Playwright DOM expansion failed — %s", exc)

    if not bands:
        try:
            body = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
            bands.extend(_parse_grille_from_plaintext(body))
        except Exception:
            pass

    logger.info(
        "scrape_price_grid: village=%s bands_found=%d",
        village_id, len(bands),
    )
    return bands


def _parse_grille_from_plaintext(
    page_text: str,
    notes: Optional[list[str]] = None,
) -> list[RawPriceBand]:
    """Best-effort parse when markdown-like table text is in the body."""
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    rows: list[list[str]] = []
    for ln in lines:
        if "|" in ln:
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if cells:
                rows.append(cells)
    return parse_grille_table(rows, page_text=page_text, notes=notes)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _formules_priced(bands: list[RawPriceBand]) -> set[str]:
    return {b.formule for b in bands if _is_priced(b)}


def _needs_fallback(
    bands: list[RawPriceBand],
    expected_formules: Optional[set[str]],
) -> bool:
    """True when cascade should continue (PS-06: per-formule completeness)."""
    present = _formules_priced(bands)
    if expected_formules:
        return not expected_formules.issubset(present)
    return not present


def scrape_village(
    village_id: str,
    url: str,
    expected_formules: Optional[Iterable[str]] = None,
) -> VillageScrapeResult:
    """Scrape grille tariffs, then use fallback tiers only when needed.

    No DB writes — caller (tarif_builder) decides what to persist.
    Fast path: HTTP HTML parse of the embedded grille popin.
    Playwright grid is used only when HTTP yields no prices.
    Booking widget is used only when no grille tier yields prices.
    """
    result = VillageScrapeResult(village_id=village_id, url=url)
    expected: Optional[set[str]] = (
        {f for f in expected_formules if f in ("PC", "DP", "LOC")}
        if expected_formules is not None
        else None
    )
    grid_bands: list[RawPriceBand] = []

    # 1) Fast path — static HTML already contains the grille table
    http_format_change: Optional[FormatChangeInfo] = None
    http_fetch_error: Optional[str] = None
    cached_html = ""
    try:
        http_result = scrape_price_grid_http(village_id, url)
        if http_result.fetch_error:
            http_fetch_error = http_result.fetch_error
        grid_bands = list(http_result.bands)
        result.bands.extend(grid_bands)
        result.parse_notes.extend(http_result.parse_notes)
        http_format_change = http_result.format_change
        cached_html = http_result.html or ""
        if (
            not grid_bands
            and http_result.html_len > 0
            and not http_result.has_grille_markers
        ):
            result.errors.append(
                f"{STEP_2_HTML_GRID_PARSE} | {STEP_2_SRC} | "
                f"Page loaded (html_len={http_result.html_len}) "
                "but no price grid markers found (grille tarifaire, pension complète, etc.). "
                "The VTF page layout may have changed."
            )
    except Exception as exc:
        msg = f"{STEP_2_HTML_GRID_PARSE} | {STEP_2_SRC} | {exc}"
        logger.exception("scrape_village: %s %s", village_id, msg)
        result.errors.append(msg)

    need_playwright = not any(_is_priced(band) for band in grid_bands)

    if need_playwright:
        sync_playwright = None
        try:
            from playwright.sync_api import sync_playwright as _sync_playwright
            sync_playwright = _sync_playwright
        except ImportError:
            if need_playwright:
                result.errors.append(
                    f"{STEP_3_PLAYWRIGHT_INIT} | {STEP_3_SRC} | "
                    "Playwright is not installed. "
                    "HTTP grille returned no bands. "
                    "Run: pip install playwright && playwright install chromium"
                )

        if sync_playwright is not None:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page(user_agent=HTTP_HEADERS["User-Agent"])

                if not any(_is_priced(band) for band in grid_bands):
                    try:
                        pw_bands = scrape_price_grid(village_id, url, page)
                        result.bands.extend(pw_bands)
                        grid_bands = list(result.bands)
                    except Exception as exc:
                        msg = f"{STEP_4_PW_GRID_PARSE} | {STEP_4_SRC} | {exc}"
                        logger.exception("scrape_village: %s %s", village_id, msg)
                        result.errors.append(msg)

                if not any(_is_priced(band) for band in grid_bands):
                    try:
                        widget_bands = scrape_booking_widget(village_id, url, page)
                        result.bands.extend(widget_bands)
                    except Exception as exc:
                        msg = f"{STEP_5_WIDGET_SCRAPE} | {STEP_5_SRC} | {exc}"
                        logger.exception("scrape_village: %s %s", village_id, msg)
                        result.errors.append(msg)

                browser.close()

    # ── LLM fallback (3rd tier — only when HTTP + Playwright both failed) ──
    priced = [b for b in result.bands if _is_priced(b)]
    if not priced or (expected and not expected.issubset(_formules_priced(result.bands))):
        # Only call LLM when nothing priced yet (keep prior behaviour for partial)
        if not priced:
            try:
                from apps.tariff_scraper.services.llm_fallback import (
                    llm_fallback_enabled,
                    parse_grille_with_llm,
                )
                if llm_fallback_enabled():
                    # Reuse HTTP HTML when available; only re-fetch if cache is empty
                    llm_html = cached_html
                    if not llm_html:
                        try:
                            llm_html = fetch_village_html(url)
                        except Exception:
                            llm_html = ""
                    if llm_html:
                        llm_bands = parse_grille_with_llm(llm_html, village_id)
                        result.bands.extend(llm_bands)
                        logger.info(
                            "scrape_village: LLM fallback produced %d bands for %s",
                            len(llm_bands), village_id,
                        )
            except ImportError:
                logger.debug("scrape_village: llm_fallback module not installed")
            except Exception as exc:
                msg = f"{STEP_6_LLM_FALLBACK} | {STEP_6_SRC} | {exc}"
                logger.exception("scrape_village: %s %s", village_id, msg)
                result.errors.append(msg)

    priced = [b for b in result.bands if _is_priced(b)]
    if not priced:
        if http_fetch_error:
            result.errors.append(
                f"{STEP_1_HTTP_FETCH} | {STEP_1_SRC} | {http_fetch_error}"
            )
        result.errors.append(
            f"{STEP_7_VALIDATION} | {STEP_7_SRC} | "
            "No priced tariff bands extracted from any source "
            f"(grille, widget, or LLM). Total bands scraped: {len(result.bands)}. "
            "Nothing will be written to VillageTarif."
        )
    elif expected:
        missing = sorted(expected - _formules_priced(result.bands))
        if missing:
            result.parse_notes.append(
                f"missing_formules: expected {sorted(expected)}, missing {missing}"
            )

    # ── Final format change detection ─────────────────────────────────────
    # Only set change_detected=True when the scrape actually failed.
    # Non-fatal errors (e.g. HTTP failed but Playwright succeeded) are just
    # warnings — not format changes.
    final_fc = http_format_change or FormatChangeInfo()

    if http_format_change and http_format_change.change_detected and not priced:
        # HTTP detected format change AND we got no prices → real format change
        result.format_change = http_format_change
    elif http_format_change and http_format_change.change_type == "header_misalignment":
        result.format_change = http_format_change
    elif not priced:
        # Page loaded but zero prices → layout changed
        result.format_change = FormatChangeInfo(
            change_detected=True,
            change_type="zero_prices",
            expected_markers=final_fc.expected_markers or list(EXPECTED_GRILLE_MARKERS),
            found_markers=final_fc.found_markers,
            missing_markers=final_fc.missing_markers,
            html_length=final_fc.html_length,
            table_count=final_fc.table_count,
            bands_scraped=len(result.bands),
            priced_bands=0,
        )
    # else: priced > 0 → scrape succeeded, no format change (errors are just warnings)

    # ── DP remise verification (diagnostic only — never blocks the scrape) ─
    # Only worth running when a DP band was actually *derived* from PC using
    # the regex/static remise — i.e. the thing the client is worried about
    # was actually used for this village.
    derived_dp = [
        b for b in result.bands
        if b.formule == "DP" and b.derivation in (DERIVATION_STATED, DERIVATION_ASSUMED)
    ]
    if priced and derived_dp:
        try:
            from apps.tariff_scraper.services.dp_verification import verify_dp_remise
            verify_html = cached_html
            if not verify_html:
                try:
                    verify_html = fetch_village_html(url)
                except Exception:
                    verify_html = ""
            if verify_html:
                result.dp_verification = verify_dp_remise(verify_html, village_id)
        except ImportError:
            logger.debug("scrape_village: dp_verification module not installed")
        except Exception:
            # Never let a verification bug affect the scrape itself.
            logger.exception(
                "scrape_village: dp_verification failed for %s (ignored)", village_id
            )

    logger.info(
        "scrape_village: village=%s total_bands=%d priced=%d errors=%d format_change=%s",
        village_id, len(result.bands), len(priced), len(result.errors),
        result.format_change.change_type if result.format_change else "none",
    )
    return result


def scrape_village_all_seasons(
    village_id: str,
    expected_formules: Optional[Iterable[str]] = None,
) -> VillageScrapeResult:
    """Scrape every registered URL for a village and merge into one result.

    Summer-only (and winter-only) villages have exactly one URL, so this is
    identical to calling ``scrape_village`` directly. Dual-season villages
    (``DUAL_SEASON_VILLAGE_IDS``) have two URLs — ``/summer/`` and
    ``/winter/`` — and each one runs the **full Tier 1-4 cascade
    independently** via a separate ``scrape_village`` call. A summer success
    never short-circuits the winter scrape, since each call escalates only
    within its own result (same PS-06 / zero-priced cascade as today).

    Every ``RawPriceBand`` produced for a URL is stamped with that URL's
    ``scrape_source`` ("summer" | "winter"). Errors and parse notes are
    prefixed with ``[summer]`` / ``[winter]`` so Step 1-7 alerts stay
    attributable per season when there is more than one URL. The merged
    result's ``url`` is the first (summer/primary) URL — the per-band
    ``scrape_source`` is the actual review signal for dual villages.

    A village succeeds overall as long as **at least one** season yields
    priced bands — a Tier 1-4 failure on winter must not discard a good
    summer result, and vice versa.
    """
    from apps.tariff_scraper.services.village_urls import get_village_scrape_urls

    urls = get_village_scrape_urls(village_id)
    if not urls:
        return VillageScrapeResult(
            village_id=village_id,
            url="",
            errors=[f"No URL registered for village '{village_id}'"],
        )

    merged = VillageScrapeResult(village_id=village_id, url=urls[0][0])
    format_changes: list[FormatChangeInfo] = []
    dp_verifications: list = []

    for url, scrape_source in urls:
        season_result = scrape_village(village_id, url, expected_formules=expected_formules)

        for band in season_result.bands:
            band.scrape_source = scrape_source
        merged.bands.extend(season_result.bands)

        prefix = f"[{scrape_source}]" if len(urls) > 1 else ""
        merged.errors.extend(
            f"{prefix} {err}" if prefix else err for err in season_result.errors
        )
        merged.parse_notes.extend(
            f"{prefix} {note}" if prefix else note for note in season_result.parse_notes
        )

        if season_result.format_change is not None:
            format_changes.append(season_result.format_change)
        if season_result.dp_verification is not None:
            dp_verifications.append(season_result.dp_verification)

    # Prefer a format_change that actually blocked pricing (no priced bands)
    # over one from a season that succeeded; fall back to the first present.
    if format_changes:
        blocking = [fc for fc in format_changes if fc.priced_bands == 0 and fc.change_detected]
        merged.format_change = blocking[0] if blocking else format_changes[0]

    # DP verification is diagnostic-only; keep the first one we got.
    if dp_verifications:
        merged.dp_verification = dp_verifications[0]

    logger.info(
        "scrape_village_all_seasons: village=%s urls=%d total_bands=%d errors=%d",
        village_id, len(urls), len(merged.bands), len(merged.errors),
    )
    return merged
