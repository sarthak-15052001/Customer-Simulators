"""Adapter tests for Phase 3 scraping (Google Places, TripAdvisor, OT Local).

Coverage:
  - GooglePlacesAdapter: no-key fallback, search_near, get_details, _place_to_activity,
    _best_type, price-level mapping, dedup within batch
  - TripAdvisorAdapter: no-key fallback, search_near, get_details,
    _location_to_activity, price estimation heuristic, error handling
  - OfficeTourismeAdapter: no-url / no-playwright fallback, search_near
  - base.py: type_hint_to_emoji, ScrapedActivity dataclass defaults,
    ActivitySourceAdapter ABC contract

Run:
  pytest tests/test_adapters.py -v
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.scraper.adapters.base import (
    ActivitySourceAdapter,
    ScrapedActivity,
    TYPE_EMOJI_MAP,
    type_hint_to_emoji,
)
from apps.scraper.adapters.google_places import (
    GooglePlacesAdapter,
    GOOGLE_PLACE_TYPES,
    GOOGLE_TYPE_MAP,
    _PRICE_LEVEL_ADULT,
    _PRICE_LEVEL_CHILD_RATIO,
)
from apps.scraper.adapters.tripadvisor import (
    TripAdvisorAdapter,
    _estimate_price_from_ta,
)
from apps.scraper.adapters.ot_local import (
    OfficeTourismeAdapter,
    _extract_distance_km,
    _extract_price,
    _extract_rating,
    _extract_saisons,
    _schema_node_to_activity,
    _looks_like_activity_name,
)
from apps.scraper.services.ot_urls import VTF_OT_URLS


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_google_place(
    place_id="abc123",
    name="Aquarium de Biarritz",
    types=None,
    lat=43.48,
    lng=-1.55,
    price_level=None,
    rating=4.3,
    user_rating_count=1800,
    website="https://aquarium-biarritz.com",
    editorial="Incroyable aquarium.",
    photos=None,
):
    place = {
        "id": place_id,
        "displayName": {"text": name},
        "types": types or ["aquarium", "tourist_attraction"],
        "location": {"latitude": lat, "longitude": lng},
        "rating": rating,
        "userRatingCount": user_rating_count,
        "websiteUri": website,
        "editorialSummary": {"text": editorial},
        "photos": photos or [],
    }
    if price_level is not None:
        place["priceLevel"] = price_level
    return place


def _make_ta_location(
    location_id="9876",
    name="Surf School Anglet",
    subcategory=None,
    lat="43.48",
    lng="-1.55",
    rating="4.7",
    num_reviews=600,
    web_url="https://tripadvisor.fr/Attraction_Review-d9876",
):
    return {
        "location_id": location_id,
        "name": name,
        "subcategory": subcategory or [{"localized_name": "Outdoor Activities"}],
        "geo": {"latitude": lat, "longitude": lng},
        "rating": rating,
        "num_reviews": num_reviews,
        "web_url": web_url,
        "description": "Great surf school.",
        "photo": {},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Base adapter: ScrapedActivity + type_hint_to_emoji
# ─────────────────────────────────────────────────────────────────────────────


class TestScrapedActivityDefaults:
    def test_required_fields_set(self):
        act = ScrapedActivity(
            source="google_places",
            source_id="x1",
            source_url="https://example.com",
            nom="Musée Basque",
            type_hint="museum",
            type_emoji="🏛️",
            latitude=43.48,
            longitude=-1.55,
        )
        assert act.source == "google_places"
        assert act.price_adult is None
        assert act.price_child is None
        assert act.rating is None
        assert act.review_count == 0
        assert act.description == ""
        assert act.image_url is None
        # Default seasons: all four
        assert act.saisons == ["hs", "vs", "ete", "fetes"]

    def test_saisons_default_is_independent_per_instance(self):
        a = ScrapedActivity(source="s", source_id="1", source_url="u", nom="A",
                            type_hint="park", type_emoji="🌳", latitude=0.0, longitude=0.0)
        b = ScrapedActivity(source="s", source_id="2", source_url="u", nom="B",
                            type_hint="park", type_emoji="🌳", latitude=0.0, longitude=0.0)
        a.saisons.append("extra")
        assert "extra" not in b.saisons


class TestTypeHintToEmoji:
    def test_known_type_returns_correct_emoji(self):
        assert type_hint_to_emoji("museum") == "🏛️"
        assert type_hint_to_emoji("beach") == "🏖️"
        assert type_hint_to_emoji("aquarium") == "🐠"
        assert type_hint_to_emoji("sport") == "🏅"
        assert type_hint_to_emoji("ski") == "⛷️"

    def test_unknown_type_returns_default_pin(self):
        assert type_hint_to_emoji("unicorn") == "📍"
        assert type_hint_to_emoji("") == "📍"

    def test_case_insensitive(self):
        assert type_hint_to_emoji("Museum") == type_hint_to_emoji("museum")
        assert type_hint_to_emoji("BEACH") == type_hint_to_emoji("beach")

    def test_all_map_keys_resolve(self):
        for key in TYPE_EMOJI_MAP:
            assert type_hint_to_emoji(key) != ""


class TestActivitySourceAdapterABC:
    """ActivitySourceAdapter cannot be instantiated directly."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            ActivitySourceAdapter()  # type: ignore[abstract]

    def test_subclass_must_implement_search_near_and_get_details(self):
        class PartialAdapter(ActivitySourceAdapter):
            source_name = "partial"
            # missing search_near and get_details

        with pytest.raises(TypeError):
            PartialAdapter()  # type: ignore[abstract]

    def test_valid_subclass_works(self):
        class MinimalAdapter(ActivitySourceAdapter):
            source_name = "minimal"

            def search_near(self, *, lat, lng, radius_km, max_results):
                return []

            def get_details(self, source_id):
                return None

        adapter = MinimalAdapter()
        assert adapter.search_near(lat=0, lng=0, radius_km=10, max_results=5) == []
        assert adapter.get_details("x") is None


# ─────────────────────────────────────────────────────────────────────────────
# GooglePlacesAdapter
# ─────────────────────────────────────────────────────────────────────────────


class TestGooglePlacesAdapterNoKey:
    """When GOOGLE_PLACES_API_KEY is absent the adapter must degrade silently."""

    def setup_method(self):
        with patch.dict("os.environ", {}, clear=True):
            # Ensure key is not set
            import os
            os.environ.pop("GOOGLE_PLACES_API_KEY", None)
        self.adapter = GooglePlacesAdapter()
        self.adapter.api_key = ""  # force empty

    def test_search_near_returns_empty_list(self):
        result = self.adapter.search_near(lat=43.48, lng=-1.55, radius_km=30, max_results=20)
        assert result == []

    def test_get_details_returns_none(self):
        result = self.adapter.get_details("ChIJabc123")
        assert result is None

    def test_search_near_does_not_raise(self):
        # Must never propagate an exception even if called repeatedly
        for _ in range(3):
            assert self.adapter.search_near(lat=0, lng=0, radius_km=5, max_results=5) == []


class TestGooglePlacesAdapterPlaceToActivity:
    """Unit-test _place_to_activity parsing without network."""

    def setup_method(self):
        self.adapter = GooglePlacesAdapter()
        self.adapter.api_key = "fake-key"

    def test_valid_place_produces_scraped_activity(self):
        place = _make_google_place(price_level=2)
        result = self.adapter._place_to_activity(place)
        assert result is not None
        assert result.source == "google_places"
        assert result.source_id == "abc123"
        assert result.nom == "Aquarium de Biarritz"
        assert result.latitude == pytest.approx(43.48)
        assert result.longitude == pytest.approx(-1.55)
        assert result.rating == pytest.approx(4.3)
        assert result.review_count == 1800

    def test_price_level_1_maps_to_8_euros(self):
        place = _make_google_place(price_level=1)
        result = self.adapter._place_to_activity(place)
        assert result.price_adult == _PRICE_LEVEL_ADULT[1]
        assert result.price_child == int(_PRICE_LEVEL_ADULT[1] * _PRICE_LEVEL_CHILD_RATIO)

    def test_price_level_4_maps_to_40_euros(self):
        place = _make_google_place(price_level=4)
        result = self.adapter._place_to_activity(place)
        assert result.price_adult == _PRICE_LEVEL_ADULT[4]

    def test_no_price_level_yields_none_prices(self):
        place = _make_google_place()  # no price_level
        result = self.adapter._place_to_activity(place)
        assert result is not None
        assert result.price_adult is None
        assert result.price_child is None

    def test_missing_place_id_returns_none(self):
        place = _make_google_place()
        place.pop("id")
        assert self.adapter._place_to_activity(place) is None

    def test_empty_display_name_returns_none(self):
        place = _make_google_place()
        place["displayName"] = {"text": ""}
        assert self.adapter._place_to_activity(place) is None

    def test_website_used_as_source_url(self):
        place = _make_google_place(website="https://my-site.fr")
        result = self.adapter._place_to_activity(place)
        assert result.source_url == "https://my-site.fr"

    def test_fallback_source_url_when_no_website(self):
        place = _make_google_place(website="")
        place.pop("websiteUri", None)
        result = self.adapter._place_to_activity(place)
        assert "google.com/maps" in result.source_url

    def test_editorial_summary_used_as_description(self):
        place = _make_google_place()
        result = self.adapter._place_to_activity(place)
        assert result.description == "Incroyable aquarium."

    def test_photo_url_built_when_key_present(self):
        place = _make_google_place(photos=[{"name": "places/abc/photos/xyz"}])
        result = self.adapter._place_to_activity(place)
        assert result.image_url is not None
        assert "places.googleapis.com" in result.image_url
        assert "fake-key" in result.image_url

    def test_corrupt_place_data_returns_none_gracefully(self):
        # Should not raise; returns None
        result = self.adapter._place_to_activity({"completely": "wrong"})
        assert result is None


class TestGooglePlacesBestType:
    def test_aquarium_preferred_over_tourist_attraction(self):
        result = GooglePlacesAdapter._best_type(["tourist_attraction", "aquarium", "establishment"])
        assert result == "aquarium"

    def test_unknown_types_fall_back_to_tourist_attraction(self):
        result = GooglePlacesAdapter._best_type(["establishment", "point_of_interest"])
        assert result == "tourist_attraction"

    def test_museum_type_recognized(self):
        result = GooglePlacesAdapter._best_type(["museum"])
        assert result == "museum"

    def test_empty_list_returns_tourist_attraction(self):
        result = GooglePlacesAdapter._best_type([])
        assert result == "tourist_attraction"


class TestGooglePlacesSearchNear:
    """search_near with mocked HTTP."""

    def setup_method(self):
        self.adapter = GooglePlacesAdapter()
        self.adapter.api_key = "fake-key"

    def _mock_nearby_response(self, places):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"places": places}
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    def test_search_near_returns_scraped_activities(self):
        place = _make_google_place(price_level=2)
        with patch.object(self.adapter._session, "post", return_value=self._mock_nearby_response([place])):
            results = self.adapter.search_near(lat=43.48, lng=-1.55, radius_km=30, max_results=20)
        assert len(results) >= 1
        assert results[0].nom == "Aquarium de Biarritz"

    def test_search_near_deduplicates_by_source_id(self):
        # Same place_id returned from two different type queries
        place = _make_google_place(place_id="SAME_ID", price_level=2)
        with patch.object(self.adapter._session, "post", return_value=self._mock_nearby_response([place])):
            results = self.adapter.search_near(lat=43.48, lng=-1.55, radius_km=5, max_results=5)
        ids = [r.source_id for r in results]
        assert len(ids) == len(set(ids)), "Duplicate source_id found in results"

    def test_search_near_respects_max_results(self):
        places = [_make_google_place(place_id=f"id{i}", name=f"Place {i}") for i in range(15)]
        with patch.object(self.adapter._session, "post", return_value=self._mock_nearby_response(places)):
            results = self.adapter.search_near(lat=43.48, lng=-1.55, radius_km=30, max_results=5)
        assert len(results) <= 5

    def test_search_near_handles_http_error_gracefully(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 429")
        with patch.object(self.adapter._session, "post", return_value=mock_resp):
            # Should not raise; returns partial results
            results = self.adapter.search_near(lat=43.48, lng=-1.55, radius_km=30, max_results=20)
        assert isinstance(results, list)

    def test_search_near_returns_empty_on_empty_api_response(self):
        with patch.object(self.adapter._session, "post", return_value=self._mock_nearby_response([])):
            results = self.adapter.search_near(lat=43.48, lng=-1.55, radius_km=30, max_results=20)
        assert results == []


class TestGooglePlacesGetDetails:
    def setup_method(self):
        self.adapter = GooglePlacesAdapter()
        self.adapter.api_key = "fake-key"

    def test_get_details_returns_activity(self):
        place = _make_google_place(price_level=3)
        mock_resp = MagicMock()
        mock_resp.json.return_value = place
        mock_resp.raise_for_status.return_value = None
        with patch.object(self.adapter._session, "get", return_value=mock_resp):
            result = self.adapter.get_details("abc123")
        assert result is not None
        assert result.source_id == "abc123"

    def test_get_details_returns_none_on_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500")
        with patch.object(self.adapter._session, "get", return_value=mock_resp):
            result = self.adapter.get_details("bad-id")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# TripAdvisorAdapter
# ─────────────────────────────────────────────────────────────────────────────


class TestTripAdvisorAdapterNoKey:
    def setup_method(self):
        self.adapter = TripAdvisorAdapter()
        self.adapter.api_key = ""

    def test_search_near_returns_empty(self):
        assert self.adapter.search_near(lat=43.48, lng=-1.55, radius_km=30, max_results=20) == []

    def test_get_details_returns_none(self):
        assert self.adapter.get_details("9876") is None

    def test_search_near_does_not_raise(self):
        for _ in range(3):
            assert self.adapter.search_near(lat=0, lng=0, radius_km=5, max_results=5) == []


class TestTripAdvisorPriceEstimation:
    def test_high_price_category(self):
        loc = {"subcategory": [{"localized_name": "Amusement & Theme Parks"}]}
        adult, child = _estimate_price_from_ta(loc)
        assert adult == 25
        assert child == 18

    def test_mid_price_category(self):
        loc = {"subcategory": [{"localized_name": "Aquariums"}]}
        adult, child = _estimate_price_from_ta(loc)
        assert adult == 15
        assert child == 10

    def test_low_price_category_is_free(self):
        loc = {"subcategory": [{"localized_name": "Beaches"}]}
        adult, child = _estimate_price_from_ta(loc)
        assert adult == 0
        assert child == 0

    def test_unknown_category_returns_none(self):
        loc = {"subcategory": [{"localized_name": "Shopping Centers"}]}
        adult, child = _estimate_price_from_ta(loc)
        assert adult is None
        assert child is None

    def test_empty_subcategory(self):
        loc = {"subcategory": []}
        adult, child = _estimate_price_from_ta(loc)
        assert adult is None
        assert child is None


class TestTripAdvisorLocationToActivity:
    def setup_method(self):
        self.adapter = TripAdvisorAdapter()
        self.adapter.api_key = "fake-ta-key"

    def test_valid_location_produces_activity(self):
        loc = _make_ta_location()
        result = self.adapter._location_to_activity(loc)
        assert result is not None
        assert result.source == "tripadvisor"
        assert result.source_id == "9876"
        assert result.nom == "Surf School Anglet"
        assert result.rating == pytest.approx(4.7)
        assert result.review_count == 600

    def test_missing_location_id_returns_none(self):
        loc = _make_ta_location()
        loc.pop("location_id")
        assert self.adapter._location_to_activity(loc) is None

    def test_empty_name_returns_none(self):
        loc = _make_ta_location(name="")
        assert self.adapter._location_to_activity(loc) is None

    def test_type_hint_museum_detected(self):
        loc = _make_ta_location(subcategory=[{"localized_name": "Museums"}])
        result = self.adapter._location_to_activity(loc)
        assert result.type_hint == "museum"

    def test_type_hint_beach_detected(self):
        loc = _make_ta_location(subcategory=[{"localized_name": "Beaches"}])
        result = self.adapter._location_to_activity(loc)
        assert result.type_hint == "beach"

    def test_type_hint_sport_detected(self):
        loc = _make_ta_location(subcategory=[{"localized_name": "Kayaking & Canoeing"}])
        result = self.adapter._location_to_activity(loc)
        assert result.type_hint == "sport"

    def test_source_url_falls_back_to_tripadvisor_pattern(self):
        loc = _make_ta_location(web_url="")
        loc.pop("web_url", None)
        result = self.adapter._location_to_activity(loc)
        assert result is not None
        assert "tripadvisor" in result.source_url

    def test_invalid_rating_handled_gracefully(self):
        loc = _make_ta_location(rating="not-a-number")
        result = self.adapter._location_to_activity(loc)
        assert result is not None
        assert result.rating is None

    def test_corrupt_data_returns_none(self):
        result = self.adapter._location_to_activity({})
        assert result is None

    def test_coordinates_parsed_from_strings(self):
        loc = _make_ta_location(lat="43.48", lng="-1.55")
        result = self.adapter._location_to_activity(loc)
        assert result is not None
        assert result.latitude == pytest.approx(43.48)
        assert result.longitude == pytest.approx(-1.55)


class TestTripAdvisorSearchNear:
    def setup_method(self):
        self.adapter = TripAdvisorAdapter()
        self.adapter.api_key = "fake-ta-key"

    def _mock_search_response(self, locations):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": locations}
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    def test_search_near_returns_activities(self):
        loc = _make_ta_location()
        with patch.object(self.adapter._session, "get", return_value=self._mock_search_response([loc])):
            results = self.adapter.search_near(lat=43.48, lng=-1.55, radius_km=30, max_results=10)
        assert len(results) == 1
        assert results[0].nom == "Surf School Anglet"

    def test_search_near_handles_api_error_gracefully(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 500")
        with patch.object(self.adapter._session, "get", return_value=mock_resp):
            results = self.adapter.search_near(lat=43.48, lng=-1.55, radius_km=30, max_results=10)
        assert results == []

    def test_search_near_returns_empty_on_no_data(self):
        with patch.object(self.adapter._session, "get", return_value=self._mock_search_response([])):
            results = self.adapter.search_near(lat=43.48, lng=-1.55, radius_km=30, max_results=10)
        assert results == []

    def test_search_near_respects_max_results(self):
        locations = [_make_ta_location(location_id=str(i), name=f"Place {i}") for i in range(15)]
        with patch.object(self.adapter._session, "get", return_value=self._mock_search_response(locations)):
            results = self.adapter.search_near(lat=43.48, lng=-1.55, radius_km=30, max_results=5)
        assert len(results) <= 5


class TestTripAdvisorGetDetails:
    def setup_method(self):
        self.adapter = TripAdvisorAdapter()
        self.adapter.api_key = "fake-ta-key"

    def test_get_details_returns_activity(self):
        loc = _make_ta_location()
        mock_resp = MagicMock()
        mock_resp.json.return_value = loc
        mock_resp.raise_for_status.return_value = None
        with patch.object(self.adapter._session, "get", return_value=mock_resp):
            result = self.adapter.get_details("9876")
        assert result is not None
        assert result.source_id == "9876"

    def test_get_details_returns_none_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("403")
        with patch.object(self.adapter._session, "get", return_value=mock_resp):
            result = self.adapter.get_details("bad")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# OfficeTourismeAdapter
# ─────────────────────────────────────────────────────────────────────────────


class TestOfficeTourismeAdapterFallbacks:
    """OT adapter must return [] when Playwright isn't available or URL isn't configured."""

    def setup_method(self):
        self.adapter = OfficeTourismeAdapter()

    def test_search_near_unknown_village_returns_empty(self):
        results = self.adapter.search_near(
            lat=43.48, lng=-1.55, radius_km=30, max_results=20,
            village_id="unknown-village-xyz",
        )
        assert results == []

    def test_search_near_no_playwright_returns_empty(self):
        # Patch playwright import to raise ImportError
        with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            results = self.adapter.search_near(
                lat=43.48, lng=-1.55, radius_km=30, max_results=20,
                village_id="biarritz",
            )
        assert isinstance(results, list)

    def test_get_details_returns_none(self):
        # OT adapter does not implement get_details scraping
        result = self.adapter.get_details("some-id")
        assert result is None

    def test_vtf_ot_urls_covers_key_villages(self):
        for village in ["biarritz", "chamonix", "bandol", "agde", "lacanau", "saint-cast"]:
            assert village in VTF_OT_URLS, f"{village} missing from VTF_OT_URLS"

    def test_vtf_ot_urls_covers_all_catalog_villages(self, db):
        """Every loaded village should have an OT URL (32 villages)."""
        from apps.catalog.models import Village
        from django.core.management import call_command

        call_command("load_vtf_mocks", verbosity=0)
        village_ids = set(Village.objects.values_list("id", flat=True))
        missing = village_ids - set(VTF_OT_URLS)
        assert not missing, f"Villages missing OT URLs: {sorted(missing)}"
        assert len(VTF_OT_URLS) >= len(village_ids)

    def test_search_near_does_not_raise_for_no_url(self):
        # Village with no OT URL configured
        try:
            self.adapter.search_near(
                lat=43.48, lng=-1.55, radius_km=30, max_results=20,
                village_id="karellis",
            )
        except Exception as exc:
            pytest.fail(f"search_near raised unexpectedly: {exc}")

    def test_search_near_signature_accepts_village_id_kwarg(self):
        """Ensure the OT adapter's search_near accepts village_id (pipeline requirement)."""
        import inspect
        sig = inspect.signature(self.adapter.search_near)
        assert "village_id" in sig.parameters


class TestOfficeTourismeParsing:
    def test_extracts_adult_and_child_prices_from_french_tariffs(self):
        text = "Tarif adulte : 18 €\nTarif enfant moins de 12 ans : 11 €"

        adult, child = _extract_price(text)

        assert adult == 18
        assert child == 11

    def test_extracts_free_activity_prices(self):
        assert _extract_price("Entrée libre toute l'année") == (0, 0)

    def test_extracts_rating_and_review_count_variants(self):
        rating, review_count = _extract_rating("Note 4,6 sur 5 - 1 234 avis")

        assert rating == pytest.approx(4.6)
        assert review_count == 1234

    def test_rejects_price_line_as_activity_name(self):
        assert not _looks_like_activity_name("Tarif adulte : 18 €")
        assert _looks_like_activity_name("Aquarium de Biarritz")

    def test_extracts_distance_from_listing_text(self):
        assert _extract_distance_km("Situé à 4,5 km du village") == pytest.approx(4.5)
        assert _extract_distance_km("A 750 m de la plage") == pytest.approx(0.75)

    def test_extracts_saisons_from_accented_text(self):
        assert _extract_saisons("Ouvert toute l'année") == ["hs", "vs", "ete", "fetes"]
        assert _extract_saisons("Ouvert en juillet et août") == ["ete"]

    def test_schema_node_produces_prices_coords_and_saisons(self):
        node = {
            "@type": "Event",
            "name": "Visite guidée du phare",
            "description": "Tarif adulte : 8 €\nTarif enfant : 4 €",
            "startDate": "2026-07-08",
            "endDate": "2026-08-26",
            "location": {
                "geo": {"latitude": "43.493", "longitude": "-1.553"},
            },
            "aggregateRating": {"ratingValue": "4.7", "reviewCount": "82"},
        }

        activity = _schema_node_to_activity(
            node,
            page_url="https://example.com/agenda",
            village_id="biarritz",
            center_lat=43.4832,
            center_lng=-1.5586,
        )

        assert activity is not None
        assert activity.price_adult == 8
        assert activity.price_child == 4
        assert activity.latitude == pytest.approx(43.493)
        assert activity.longitude == pytest.approx(-1.553)
        assert activity.rating == pytest.approx(4.7)
        assert activity.review_count == 82
        assert activity.saisons == ["ete"]
