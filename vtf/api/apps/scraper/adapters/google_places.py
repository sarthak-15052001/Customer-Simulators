"""Google Places API adapter (Phase 3).

Uses the Google Places API v1 (New) — Nearby Search + Place Details.
Falls back gracefully when the API key is not configured.

Spec §5.2 — GooglePlacesAdapter.
Playwright is used for any JS-rendered enrichment fallback (price extraction).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from apps.scraper.adapters.base import (
    ActivitySourceAdapter,
    ScrapedActivity,
    type_hint_to_emoji,
)

logger = logging.getLogger(__name__)

# Activity types we care about (Google Places types)
GOOGLE_PLACE_TYPES = [
    "tourist_attraction",
    "amusement_park",
    "aquarium",
    "art_gallery",
    "museum",
    "natural_feature",
    "park",
    "stadium",
    "zoo",
    "spa",
    "campground",
]

# Map Google place types → internal type_hint
GOOGLE_TYPE_MAP: dict[str, str] = {
    "tourist_attraction": "tourist_attraction",
    "amusement_park": "amusement_park",
    "aquarium": "aquarium",
    "art_gallery": "museum",
    "museum": "museum",
    "natural_feature": "natural_feature",
    "park": "park",
    "stadium": "sport",
    "zoo": "zoo",
    "spa": "spa",
    "campground": "park",
    "beach": "beach",
    "movie_theater": "cinema",
    "bowling_alley": "bowling",
    "casino": "default",
    "golf_course": "golf",
    "gym": "sport",
}

_GOOGLE_PLACES_API_BASE = "https://places.googleapis.com/v1"
_GOOGLE_PLACES_NEARBY = f"{_GOOGLE_PLACES_API_BASE}/places:searchNearby"
_GOOGLE_PLACES_DETAIL = f"{_GOOGLE_PLACES_API_BASE}/places/{{place_id}}"

# Fields to fetch — minimises cost
_NEARBY_FIELD_MASK = (
    "places.id,places.displayName,places.types,places.location,"
    "places.rating,places.userRatingCount,places.priceLevel,"
    "places.editorialSummary,places.websiteUri,places.photos,"
    "places.regularOpeningHours"
)

_DETAIL_FIELD_MASK = (
    "id,displayName,types,location,rating,userRatingCount,priceLevel,"
    "editorialSummary,websiteUri,photos,regularOpeningHours,accessibilityOptions"
)

# Price level → approximate adult ticket price (heuristic, EUR)
_PRICE_LEVEL_ADULT: dict[int, int] = {
    1: 8,
    2: 15,
    3: 25,
    4: 40,
}
_PRICE_LEVEL_CHILD_RATIO = 0.65  # child ≈ 65% of adult


class GooglePlacesAdapter(ActivitySourceAdapter):
    """Uses the Google Places API (New) v1 — Nearby Search + Place Details.

    When GOOGLE_PLACES_API_KEY is not set the adapter returns an empty list
    so the pipeline continues with other sources.
    """

    source_name = "google_places"

    def __init__(self) -> None:
        self.api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

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
                "google_places: GOOGLE_PLACES_API_KEY not set — skipping"
            )
            return []

        results: list[ScrapedActivity] = []
        for place_type in GOOGLE_PLACE_TYPES:
            if len(results) >= max_results:
                break
            try:
                batch = self._nearby_search(
                    lat=lat,
                    lng=lng,
                    radius_m=radius_km * 1000,
                    place_type=place_type,
                    max_results=max_results - len(results),
                )
                results.extend(batch)
                time.sleep(0.1)  # gentle rate limit
            except Exception as exc:
                logger.warning(
                    "google_places nearby_search type=%s error=%s",
                    place_type,
                    exc,
                )

        # Deduplicate by source_id within this batch
        seen: set[str] = set()
        unique: list[ScrapedActivity] = []
        for act in results:
            if act.source_id not in seen:
                seen.add(act.source_id)
                unique.append(act)

        return unique[:max_results]

    def get_details(self, source_id: str) -> ScrapedActivity | None:
        if not self.api_key:
            return None
        try:
            url = _GOOGLE_PLACES_DETAIL.format(place_id=source_id)
            resp = self._session.get(
                url,
                headers={
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": _DETAIL_FIELD_MASK,
                },
                timeout=10,
            )
            resp.raise_for_status()
            place = resp.json()
            return self._place_to_activity(place)
        except Exception as exc:
            logger.warning(
                "google_places get_details source_id=%s error=%s",
                source_id,
                exc,
            )
            return None

    # ─── Private helpers ───────────────────────────────────────────────────

    def _nearby_search(
        self,
        lat: float,
        lng: float,
        radius_m: int,
        place_type: str,
        max_results: int,
    ) -> list[ScrapedActivity]:
        payload: dict[str, Any] = {
            "includedTypes": [place_type],
            "maxResultCount": min(max_results, 20),
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius_m),
                }
            },
        }
        resp = self._session.post(
            _GOOGLE_PLACES_NEARBY,
            json=payload,
            headers={
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": _NEARBY_FIELD_MASK,
            },
            timeout=15,
        )
        resp.raise_for_status()
        places = resp.json().get("places", [])
        return [
            a
            for a in (self._place_to_activity(p) for p in places)
            if a is not None
        ]

    def _place_to_activity(self, place: dict) -> ScrapedActivity | None:
        try:
            place_id = place.get("id", "")
            if not place_id:
                return None

            display_name = place.get("displayName", {})
            nom = (
                display_name.get("text", "")
                if isinstance(display_name, dict)
                else str(display_name)
            )
            if not nom:
                return None

            types = place.get("types", [])
            type_hint = self._best_type(types)
            emoji = type_hint_to_emoji(type_hint)

            location = place.get("location", {})
            lat = location.get("latitude", 0.0)
            lng = location.get("longitude", 0.0)

            price_level = place.get("priceLevel")
            price_adult: int | None = None
            price_child: int | None = None
            if (
                isinstance(price_level, int)
                and price_level in _PRICE_LEVEL_ADULT
            ):
                price_adult = _PRICE_LEVEL_ADULT[price_level]
                price_child = int(price_adult * _PRICE_LEVEL_CHILD_RATIO)

            summary = place.get("editorialSummary", {})
            description = (
                summary.get("text", "")
                if isinstance(summary, dict)
                else ""
            )

            photos = place.get("photos", [])
            image_url: str | None = None
            if photos and self.api_key:
                photo_name = photos[0].get("name", "")
                if photo_name:
                    image_url = (
                        f"https://places.googleapis.com/v1/{photo_name}/media"
                        f"?maxHeightPx=400&key={self.api_key}"
                    )

            website = place.get("websiteUri", "")
            source_url = (
                website
                or f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            )

            return ScrapedActivity(
                source=self.source_name,
                source_id=place_id,
                source_url=source_url,
                nom=nom,
                type_hint=type_hint,
                type_emoji=emoji,
                latitude=lat,
                longitude=lng,
                price_adult=price_adult,
                price_child=price_child,
                rating=place.get("rating"),
                review_count=place.get("userRatingCount", 0) or 0,
                description=description,
                image_url=image_url,
            )
        except Exception as exc:
            logger.debug(
                "google_places _place_to_activity error=%s",
                exc,
            )
            return None

    @staticmethod
    def _best_type(types: list[str]) -> str:
        """Pick the most descriptive type from the list."""
        for t in types:
            if (
                t in GOOGLE_TYPE_MAP
                and t not in ("point_of_interest", "establishment", "tourist_attraction")
            ):
                return GOOGLE_TYPE_MAP[t]
        if "tourist_attraction" in types:
            return "tourist_attraction"
        return "tourist_attraction"