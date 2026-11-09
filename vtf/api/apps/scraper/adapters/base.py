"""Base adapter contract for all scraping sources (Phase 3). 

Spec §5.2 — ActivitySourceAdapter ABC.
Every source (Google Places, TripAdvisor, OT local) implements this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ScrapedActivity:
    """Normalised activity row returned by any source adapter."""

    source: str
    source_id: str
    source_url: str
    nom: str
    type_hint: str        # "museum" | "sport" | "nature" | "park" | "beach" | etc.
    type_emoji: str       # 🏄 🎭 🏔️ etc.
    latitude: float
    longitude: float
    price_adult: int | None = None
    price_child: int | None = None
    distance_km: float | None = None
    rating: float | None = None
    review_count: int = 0
    description: str = ""
    image_url: str | None = None
    saisons: list[str] = field(default_factory=lambda: ["hs", "vs", "ete", "fetes"])


# Mapping of Google/TripAdvisor type strings → emoji used in our catalog
TYPE_EMOJI_MAP: dict[str, str] = {
    "museum": "🏛️",
    "aquarium": "🐠",
    "zoo": "🦁",
    "amusement_park": "🎡",
    "theme_park": "🎢",
    "park": "🌳",
    "natural_feature": "🌿",
    "beach": "🏖️",
    "sport": "🏅",
    "surf": "🏄",
    "ski": "⛷️",
    "hiking": "🥾",
    "kayak": "🛶",
    "climbing": "🧗",
    "escape_game": "🔐",
    "market": "🛒",
    "church": "⛪",
    "castle": "🏰",
    "lighthouse": "🗼",
    "thermal": "♨️",
    "spa": "🧖",
    "cinema": "🎬",
    "theater": "🎭",
    "concert": "🎵",
    "paintball": "🎯",
    "karting": "🏎️",
    "bowling": "🎳",
    "golf": "⛳",
    "horse_riding": "🐴",
    "diving": "🤿",
    "boat": "⛵",
    "tourist_attraction": "📍",
    "default": "📍",
}


def type_hint_to_emoji(type_hint: str) -> str:
    """Map a type_hint string to its emoji representation."""
    return TYPE_EMOJI_MAP.get(type_hint.lower(), TYPE_EMOJI_MAP["default"])


class ActivitySourceAdapter(ABC):
    """Base class for all scraping adapters.

    Each adapter wraps one external data source (Google Places, TripAdvisor,
    local Office de Tourisme website). Implementations should handle rate
    limiting, retries, and error recovery internally and return an empty list
    on failure so the pipeline degrades gracefully.
    """

    source_name: str = "unknown"

    @abstractmethod
    def search_near(
        self,
        *,
        lat: float,
        lng: float,
        radius_km: int,
        max_results: int,
    ) -> list[ScrapedActivity]:
        """Search for activities near a geographic coordinate.

        Args:
            lat: Latitude of the centre point.
            lng: Longitude of the centre point.
            radius_km: Search radius in kilometres.
            max_results: Maximum number of results to return.

        Returns:
            List of normalised ScrapedActivity objects. Empty on failure.
        """

    @abstractmethod
    def get_details(self, source_id: str) -> ScrapedActivity | None:
        """Fetch full details for a specific activity by its source ID.

        Args:
            source_id: The platform-specific identifier.

        Returns:
            A ScrapedActivity with full details, or None if not found / error.
        """