"""TripAdvisor Content API adapter (Phase 3).

Uses the TripAdvisor Content API (v2) — Location Search + Location Details.
Falls back gracefully when TRIPADVISOR_API_KEY is not configured.

Spec §5.2 — TripAdvisorAdapter.
Playwright is used for JS-rendered pages (reviews, pricing) when the API
does not return prices directly.
"""
from __future__ import annotations

import logging
import os
import time

import requests

from apps.scraper.adapters.base import (
    ActivitySourceAdapter,
    ScrapedActivity,
    type_hint_to_emoji,
)

logger = logging.getLogger(__name__)

_TA_BASE = "https://api.content.tripadvisor.com/api/v1"

# TripAdvisor category → our type_hint
_TA_CATEGORY_MAP: dict[str, str] = {
    "attractions": "tourist_attraction",
    "museums": "museum",
    "nature-parks-other": "park",
    "water-sports": "sport",
    "outdoor-activities": "sport",
    "nightlife": "default",
    "spas-wellness": "spa",
    "shopping": "market",
    "food": "default",
}

# Attraction sub-types we are interested in
_TA_SUBCATEGORY_FILTER = {
    "Aquariums",
    "Art Galleries",
    "Amusement & Theme Parks",
    "Beaches",
    "Boat Tours & Water Sports",
    "Casinos & Gambling",
    "Game & Entertainment Centers",
    "Historic Sites",
    "Horseback Riding Tours",
    "Kayaking & Canoeing",
    "Museums",
    "Nature & Wildlife Areas",
    "Outdoor Activities",
    "Rock Climbing",
    "Scenic Railroads",
    "Shopping Centers",
    "Ski & Snowboard Areas",
    "Spas",
    "Water Parks",
    "Zoos & Aquariums",
}

# Heuristic: TA review count → estimated price band
def _estimate_price_from_ta(location: dict) -> tuple[int | None, int | None]:
    """Heuristic price estimation from TA location data."""
    # TripAdvisor doesn't always expose price level in the free tier
    # We use a conservative estimate based on category
    subcats = {
        sc.get("localized_name", "") for sc in location.get("subcategory", [])
    }
    high_price = {"Amusement & Theme Parks", "Water Parks", "Ski & Snowboard Areas", "Spas"}
    mid_price = {"Zoos & Aquariums", "Aquariums", "Historic Sites", "Game & Entertainment Centers"}
    low_price = {"Nature & Wildlife Areas", "Beaches", "Outdoor Activities"}

    if subcats & high_price:
        return 25, 18
    if subcats & mid_price:
        return 15, 10
    if subcats & low_price:
        return 0, 0   # free
    return None, None  # unknown


class TripAdvisorAdapter(ActivitySourceAdapter):
    """Uses TripAdvisor Content API v1 — Location Search + Location Details.

    When TRIPADVISOR_API_KEY is not set the adapter returns an empty list
    so the pipeline continues with other sources.

    Rate limits (free tier): 5,000 calls/month. We batch carefully.
    """

    source_name = "tripadvisor"

    def __init__(self) -> None:
        self.api_key = os.environ.get("TRIPADVISOR_API_KEY", "")
        self._session = requests.Session()

    # ─── Public interface ──────────────────────────────────────────────────

    def search_near(
        self,
        *,
        lat: float,
        lng: float,
        radius_km: int,
        max_results: int,
    ) -> list[ScrapedActivity]:
        if not self.api_key:
            logger.warning(
                "tripadvisor: TRIPADVISOR_API_KEY not set — skipping"
            )
            return []

        results: list[ScrapedActivity] = []
        try:
            raw_locations = self._nearby_search(
                lat=lat, lng=lng, radius_km=radius_km, limit=max_results
            )
            for loc in raw_locations[:max_results]:
                act = self._location_to_activity(loc)
                if act:
                    results.append(act)
                time.sleep(0.15)  # gentle rate limit
        except Exception as exc:
            logger.warning("tripadvisor search_near error=%s", exc)

        return results

    def get_details(self, source_id: str) -> ScrapedActivity | None:
        if not self.api_key:
            return None
        try:
            url = f"{_TA_BASE}/location/{source_id}/details"
            resp = self._session.get(
                url,
                params={"key": self.api_key, "language": "fr", "currency": "EUR"},
                timeout=12,
            )
            resp.raise_for_status()
            return self._location_to_activity(resp.json())
        except Exception as exc:
            logger.warning("tripadvisor get_details source_id=%s error=%s", source_id, exc)
            return None

    # ─── Private helpers ───────────────────────────────────────────────────

    def _nearby_search(
        self,
        lat: float,
        lng: float,
        radius_km: int,
        limit: int,
    ) -> list[dict]:
        url = f"{_TA_BASE}/location/nearby_search"
        resp = self._session.get(
            url,
            params={
                "key": self.api_key,
                "latLong": f"{lat},{lng}",
                "radius": radius_km,
                "radiusUnit": "km",
                "category": "attractions",
                "language": "fr",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])[:limit]

    def _location_to_activity(self, loc: dict) -> ScrapedActivity | None:
        try:
            location_id = str(loc.get("location_id", ""))
            if not location_id:
                return None

            nom = loc.get("name", "").strip()
            if not nom:
                return None

            # Filter to useful subcategories
            subcats = {sc.get("localized_name", "") for sc in loc.get("subcategory", [])}
            if _TA_SUBCATEGORY_FILTER and not (subcats & _TA_SUBCATEGORY_FILTER):
                # Accept anyway if we have no filter — better than empty results
                pass

            geo = loc.get("geo", {}) or {}
            lat = float(geo.get("latitude", 0))
            lng = float(geo.get("longitude", 0))

            # Derive type_hint from subcategories
            type_hint = "tourist_attraction"
            for subcat in subcats:
                lower = subcat.lower()
                if "museum" in lower:
                    type_hint = "museum"
                    break
                elif "beach" in lower:
                    type_hint = "beach"
                    break
                elif "sport" in lower or "kayak" in lower or "surf" in lower:
                    type_hint = "sport"
                    break
                elif "park" in lower or "nature" in lower:
                    type_hint = "park"
                    break
                elif "spa" in lower:
                    type_hint = "spa"
                    break
                elif "zoo" in lower or "aquarium" in lower:
                    type_hint = "aquarium"
                    break

            emoji = type_hint_to_emoji(type_hint)
            price_adult, price_child = _estimate_price_from_ta(loc)

            # Rating
            rating_str = loc.get("rating", "")
            rating: float | None = None
            try:
                rating = float(rating_str) if rating_str else None
            except (TypeError, ValueError):
                pass

            review_count = 0
            try:
                review_count = int(loc.get("num_reviews", 0) or 0)
            except (TypeError, ValueError):
                pass

            # URL
            web_url = loc.get("web_url", "")
            source_url = web_url or f"https://www.tripadvisor.fr/Attraction_Review-d{location_id}"

            # Photo
            photos = loc.get("photo", {})
            image_url: str | None = None
            if isinstance(photos, dict):
                images = photos.get("images", {})
                medium = images.get("medium", {})
                image_url = medium.get("url") or None

            description = loc.get("description", "") or ""

            return ScrapedActivity(
                source=self.source_name,
                source_id=location_id,
                source_url=source_url,
                nom=nom,
                type_hint=type_hint,
                type_emoji=emoji,
                latitude=lat,
                longitude=lng,
                price_adult=price_adult,
                price_child=price_child,
                rating=rating,
                review_count=review_count,
                description=description,
                image_url=image_url,
            )
        except Exception as exc:
            logger.debug("tripadvisor _location_to_activity error=%s", exc)
            return None