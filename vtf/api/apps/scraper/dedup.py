"""Deduplication engine for scraped activities (Phase 3).

Spec §5.2 — Deduplication Strategy.
Activities are matched against the existing catalog using:
  1. Exact source_id match (previously scraped from same source)
  2. Fuzzy name match (RapidFuzz — distance < 3 / ratio > 0.85, normalised)
  3. Geo proximity (< 500m between coordinates)
  4. Type + price match (same category + within 20% price range)
"""
from __future__ import annotations

import logging
import math
import unicodedata

from apps.scraper.adapters.base import ScrapedActivity

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz as _fuzz

    def _fuzzy_ratio(a: str, b: str) -> float:
        return _fuzz.token_set_ratio(a, b) / 100.0

except ImportError:  # pragma: no cover
    # Fallback: simple character overlap
    def _fuzzy_ratio(a: str, b: str) -> float:  # type: ignore[misc]
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a, b).ratio()


def normalize_name(name: str) -> str:
    """Lowercase, strip accents, remove special chars for comparison."""
    nfkd = unicodedata.normalize("NFKD", name.lower())
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    return "".join(c for c in ascii_name if c.isalnum() or c.isspace()).strip()


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return great-circle distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def match_confidence(candidate: ScrapedActivity, existing) -> float:
    """Compute a 0–1 confidence that *candidate* matches *existing* Activity.

    Scoring dimensions (spec §5.2):
      Name similarity   → 0–0.40
      Geo proximity     → 0–0.30
      Price match       → 0–0.20
      Type match        → 0–0.10

    Args:
        candidate: Newly scraped activity.
        existing:  Existing catalog Activity ORM object (duck-typed).

    Returns:
        Float 0.0 (no match) to 1.0 (perfect match).
    """
    score = 0.0

    # 1. Name similarity (0–0.40)
    cand_norm = normalize_name(candidate.nom)
    exist_norm = normalize_name(getattr(existing, "nom", "") or "")
    if cand_norm and exist_norm:
        name_sim = _fuzzy_ratio(cand_norm, exist_norm)
        score += name_sim * 0.40

    # 2. Geo proximity (0–0.30)
    exist_lat = getattr(existing, "latitude", None)
    exist_lng = getattr(existing, "longitude", None)
    if (
        exist_lat is not None
        and exist_lng is not None
        and candidate.latitude
        and candidate.longitude
    ):
        dist = haversine_km(
            candidate.latitude, candidate.longitude,
            float(exist_lat), float(exist_lng),
        )
        # 0.30 at 0 km, 0 at 5 km
        score += max(0.0, 0.30 - dist * 0.06)

    # 3. Price match (0–0.20)
    cand_price = candidate.price_adult
    exist_price = getattr(existing, "price_adult", None)
    if cand_price and exist_price and cand_price > 0 and exist_price > 0:
        ratio = min(cand_price, exist_price) / max(cand_price, exist_price)
        score += ratio * 0.20

    # 4. Type match (0–0.10)
    cand_type = (candidate.type_hint or "").lower()
    exist_type = (getattr(existing, "type", "") or "").strip()
    if cand_type and exist_type and (cand_type in exist_type or exist_type in cand_type):
        score += 0.10

    return min(1.0, score)


def find_best_match(
    candidate: ScrapedActivity,
    existing_activities,
    *,
    threshold: float = 0.70,
) -> tuple[object | None, float]:
    """Find the best-matching existing Activity for *candidate*.

    Args:
        candidate:           The newly scraped activity.
        existing_activities: QuerySet or list of Activity ORM objects.
        threshold:           Minimum confidence to consider a match.

    Returns:
        Tuple of (best_match_activity | None, confidence_score).
    """
    best_match = None
    best_score = 0.0

    for existing in existing_activities:
        # Fast path: exact source_id match (same source only)
        codes = getattr(existing, "code", "") or ""
        if candidate.source_id and candidate.source_id in codes:
            return existing, 1.0

        score = match_confidence(candidate, existing)
        if score > best_score:
            best_score = score
            best_match = existing

    if best_score >= threshold:
        return best_match, best_score
    return None, best_score


def deduplicate_candidates(
    candidates: list[ScrapedActivity],
) -> list[ScrapedActivity]:
    """Remove duplicates within a scraped batch (cross-source dedup).

    Uses name similarity + geo proximity to collapse duplicates.
    Keeps the candidate with the highest review_count.

    Args:
        candidates: Raw list from multiple adapters.

    Returns:
        Deduplicated list with best representative per cluster.
    """
    if not candidates:
        return []

    def merge_activity(primary: ScrapedActivity, secondary: ScrapedActivity) -> ScrapedActivity:
        """Fill missing fields on the kept candidate from its duplicate."""
        for field in ("price_adult", "price_child", "rating", "image_url"):
            if getattr(primary, field) is None and getattr(secondary, field) is not None:
                setattr(primary, field, getattr(secondary, field))
        if not primary.review_count and secondary.review_count:
            primary.review_count = secondary.review_count
        if (not primary.description) and secondary.description:
            primary.description = secondary.description
        if (not primary.saisons or primary.saisons == ["hs", "vs", "ete", "fetes"]) and secondary.saisons:
            primary.saisons = secondary.saisons
        if (not primary.latitude or not primary.longitude) and secondary.latitude and secondary.longitude:
            primary.latitude = secondary.latitude
            primary.longitude = secondary.longitude
        return primary

    def preferred_activity(a: ScrapedActivity, b: ScrapedActivity) -> ScrapedActivity:
        def score(item: ScrapedActivity) -> tuple[int, int, int, int]:
            has_price = int(item.price_adult is not None or item.price_child is not None)
            has_rating = int(item.rating is not None)
            has_coords = int(bool(item.latitude and item.longitude))
            return (item.review_count, has_price, has_rating, has_coords)

        if score(b) > score(a):
            return merge_activity(b, a)
        return merge_activity(a, b)

    kept: list[ScrapedActivity] = []
    for cand in candidates:
        duplicate = False
        for existing in kept:
            if cand.source_id and cand.source_id == existing.source_id:
                replacement = preferred_activity(existing, cand)
                if replacement is not existing:
                    kept.remove(existing)
                    kept.append(replacement)
                duplicate = True
                break

            # Compare by name only (cross-source — no source_id match)
            name_sim = _fuzzy_ratio(
                normalize_name(cand.nom), normalize_name(existing.nom)
            )
            same_place = True
            if cand.latitude and cand.longitude and existing.latitude and existing.longitude:
                same_place = haversine_km(
                    cand.latitude,
                    cand.longitude,
                    existing.latitude,
                    existing.longitude,
                ) <= 1.0
            if name_sim >= 0.85 and same_place:
                replacement = preferred_activity(existing, cand)
                if replacement is not existing:
                    kept.remove(existing)
                    kept.append(replacement)
                duplicate = True
                break
        if not duplicate:
            kept.append(cand)

    return kept


def create_price_change_alerts(
    candidate: ScrapedActivity,
    existing,
    *,
    min_confidence: float = 0.90,
    confidence: float,
    alert_model=None,
) -> int:
    """Create pending PriceChangeAlert rows for catalog price deltas.

    Skips duplicate pending alerts for the same activity/field/new_value.
    Returns the number of alerts created.
    """
    if confidence < min_confidence:
        return 0

    if alert_model is None:
        from apps.scraper.models import PriceChangeAlert

        alert_model = PriceChangeAlert

    from django.utils import timezone as dj_timezone

    created = 0
    for change in detect_price_change(candidate, existing):
        already_pending = alert_model.objects.filter(
            activity=existing,
            field=change["field"],
            new_value=change["new_value"],
            status="pending",
        ).exists()
        if already_pending:
            continue
        alert_model.objects.create(
            activity=existing,
            field=change["field"],
            old_value=change["old_value"],
            new_value=change["new_value"],
            source=candidate.source,
            scraped_at=dj_timezone.now(),
            status="pending",
        )
        created += 1
    return created


def detect_price_change(
    candidate: ScrapedActivity,
    existing,
    *,
    threshold_pct: float = 0.10,
) -> list[dict]:
    """Return list of price change dicts if candidate prices differ > threshold.

    Args:
        candidate:      Freshly scraped activity.
        existing:       Existing catalog Activity ORM object.
        threshold_pct:  Fractional change to trigger an alert (default 10%).

    Returns:
        List of {"field": ..., "old_value": ..., "new_value": ...} dicts.
    """
    changes: list[dict] = []

    for field in ("price_adult", "price_child"):
        new_val = getattr(candidate, field, None)
        old_val = getattr(existing, field, None)
        if new_val is None or old_val is None:
            continue
        if old_val == 0:
            continue  # free activity — skip
        delta = abs(new_val - old_val) / old_val
        if delta > threshold_pct:
            changes.append({
                "field": field,
                "old_value": old_val,
                "new_value": new_val,
                "delta_pct": round(delta * 100, 1),
            })

    return changes
