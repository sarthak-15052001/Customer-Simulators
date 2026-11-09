"""Office de Tourisme (OT local) adapter — Playwright-based scraper (Phase 3).

Scrapes local Office de Tourisme websites for activities when external APIs
don't have coverage. Uses Playwright for JS-rendered pages.

Spec §5.2 — OfficeTourismeAdapter.

Each village can have a configured OT URL in VTF_OT_URLS. When Playwright
is not installed or the URL is not configured, the adapter returns an empty
list gracefully.
"""
from __future__ import annotations

import logging
import hashlib
import html
import json
import math
import os
import re
import time
from datetime import date
from urllib.parse import urljoin, urlparse

from apps.scraper.adapters.base import (
    ActivitySourceAdapter,
    ScrapedActivity,
    type_hint_to_emoji,
)
from apps.scraper.dedup import deduplicate_candidates
from apps.scraper.services.ot_urls import VTF_OT_URLS

logger = logging.getLogger(__name__)

_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_EURO_TOKEN_RE = r"(?:\u20ac|EUR|euros?)"
_PRICE_RE = re.compile(
    rf"(?:{_EURO_TOKEN_RE}\s*(?P<prefix_value>\d{{1,3}}(?:[,.]\d{{1,2}})?)|"
    rf"(?P<suffix_value>\d{{1,3}}(?:[,.]\d{{1,2}})?)\s*{_EURO_TOKEN_RE})",
    re.IGNORECASE,
)
_PLAIN_AMOUNT_RE = re.compile(
    r"(?<![\d])(?P<value>\d{1,3}(?:[,.]\d{1,2})?)(?!\d)"
    r"(?!\s*(?:ans?|mois|jours?|heures?|h|km|kilom[eè]tres?|m)\b)",
    re.IGNORECASE,
)
_TARIFF_HINT_RE = re.compile(
    rf"(?:{_EURO_TOKEN_RE}|tarifs?|prix|adulte|adultes|enfant|enfants|"
    r"plein tarif|tarif plein|tarif normal|tarif unique|tarif reduit|"
    r"tarif r[eé]duit|gratuit|gratuite)",
    re.IGNORECASE,
)
_ADULT_RE = re.compile(
    r"\b(?:adulte|adultes|plein tarif|tarif normal|tarif plein|"
    r"tarif individuel|tarif unique|tarif de base|aller retour adulte|"
    r"aller adulte|personne|visiteur)\b",
    re.IGNORECASE,
)
_CHILD_RE = re.compile(
    r"\b(?:enfant|enfants|jeune|jeunes|junior|ado|ados|"
    r"moins de \d+ ans|de \d+ à \d+ ans|de \d+ a \d+ ans|"
    r"tarif reduit|tarif réduit|reduit|réduit|scolaire|étudiant|etudiant)\b",
    re.IGNORECASE,
)
_FREE_RE = re.compile(
    r"\b(?:gratuit|gratuite|entrée libre|entree libre|accès libre|acces libre)\b",
    re.IGNORECASE,
)
_RATING_RE = re.compile(
    r"(?:note|avis|rating|score)?\s*(?P<rating>[0-5](?:[,.]\d{1,2})?)\s*(?:/|sur)\s*5\b",
    re.IGNORECASE,
)
_RATING_STAR_RE = re.compile(
    r"\b(?P<rating>[0-5](?:[,.]\d{1,2})?)\s*(?:étoiles?|stars?)\b",
    re.IGNORECASE,
)
_RATING_NOTE_RE = re.compile(
    r"\b(?:note|avis|rating|score)\s*:\s*(?P<rating>[0-5](?:[,.]\d{1,2})?)\b",
    re.IGNORECASE,
)
_RATING_VALUE_RE = re.compile(
    r'"(?:ratingValue|rating_value)"\s*:\s*"?(?P<rating>[0-5](?:[,.]\d{1,2})?)"?',
    re.IGNORECASE,
)
_META_RATING_RE = re.compile(
    r'(?:itemprop|property|name)=["\'](?:ratingValue|rating_value|og:rating)["\'][^>]+'
    r'content=["\'](?P<rating>[0-5](?:[,.]\d{1,2})?)["\']',
    re.IGNORECASE,
)
_META_RATING_REVERSE = re.compile(
    r'content=["\'](?P<rating>[0-5](?:[,.]\d{1,2})?)["\'][^>]+'
    r'(?:itemprop|property|name)=["\'](?:ratingValue|rating_value|og:rating)["\']',
    re.IGNORECASE,
)
_REVIEW_COUNT_RE = re.compile(
    r"\b(?P<count>\d{1,6}(?:[\s.]\d{3})*)\s*(?:avis|reviews?|commentaires?)\b",
    re.IGNORECASE,
)
_REVIEW_COUNT_NOTE_RE = re.compile(
    r"\b(?P<count>\d{1,6}(?:[\s.]\d{3})*)\s*(?:notes|evaluations?|évaluations?)\b",
    re.IGNORECASE,
)
_REVIEW_COUNT_VALUE_RE = re.compile(
    r'"(?:reviewCount|ratingCount|review_count|rating_count)"\s*:\s*"?(?P<count>\d{1,6})"?',
    re.IGNORECASE,
)
_META_REVIEW_COUNT_RE = re.compile(
    r'(?:itemprop|property|name)=["\'](?:reviewCount|ratingCount|review_count|rating_count)["\'][^>]+'
    r'content=["\'](?P<count>\d{1,6})["\']',
    re.IGNORECASE,
)
_META_REVIEW_COUNT_REVERSE = re.compile(
    r'content=["\'](?P<count>\d{1,6})["\'][^>]+'
    r'(?:itemprop|property|name)=["\'](?:reviewCount|ratingCount|review_count|rating_count)["\']',
    re.IGNORECASE,
)
_DISTANCE_RE = re.compile(
    r"\b(?:à|a|distance|situé à|situe a)?\s*"
    r"(?P<value>\d{1,3}(?:[,.]\d{1,2})?)\s*(?P<unit>km|kilomètres?|kilometres?|m)\b",
    re.IGNORECASE,
)
_LAT_LNG_RE = re.compile(
    r"(?P<lat>[+-]?(?:[1-8]?\d(?:\.\d+)?|90(?:\.0+)?))\s*[,;]\s*"
    r"(?P<lng>[+-]?(?:1[0-7]\d(?:\.\d+)?|[1-9]?\d(?:\.\d+)?|180(?:\.0+)?))"
)
_JSON_GEO_RE = re.compile(
    r'"latitude"\s*:\s*"?(?P<lat>[+-]?\d+(?:\.\d+)?)"?'
    r".{0,160}?"
    r'"longitude"\s*:\s*"?(?P<lng>[+-]?\d+(?:\.\d+)?)"?',
    re.IGNORECASE | re.DOTALL,
)
_MAP_COORD_RE = re.compile(
    r"(?:@|[?&](?:q|ll|center)=)"
    r"(?P<lat>[+-]?(?:[1-8]?\d(?:\.\d+)?|90(?:\.0+)?))\s*[,;]"
    r"\s*(?P<lng>[+-]?(?:1[0-7]\d(?:\.\d+)?|[1-9]?\d(?:\.\d+)?|180(?:\.0+)?))"
)
_DATE_MONTH_RE = re.compile(r"\b\d{1,2}/(?P<month>\d{1,2})(?:/\d{2,4})?\b")
_INVALID_TITLE_RE = re.compile(
    r"\b(?:découvrez toutes les activités|decouvrez toutes les activites|"
    r"toutes les activités|toutes les activites|en savoir plus|"
    r"réservez en ligne|reservez en ligne|voir plus|accueil|contact|"
    r"tarifs?|horaires?|agenda|carte|plan|nouveau|exclusivité|billetterie|plus d'infos?)\b",
    re.IGNORECASE,
)
_PRICE_OR_META_LINE_RE = re.compile(
    r"(?:€|EUR|avis|note|rating|\b\d{1,2}[,.]\d\s*/\s*5\b|"
    r"gratuit|tarif|à partir|a partir)",
    re.IGNORECASE,
)
_NON_ACTIVITY_TEXT_RE = re.compile(
    r"\b(?:cookie|cookies|newsletter|menu|ouvrir|fermer|rechercher|"
    r"instagram|facebook|youtube|linkedin|compte|panier|"
    r"conditions generales|mentions legales|politique de confidentialite)\b",
    re.IGNORECASE,
)

# Activity keywords to detect from page text
_ACTIVITY_KEYWORDS = {
    "musée": "museum",
    "museum": "museum",
    "aquarium": "aquarium",
    "zoo": "zoo",
    "parc": "park",
    "plage": "beach",
    "surf": "surf",
    "kayak": "kayak",
    "escalade": "climbing",
    "randonnée": "hiking",
    "ski": "ski",
    "château": "castle",
    "escape": "escape_game",
    "accrobranche": "climbing",
    "karting": "karting",
    "golf": "golf",
    "équitation": "horse_riding",
    "plongée": "diving",
    "voile": "boat",
    "spa": "spa",
    "bowling": "bowling",
    "cinéma": "cinema",
    "théâtre": "theater",
    "marché": "market",
}

_SCHEMA_ACTIVITY_TYPES = {
    "event",
    "touristattraction",
    "localbusiness",
    "sportsactivitylocation",
    "entertainmentbusiness",
    "museum",
    "park",
    "place",
    "product",
}

_DISCOVERY_TERMS = (
    "activit",
    "loisir",
    "que-faire",
    "a-faire",
    "visite",
    "famille",
    "sport",
    "culture",
    "agenda",
    "billetterie",
    "reservation",
    "réservation",
    "explorer",
    "experience",
    "expérience",
    "incontournable",
    "patrimoine",
    "mon-sejour",
    "sejour",
    "séjour",
    "decouvrir",
    "découvrir",
)

# Selectors used to find activity listings on typical OT sites
_ACTIVITY_SELECTORS = [
    "article.fiche-activite",
    "div.fiche-activite",
    ".activity-card",
    ".loisir-item",
    ".iris-card",
    ".sit-item",
    ".sitra-item",
    ".apidae-item",
    "[class*='sitra']",
    "[class*='apidae']",
    "[class*='fiche']",
    "[data-latitude]",
    "[data-lat]",
    "[itemtype*='TouristAttraction']",
    "[itemtype*='Event']",
    "article[class*='activit']",
    "div[class*='activit']",
    ".sitchable",
    "li.sitchable",
    ".list-item",
    "article",
]

# Price page URL patterns on typical OT sites
_PRICE_URL_PATTERNS = [
    "/activites",
    "/activites-loisirs",
    "/activites-et-loisirs",
    "/loisirs-activites",
    "/que-faire",
    "/a-faire",
    "/a-voir-a-faire",
    "/a-voir-a-faire/activites",
    "/a-faire-a-biarritz",
    "/decouvrir",
    "/fr/decouvrir",
    "/explorer",
    "/loisirs",
    "/loisirs-et-decouvertes",
    "/mon-sejour/explorer/sport-et-loisirs",
    "/visites",
    "/activités",
    "/activites-a-serre-poncon",
    "/category/loisirs",
    "/activites-ventoux.html",
    "/activites/activites-et-loisirs-reservables-en-ligne",
    "/agenda",
    "/billetterie",
]


def _stable_id(*parts: str) -> str:
    raw = "|".join(part for part in parts if part)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _parse_euro(value: str) -> int:
    return int(round(float(value.replace(",", "."))))


def _clean_text(value: str) -> str:
    """Decode entities and collapse whitespace without changing meaning."""
    return re.sub(r"[ \t\r\f\v]+", " ", html.unescape(value or "")).strip()


def _fold_text(value: str) -> str:
    import unicodedata

    cleaned = _clean_text(value).lower()
    normalized = unicodedata.normalize("NFKD", cleaned)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _line_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    return line_start, line_end


def _neighbor_line(text: str, line_start: int, line_end: int, *, previous: bool) -> str:
    if previous:
        if line_start <= 1:
            return ""
        prev_start = text.rfind("\n", 0, line_start - 2) + 1
        return text[prev_start:line_start - 1].strip()
    if line_end >= len(text):
        return ""
    next_end = text.find("\n", line_end + 1)
    if next_end == -1:
        next_end = len(text)
    return text[line_end + 1:next_end].strip()


def _price_context_for_match(text: str, start: int, end: int) -> str:
    line_start, line_end = _line_bounds(text, start, end)
    current_line = text[line_start:line_end].strip()
    prev_line = _neighbor_line(text, line_start, line_end, previous=True)
    next_line = _neighbor_line(text, line_start, line_end, previous=False)

    if _ADULT_RE.search(current_line) or _CHILD_RE.search(current_line):
        return current_line
    if _ADULT_RE.search(prev_line) or _CHILD_RE.search(prev_line):
        return f"{prev_line}\n{current_line}"
    if _ADULT_RE.search(next_line) or _CHILD_RE.search(next_line):
        return f"{current_line}\n{next_line}"
    return text[max(0, start - 80): min(len(text), end + 80)]


def _amount_segment_context(line: str, start: int, end: int) -> str:
    boundaries = [0, len(line)]
    for sep in ("/", "|", ";", "\t", "  "):
        pos = 0
        while True:
            found = line.find(sep, pos)
            if found == -1:
                break
            boundaries.extend([found, found + len(sep)])
            pos = found + len(sep)

    left = max(boundary for boundary in boundaries if boundary <= start)
    right = min(boundary for boundary in boundaries if boundary >= end)
    segment = line[left:right].strip(" /|;\t")
    return segment or line


def _looks_like_age_or_date_amount(line: str, start: int, end: int) -> bool:
    before = _fold_text(line[max(0, start - 24):start])
    after = _fold_text(line[end:min(len(line), end + 24)])
    if re.match(r"\s*ans?\b", after):
        return True
    if re.match(r"\s*(?:a|à|-)\s*\d{1,2}\s*ans?\b", after):
        return True
    if re.search(r"\b(?:moins de|plus de|jusqu'a|jusqu a|de)\s*$", before) and re.match(
        r"\s*ans?\b", after
    ):
        return True
    if re.search(r"\b\d{1,2}\s*(?:a|à|-)\s*$", before) and re.match(r"\s*ans?\b", after):
        return True
    if re.search(r"\b\d{1,2}\s*/\s*$", before) or re.match(r"\s*/\s*\d{1,2}", after):
        return True
    return False


def _collect_price_candidates(text: str) -> list[tuple[int, str]]:
    candidates: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()

    def add(price: int, context: str) -> None:
        if not 0 <= price <= 300:
            return
        key = (price, _fold_text(context))
        if key not in seen:
            seen.add(key)
            candidates.append((price, context))

    for match in _PRICE_RE.finditer(text):
        try:
            price = _parse_euro(match.group("prefix_value") or match.group("suffix_value"))
        except ValueError:
            continue
        add(price, _price_context_for_match(text, match.start(), match.end()))

    offset = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        line_start = offset + raw_line.find(line) if line else offset
        offset += len(raw_line) + 1
        if not line or not _TARIFF_HINT_RE.search(line):
            continue
        if not (_ADULT_RE.search(line) or _CHILD_RE.search(line) or _PRICE_RE.search(line)):
            continue
        for match in _PLAIN_AMOUNT_RE.finditer(line):
            if _looks_like_age_or_date_amount(line, match.start(), match.end()):
                continue
            value = match.group("value")
            absolute_start = line_start + match.start()
            absolute_end = line_start + match.end()
            try:
                price = _parse_euro(value)
            except ValueError:
                continue
            context = _amount_segment_context(line, match.start(), match.end())
            if not (_ADULT_RE.search(context) or _CHILD_RE.search(context)):
                context = _price_context_for_match(text, absolute_start, absolute_end)
            add(price, context)

    return candidates


def _extract_price(text: str) -> tuple[int | None, int | None]:
    """Extract adult and child prices from French OT text."""
    if not text:
        return None, None
    text = _clean_text(text)

    # Clean up spaces around decimal separators (e.g. "9 .50 €" -> "9.50 €")
    text = re.sub(r"\b(\d+)\s*([.,])\s*(\d+)\b", r"\1\2\3", text)

    if _FREE_RE.search(text) and not _PRICE_RE.search(text):
        return 0, 0

    adult_prices: list[int] = []
    child_prices: list[int] = []
    other_prices: list[int] = []

    for price, context in _collect_price_candidates(text):
        has_child_label = _CHILD_RE.search(context)
        has_adult_label = _ADULT_RE.search(context)
        if has_child_label and not has_adult_label:
            child_prices.append(price)
        elif has_adult_label and not has_child_label:
            adult_prices.append(price)
        else:
            other_prices.append(price)

    if _FREE_RE.search(text):
        folded = _fold_text(text)
        if _CHILD_RE.search(text) and any(term in folded for term in ("gratuit", "gratuite")):
            child_prices.append(0)
        elif _ADULT_RE.search(text) and any(term in folded for term in ("gratuit", "gratuite")):
            adult_prices.append(0)

    if adult_prices or child_prices:
        adult = max(adult_prices) if adult_prices else None
        child = min(child_prices) if child_prices else None
        if adult is None and other_prices:
            adult = max(other_prices)
        if child is None and adult is not None:
            cheaper = [price for price in other_prices if price < adult]
            child = min(cheaper) if cheaper else None
        return adult, child

    prices = sorted(set(other_prices))
    if not prices:
        return None, None
    adult = max(prices)
    child = min(prices) if len(prices) > 1 and min(prices) < adult else None
    return adult, child


def _extract_rating(text: str) -> tuple[float | None, int]:
    rating: float | None = None
    review_count = 0
    if text:
        text = _clean_text(text)
        match = _RATING_RE.search(text)
        if not match:
            match = _RATING_STAR_RE.search(text)
        if not match:
            match = _RATING_NOTE_RE.search(text)
        if not match:
            match = _RATING_VALUE_RE.search(text)
        if not match:
            match = _META_RATING_RE.search(text)
        if not match:
            match = _META_RATING_REVERSE.search(text)
        if match:
            try:
                rating = float(match.group("rating").replace(",", "."))
            except ValueError:
                rating = None

        count_match = _REVIEW_COUNT_RE.search(text)
        if not count_match:
            count_match = _REVIEW_COUNT_NOTE_RE.search(text)
        if not count_match:
            count_match = _REVIEW_COUNT_VALUE_RE.search(text)
        if not count_match:
            count_match = _META_REVIEW_COUNT_RE.search(text)
        if not count_match:
            count_match = _META_REVIEW_COUNT_REVERSE.search(text)
        if count_match:
            try:
                review_count = int(count_match.group("count").replace(" ", "").replace(".", ""))
            except ValueError:
                review_count = 0
    return rating, review_count


def _extract_distance_km(text: str) -> float | None:
    if not text:
        return None
    for match in _DISTANCE_RE.finditer(_clean_text(text)):
        try:
            value = float(match.group("value").replace(",", "."))
        except ValueError:
            continue
        unit = match.group("unit").lower()
        if unit == "m":
            value = value / 1000
        if 0 <= value <= 100:
            return round(value, 2)
    return None


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _schema_type_names(item: dict) -> set[str]:
    names: set[str] = set()
    for value in _as_list(item.get("@type")):
        if isinstance(value, str):
            names.add(value.lower().replace(" ", ""))
    return names


def _iter_schema_nodes(obj):
    if isinstance(obj, list):
        for value in obj:
            yield from _iter_schema_nodes(value)
        return
    if not isinstance(obj, dict):
        return
    graph = obj.get("@graph")
    if isinstance(graph, list):
        for value in graph:
            yield from _iter_schema_nodes(value)
    yield obj


def _coerce_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _extract_schema_geo(item: dict) -> tuple[float, float] | None:
    location = item.get("location")
    geo_sources = [
        item.get("geo"),
        location.get("geo") if isinstance(location, dict) else None,
    ]
    for geo in geo_sources:
        if not isinstance(geo, dict):
            continue
        lat = _coerce_float(geo.get("latitude"))
        lng = _coerce_float(geo.get("longitude"))
        if lat is not None and lng is not None and -90 <= lat <= 90 and -180 <= lng <= 180:
            return lat, lng
    return None


def _extract_schema_text(item: dict) -> str:
    parts: list[str] = []
    for key in ("name", "description", "disambiguatingDescription", "startDate", "endDate"):
        value = item.get(key)
        if isinstance(value, str):
            parts.append(value)
    location = item.get("location")
    if isinstance(location, dict):
        for key in ("name", "description"):
            value = location.get(key)
            if isinstance(value, str):
                parts.append(value)
    for offer in _as_list(item.get("offers")):
        if isinstance(offer, dict):
            for key in ("name", "description", "price"):
                value = offer.get(key)
                if isinstance(value, (str, int, float)):
                    parts.append(str(value))
    return "\n".join(parts)


def _extract_schema_price(item: dict, text: str) -> tuple[int | None, int | None]:
    if item.get("isAccessibleForFree") is True:
        return 0, 0
    offer_prices: list[int] = []
    labelled_parts: list[str] = [text]
    for offer in _as_list(item.get("offers")):
        if not isinstance(offer, dict):
            continue
        offer_label_parts = []
        for key in ("name", "description", "category", "eligibleCustomerType"):
            value = offer.get(key)
            if isinstance(value, (str, int, float)):
                offer_label_parts.append(str(value))
        for key in ("price", "minPrice", "maxPrice", "lowPrice", "highPrice"):
            parsed = _coerce_float(offer.get(key))
            if parsed is not None and 0 <= parsed <= 300:
                offer_prices.append(int(round(parsed)))
                labelled_parts.append(" ".join([*offer_label_parts, f"{parsed:g} EUR"]).strip())
        for spec in _as_list(offer.get("priceSpecification")):
            if isinstance(spec, dict):
                spec_label_parts = list(offer_label_parts)
                for key in ("name", "description", "category", "eligibleCustomerType"):
                    value = spec.get(key)
                    if isinstance(value, (str, int, float)):
                        spec_label_parts.append(str(value))
                for key in ("price", "minPrice", "maxPrice", "lowPrice", "highPrice"):
                    parsed = _coerce_float(spec.get(key))
                    if parsed is not None and 0 <= parsed <= 300:
                        offer_prices.append(int(round(parsed)))
                        labelled_parts.append(" ".join([*spec_label_parts, f"{parsed:g} EUR"]).strip())
    labelled_adult, labelled_child = _extract_price("\n".join(part for part in labelled_parts if part))
    if labelled_adult is not None or labelled_child is not None:
        return labelled_adult, labelled_child
    if offer_prices:
        prices = sorted(set(offer_prices))
        adult = max(prices)
        child = min(prices) if len(prices) > 1 and min(prices) < adult else None
        return adult, child
    return _extract_price(text)


def _month_to_saison(month: int) -> set[str]:
    if month in (6, 7, 8, 9):
        return {"ete"}
    if month in (12, 1, 2, 3):
        return {"hs", "fetes"}
    if month in (4, 5, 10, 11):
        return {"vs"}
    return set()


def _extract_saisons_from_dates(*values: str) -> list[str]:
    saisons: set[str] = set()
    for raw in values:
        if not raw:
            continue
        try:
            parsed = date.fromisoformat(raw[:10])
        except ValueError:
            continue
        saisons.update(_month_to_saison(parsed.month))
    return [season for season in ("hs", "vs", "ete", "fetes") if season in saisons]


def _extract_rating_from_json_ld(page) -> tuple[float | None, int]:
    """Read schema.org aggregateRating from JSON-LD when available."""
    try:
        scripts = page.eval_on_selector_all(
            "script[type='application/ld+json']",
            "els => els.map(el => el.textContent || '').filter(Boolean)",
        )
    except Exception:
        return None, 0

    def walk(obj) -> tuple[float | None, int]:
        if isinstance(obj, list):
            for item in obj:
                found = walk(item)
                if found != (None, 0):
                    return found
        if not isinstance(obj, dict):
            return None, 0
        rating_obj = obj.get("aggregateRating") or obj.get("aggregate_rating")
        if isinstance(rating_obj, dict):
            rating_raw = rating_obj.get("ratingValue") or rating_obj.get("rating_value")
            count_raw = (
                rating_obj.get("reviewCount")
                or rating_obj.get("ratingCount")
                or rating_obj.get("review_count")
                or rating_obj.get("rating_count")
                or 0
            )
            try:
                rating = float(str(rating_raw).replace(",", ".")) if rating_raw else None
            except ValueError:
                rating = None
            try:
                count = int(float(str(count_raw).replace(" ", ""))) if count_raw else 0
            except ValueError:
                count = 0
            return rating, count
        for value in obj.values():
            found = walk(value)
            if found != (None, 0):
                return found
        return None, 0

    for raw in scripts:
        try:
            found = walk(json.loads(raw))
        except Exception:
            continue
        if found != (None, 0):
            return found
    return None, 0


def _extract_saisons(text: str) -> list[str]:
    lower = _fold_text(text)
    if any(term in lower for term in ("toute l'annee", "tous les jours de l'annee", "4 saisons")):
        return ["hs", "vs", "ete", "fetes"]

    saisons: set[str] = set()
    if any(term in lower for term in ("ete", "juillet", "aout", "juin", "septembre")):
        saisons.add("ete")
    if any(term in lower for term in ("hiver", "decembre", "janvier", "fevrier", "mars", "noel")):
        saisons.update({"hs", "fetes"})
    if any(term in lower for term in ("printemps", "automne", "avril", "mai", "octobre", "novembre")):
        saisons.add("vs")
    for match in _DATE_MONTH_RE.finditer(lower):
        month = int(match.group("month"))
        if month in (6, 7, 8, 9):
            saisons.add("ete")
        elif month in (12, 1, 2, 3):
            saisons.update({"hs", "fetes"})
        elif month in (4, 5, 10, 11):
            saisons.add("vs")
    return [season for season in ("hs", "vs", "ete", "fetes") if season in saisons] or [
        "hs",
        "vs",
        "ete",
        "fetes",
    ]


def _extract_coords_from_text(text: str) -> tuple[float, float] | None:
    if not text:
        return None
    for pattern in (_JSON_GEO_RE, _MAP_COORD_RE):
        match = pattern.search(text)
        if not match:
            continue
        try:
            lat = float(match.group("lat"))
            lng = float(match.group("lng"))
        except ValueError:
            continue
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return lat, lng
    return None


def _looks_like_activity_name(nom: str) -> bool:
    cleaned = _clean_text(nom)
    if len(cleaned) < 3 or len(cleaned) > 128:
        return False
    if _NON_ACTIVITY_TEXT_RE.search(_fold_text(cleaned)):
        return False
    if cleaned.isupper() and len(cleaned) < 20:
        return False
    if _INVALID_TITLE_RE.search(cleaned):
        return False
    if _PRICE_OR_META_LINE_RE.search(cleaned):
        return False
    return True


def _first_valid_line(text: str) -> str:
    valid_lines = []
    for line in (_clean_text(line) for line in (text or "").splitlines()):
        if _looks_like_activity_name(line):
            valid_lines.append(line)
    if valid_lines:
        return valid_lines[0]
    return ""


def _extract_name_from_element(el, fallback_text: str) -> str:
    selectors = [
        "[itemprop='name']",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        ".title",
        ".titre",
        ".nom",
        ".name",
        "[class*='title']",
        "[class*='titre']",
        "[class*='nom']",
        "[class*='name']",
    ]
    for selector in selectors:
        try:
            node = el.query_selector(selector)
            if not node:
                continue
            nom = _first_valid_line(node.inner_text() or "")
            if nom:
                return nom
        except Exception:
            continue

    for selector, attr in (("a[aria-label]", "aria-label"), ("img[alt]", "alt")):
        try:
            node = el.query_selector(selector)
            value = node.get_attribute(attr) if node else ""
            if _looks_like_activity_name(value or ""):
                return _clean_text(value or "")
        except Exception:
            continue

    try:
        link = el.query_selector("a[href]")
        if link:
            nom = _first_valid_line(link.inner_text() or "")
            if nom:
                return nom
    except Exception:
        pass

    return _first_valid_line(fallback_text)


def _distance_between_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return round(radius * 2 * math.asin(math.sqrt(a)), 2)


def _set_best_distance(
    activity: ScrapedActivity,
    text: str,
    center_lat: float,
    center_lng: float,
) -> None:
    text_distance = _extract_distance_km(text)
    if text_distance is not None:
        setattr(activity, "distance_km", text_distance)
        return
    if activity.latitude and activity.longitude:
        setattr(
            activity,
            "distance_km",
            _distance_between_km(center_lat, center_lng, activity.latitude, activity.longitude),
        )


def _extract_coords_from_element(el) -> tuple[float, float] | None:
    try:
        raw = el.evaluate(
            """el => [
                el.outerHTML,
                el.getAttribute('data-lat'),
                el.getAttribute('data-lng'),
                el.getAttribute('data-latitude'),
                el.getAttribute('data-longitude')
            ].filter(Boolean).join('\\n')"""
        )
    except Exception:
        raw = ""
    return _extract_coords_from_text(raw or "")


def _extract_coords_from_page(page) -> tuple[float, float] | None:
    try:
        html = page.content()
    except Exception:
        html = ""
    coords = _extract_coords_from_text(html)
    if coords:
        return coords

    try:
        hrefs = page.eval_on_selector_all(
            "a[href*='google'], a[href*='maps'], a[href*='itineraire']",
            "els => els.map(el => el.href).join('\\n')",
        )
    except Exception:
        hrefs = ""
    return _extract_coords_from_text(hrefs or "")


def _detect_type(text: str) -> tuple[str, str]:
    """Detect activity type from text keywords."""
    lower = _fold_text(text)
    for keyword, type_hint in _ACTIVITY_KEYWORDS.items():
        if _fold_text(keyword) in lower:
            return type_hint, type_hint_to_emoji(type_hint)
    return "tourist_attraction", "📍"


def _schema_node_to_activity(
    item: dict,
    *,
    page_url: str,
    village_id: str,
    center_lat: float,
    center_lng: float,
) -> ScrapedActivity | None:
    schema_types = _schema_type_names(item)
    if schema_types and not (schema_types & _SCHEMA_ACTIVITY_TYPES):
        return None

    nom = _clean_text(str(item.get("name") or ""))
    if not _looks_like_activity_name(nom):
        return None

    text = _extract_schema_text(item)
    source_url = urljoin(page_url, str(item.get("url") or page_url))
    coords = _extract_schema_geo(item)
    latitude, longitude = coords or (center_lat, center_lng)

    type_hint, emoji = _detect_type("\n".join([nom, text, " ".join(schema_types)]))
    price_adult, price_child = _extract_schema_price(item, text)
    rating, review_count = _extract_rating(text)

    rating_obj = item.get("aggregateRating")
    if isinstance(rating_obj, dict):
        if rating is None:
            rating = _coerce_float(rating_obj.get("ratingValue"))
        if not review_count:
            review_count = int(_coerce_float(
                rating_obj.get("reviewCount") or rating_obj.get("ratingCount") or 0
            ) or 0)

    saisons = _extract_saisons_from_dates(
        str(item.get("startDate") or ""),
        str(item.get("endDate") or ""),
    ) or _extract_saisons(text)

    activity = ScrapedActivity(
        source="ot_local",
        source_id=f"ot:{village_id}:{_stable_id(source_url, nom)}",
        source_url=source_url,
        nom=nom[:128],
        type_hint=type_hint,
        type_emoji=emoji,
        latitude=latitude,
        longitude=longitude,
        price_adult=price_adult,
        price_child=price_child,
        rating=rating,
        review_count=review_count,
        description=text[:512],
        saisons=saisons,
    )
    _set_best_distance(activity, text, center_lat, center_lng)
    return activity


def _extract_activities_from_schema(
    page,
    page_url: str,
    village_id: str,
    max_results: int,
    center_lat: float,
    center_lng: float,
) -> list[ScrapedActivity]:
    activities: list[ScrapedActivity] = []
    try:
        scripts = page.eval_on_selector_all(
            "script[type='application/ld+json']",
            "els => els.map(el => el.textContent || '').filter(Boolean)",
        )
    except Exception:
        scripts = []

    for raw in scripts:
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        for node in _iter_schema_nodes(payload):
            activity = _schema_node_to_activity(
                node,
                page_url=page_url,
                village_id=village_id,
                center_lat=center_lat,
                center_lng=center_lng,
            )
            if activity is None:
                continue
            activities.append(activity)
            if len(activities) >= max_results:
                return activities
    return activities


def _dedupe_by_source_id(activities: list[ScrapedActivity]) -> list[ScrapedActivity]:
    seen: set[str] = set()
    unique: list[ScrapedActivity] = []
    for activity in activities:
        if activity.source_id in seen:
            continue
        seen.add(activity.source_id)
        unique.append(activity)
    return unique


def _discover_activity_links(page, base_url: str, max_links: int = 30) -> list[str]:
    base_netloc = urlparse(base_url).netloc
    try:
        raw_links = page.eval_on_selector_all(
            "a[href]",
            """els => els.map(el => ({
                href: el.href,
                text: (el.innerText || el.getAttribute('aria-label') || '').trim()
            }))""",
        )
    except Exception:
        return []

    links: list[str] = []
    for item in raw_links:
        href = item.get("href", "") if isinstance(item, dict) else ""
        text = item.get("text", "") if isinstance(item, dict) else ""
        parsed = urlparse(href)
        if parsed.netloc != base_netloc:
            continue
        haystack = _fold_text(f"{parsed.path} {text}")
        if not any(term in haystack for term in _DISCOVERY_TERMS):
            continue
        clean_url = href.split("#", 1)[0]
        if clean_url and clean_url not in links:
            links.append(clean_url)
        if len(links) >= max_links:
            break
    return links


def _discover_pagination_links(page, base_url: str, max_links: int = 8) -> list[str]:
    """Find next-page / numbered pagination links on listing pages."""
    base_netloc = urlparse(base_url).netloc
    try:
        raw_links = page.eval_on_selector_all(
            "a[href]",
            """els => els.map(el => ({
                href: el.href,
                text: (el.innerText || el.getAttribute('aria-label') || '').trim(),
                rel: (el.getAttribute('rel') || '').toLowerCase()
            }))""",
        )
    except Exception:
        return []

    links: list[str] = []
    for item in raw_links:
        if not isinstance(item, dict):
            continue
        href = item.get("href", "")
        text = _fold_text(item.get("text", ""))
        rel = item.get("rel", "")
        parsed = urlparse(href)
        if parsed.netloc != base_netloc:
            continue
        is_next = rel == "next" or text in {"suivant", "next", ">", "»"}
        is_page = bool(re.search(r"\bpage\b|\bpagination\b|\?page=\d+", _fold_text(parsed.path + parsed.query)))
        is_numbered = text.isdigit() and 1 < int(text) <= 20
        if not (is_next or is_page or is_numbered):
            continue
        clean_url = href.split("#", 1)[0]
        if clean_url and clean_url not in links:
            links.append(clean_url)
        if len(links) >= max_links:
            break
    return links


def _playwright_available() -> bool:
    """Check if Playwright is installed and browsers are available."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _scrape_with_playwright(
    url: str,
    village_id: str,
    max_results: int,
    *,
    center_lat: float,
    center_lng: float,
) -> list[ScrapedActivity]:
    """Scrape an OT website using Playwright (handles JS-rendered pages).

    Returns a list of ScrapedActivity discovered from the page.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

    activities: list[ScrapedActivity] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=_BROWSER_USER_AGENT,
            locale="fr-FR",
        )
        page = context.new_page()
        page.set_default_timeout(20_000)

        try:
            candidate_urls: list[str] = [url]
            for path_suffix in _PRICE_URL_PATTERNS:
                target = urljoin(url, path_suffix)
                if target not in candidate_urls:
                    candidate_urls.append(target)

            try:
                response = page.goto(url, wait_until="domcontentloaded")
                if response and response.status < 400:
                    for discovered in _discover_activity_links(page, url):
                        if discovered not in candidate_urls:
                            candidate_urls.append(discovered)
            except Exception:
                pass

            for target in candidate_urls[:32]:
                if len(activities) >= max_results:
                    break
                try:
                    response = page.goto(target, wait_until="domcontentloaded")
                    if not response or response.status >= 400:
                        continue
                    try:
                        page.wait_for_load_state("networkidle", timeout=3_000)
                    except Exception:
                        pass

                    remaining = max_results - len(activities)
                    batch = _extract_activities_from_schema(
                        page, target, village_id, remaining, center_lat, center_lng
                    )
                    batch.extend(_extract_activities_from_page(
                        page, target, village_id, remaining, center_lat, center_lng
                    ))
                    if batch:
                        activities.extend(batch)
                        activities = deduplicate_candidates(activities)
                        _enrich_activities_from_detail_pages(
                            page,
                            activities,
                            url,
                            center_lat,
                            center_lng,
                            max_enrich=min(remaining, 30),
                        )
                        for paginated in _discover_pagination_links(page, target):
                            if paginated not in candidate_urls:
                                candidate_urls.append(paginated)
                    time.sleep(0.2)
                except PlaywrightTimeout:
                    logger.debug("ot_local playwright timeout url=%s", target)
                    continue
                except Exception as exc:
                    logger.debug("ot_local playwright page error url=%s err=%s", target, exc)
                    continue

        finally:
            context.close()
            browser.close()

    return deduplicate_candidates(activities)[:max_results]


def _extract_activities_from_page(
    page,
    url: str,
    village_id: str,
    max_results: int,
    center_lat: float,
    center_lng: float,
) -> list[ScrapedActivity]:
    """Extract activity listings from the currently loaded Playwright page."""
    activities: list[ScrapedActivity] = []

    # Try structured selectors first
    for selector in _ACTIVITY_SELECTORS:
        try:
            elements = page.query_selector_all(selector)
            if elements:
                limit = min(len(elements), max_results)
                for el in elements[:limit]:
                    try:
                        text = el.inner_text() or ""
                        if len(text) < 10:
                            continue

                        # Try to get link
                        link_el = el.query_selector("a[href]")
                        href = link_el.get_attribute("href") if link_el else None
                        source_url = urljoin(url, href) if href else url

                        nom = _extract_name_from_element(el, text)
                        if not _looks_like_activity_name(nom):
                            continue

                        type_hint, emoji = _detect_type(text)
                        price_adult, price_child = _extract_price(text)
                        rating, review_count = _extract_rating(text)
                        saisons = _extract_saisons(text)
                        coords = _extract_coords_from_element(el)
                        latitude, longitude = coords or (center_lat, center_lng)

                        source_id = f"ot:{village_id}:{_stable_id(source_url, nom)}"

                        activity = ScrapedActivity(
                            source="ot_local",
                            source_id=source_id,
                            source_url=source_url,
                            nom=nom[:128],
                            type_hint=type_hint,
                            type_emoji=emoji,
                            latitude=latitude,
                            longitude=longitude,
                            price_adult=price_adult,
                            price_child=price_child,
                            rating=rating,
                            review_count=review_count,
                            description=text[:512],
                            saisons=saisons,
                        )
                        _set_best_distance(activity, text, center_lat, center_lng)
                        activities.append(activity)
                    except Exception:
                        continue

                if activities:
                    break
        except Exception:
            continue

    # Fallback: extract h2/h3 headings that look like activity names
    if not activities:
        try:
            headings = page.query_selector_all("h2, h3")
            for heading in headings[:max_results * 2]:
                try:
                    nom = heading.inner_text().strip()
                    if not _looks_like_activity_name(nom):
                        continue
                    type_hint, emoji = _detect_type(nom)
                    if type_hint == "tourist_attraction" and not any(
                        _fold_text(kw) in _fold_text(nom) for kw in _ACTIVITY_KEYWORDS
                    ):
                        continue

                    parent_text = ""
                    try:
                        parent_text = heading.evaluate(
                            "el => el.parentElement?.innerText || ''"
                        )
                    except Exception:
                        pass
                    price_adult, price_child = _extract_price(parent_text)
                    rating, review_count = _extract_rating(parent_text)
                    coords = _extract_coords_from_text(parent_text)
                    latitude, longitude = coords or (center_lat, center_lng)

                    # Try to resolve a detail page link from the heading or its surroundings
                    link_href = None
                    try:
                        link_href = heading.evaluate(
                            "el => el.tagName.toLowerCase() === 'a' ? el.getAttribute('href') : ("
                            "el.querySelector('a[href]')?.getAttribute('href') || "
                            "el.closest('a')?.getAttribute('href') || "
                            "el.parentElement?.querySelector('a[href]')?.getAttribute('href') || '')"
                        )
                    except Exception:
                        pass

                    source_url = urljoin(url, link_href) if link_href else url
                    source_id = f"ot:{village_id}:{_stable_id(source_url, nom)}"

                    activity = ScrapedActivity(
                        source="ot_local",
                        source_id=source_id,
                        source_url=source_url,
                        nom=nom[:128],
                        type_hint=type_hint,
                        type_emoji=emoji,
                        latitude=latitude,
                        longitude=longitude,
                        price_adult=price_adult,
                        price_child=price_child,
                        rating=rating,
                        review_count=review_count,
                        description=parent_text[:512],
                        saisons=_extract_saisons(parent_text),
                    )
                    _set_best_distance(activity, parent_text, center_lat, center_lng)
                    activities.append(activity)
                except Exception:
                    continue
        except Exception:
            pass

    return activities[:max_results]


def _enrich_activities_from_detail_pages(
    page,
    activities: list[ScrapedActivity],
    base_url: str,
    center_lat: float,
    center_lng: float,
    *,
    max_enrich: int = 30,
) -> None:
    """Open same-site detail URLs and fill prices, seasons, rating, coords."""
    base_netloc = urlparse(base_url).netloc
    seen: set[str] = set()

    for activity in activities:
        if len(seen) >= max_enrich:
            break
        detail_url = activity.source_url
        parsed = urlparse(detail_url)
        if not detail_url or parsed.netloc != base_netloc or detail_url in seen:
            continue
        if detail_url.rstrip("/") == base_url.rstrip("/"):
            continue

        seen.add(detail_url)
        try:
            response = page.goto(detail_url, wait_until="domcontentloaded")
            if not response or response.status >= 400:
                continue
            # Try main content selectors first to exclude global navigation/footer
            text = ""
            for sel in ["article", "main", "#content", ".content", ".entry-content", "[role='main']", ".main"]:
                try:
                    node = page.query_selector(sel)
                    if node:
                        sel_text = node.inner_text() or ""
                        if len(sel_text.strip()) > 200:
                            text = sel_text
                            break
                except Exception:
                    continue
            if not text:
                text = page.inner_text("body") or ""
        except Exception:
            continue

        price_adult, price_child = _extract_price(text)
        if price_adult is not None:
            activity.price_adult = price_adult
        if price_child is not None:
            activity.price_child = price_child

        rating, review_count = _extract_rating(text)
        json_rating, json_review_count = _extract_rating_from_json_ld(page)
        if rating is None:
            rating = json_rating
        if not review_count:
            review_count = json_review_count
        if rating is not None:
            activity.rating = rating
        if review_count:
            activity.review_count = review_count

        activity.saisons = _extract_saisons(text)
        if text:
            activity.description = text[:512]

        coords = _extract_coords_from_page(page)
        if coords:
            activity.latitude, activity.longitude = coords
        elif not activity.latitude or not activity.longitude:
            activity.latitude = center_lat
            activity.longitude = center_lng
        if text:
            _set_best_distance(activity, text, center_lat, center_lng)


class OfficeTourismeAdapter(ActivitySourceAdapter):
    """Scrapes local Office de Tourisme websites using Playwright.

    This adapter handles JS-rendered pages. When Playwright is not available
    (e.g. test environments without browser binaries), returns an empty list
    gracefully so the pipeline continues.

    Each village has a configured OT URL in VTF_OT_URLS. Additional URLs
    can be injected via the SCRAPER_OT_URLS_JSON env var (JSON dict).
    """

    source_name = "ot_local"

    def __init__(self) -> None:
        # Allow env override for additional OT URLs
        self._ot_urls: dict[str, str] = dict(VTF_OT_URLS)
        extra_json = os.environ.get("SCRAPER_OT_URLS_JSON", "")
        if extra_json:
            try:
                import json
                self._ot_urls.update(json.loads(extra_json))
            except Exception:
                pass

    # ─── Public interface ──────────────────────────────────────────────────

    def search_near(
        self,
        *,
        lat: float,
        lng: float,
        radius_km: int,
        max_results: int,
        village_id: str = "",
    ) -> list[ScrapedActivity]:
        """For OT local we use the village_id to look up the OT URL."""
        ot_url = self._ot_urls.get(village_id, "")
        if not ot_url:
            logger.debug(
                "ot_local: no OT URL configured for village_id=%s", village_id
            )
            return []

        if not _playwright_available():
            logger.warning(
                "ot_local: playwright not available — install with: "
                "pip install playwright && playwright install chromium"
            )
            return []

        try:
            return _scrape_with_playwright(
                ot_url,
                village_id,
                max_results,
                center_lat=lat,
                center_lng=lng,
            )
        except Exception as exc:
            logger.warning(
                "ot_local search_near village=%s url=%s error=%s",
                village_id,
                ot_url,
                exc,
            )
            return []

    def get_details(self, source_id: str) -> ScrapedActivity | None:
        """OT local scraper doesn't support detail lookups by ID."""
        return None

    def get_ot_url(self, village_id: str) -> str | None:
        """Return the configured OT URL for a village, or None."""
        return self._ot_urls.get(village_id)
