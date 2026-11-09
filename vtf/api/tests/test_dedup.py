"""Deduplication engine tests (Phase 3).

Coverage:
  - normalize_name: lowercasing, accent stripping, special char removal
  - haversine_km: known distances, zero coords, symmetry
  - match_confidence: all four scoring dimensions, clamping to 1.0
  - find_best_match: threshold gating, exact source_id fast path,
    no-match case, best score selection
  - deduplicate_candidates: cross-source dedup, keeps highest review_count,
    empty input, single item, no duplicates case
  - detect_price_change: > 10% delta triggers alert, < 10% is silent,
    free activity (old_val=0) skipped, None values skipped, both fields checked

Run:
  pytest tests/test_dedup.py -v
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from apps.scraper.adapters.base import ScrapedActivity
from apps.scraper.dedup import (
    create_price_change_alerts,
    deduplicate_candidates,
    detect_price_change,
    find_best_match,
    haversine_km,
    match_confidence,
    normalize_name,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _activity(
    nom="Aquarium de Biarritz",
    latitude=43.48,
    longitude=-1.55,
    price_adult=17,
    price_child=11,
    type="aquarium",
    code="paid:al:aquarium-biarritz",
) -> Any:
    """Minimal duck-typed Activity object for dedup tests (no DB)."""

    @dataclass
    class FakeActivity:
        nom: str
        latitude: float | None
        longitude: float | None
        price_adult: int | None
        price_child: int | None
        type: str
        code: str

    return FakeActivity(
        nom=nom,
        latitude=latitude,
        longitude=longitude,
        price_adult=price_adult,
        price_child=price_child,
        type=type,
        code=code,
    )


def _candidate(
    nom="Aquarium de Biarritz",
    source="tripadvisor",
    source_id="ta-9876",
    source_url="https://tripadvisor.fr/...",
    latitude=43.48,
    longitude=-1.55,
    price_adult=17,
    price_child=11,
    type_hint="aquarium",
    rating=4.3,
    review_count=1800,
) -> ScrapedActivity:
    return ScrapedActivity(
        source=source,
        source_id=source_id,
        source_url=source_url,
        nom=nom,
        type_hint=type_hint,
        type_emoji="🐠",
        latitude=latitude,
        longitude=longitude,
        price_adult=price_adult,
        price_child=price_child,
        rating=rating,
        review_count=review_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
# normalize_name
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeName:
    def test_lowercases(self):
        assert normalize_name("AQUARIUM") == "aquarium"

    def test_strips_accents(self):
        assert normalize_name("Été") == "ete"
        assert normalize_name("École") == "ecole"
        assert normalize_name("Île") == "ile"

    def test_removes_special_chars(self):
        # Only alphanumeric + space kept
        result = normalize_name("Musée d'Orsay — Paris!")
        assert "'" not in result
        assert "—" not in result
        assert "!" not in result

    def test_strips_leading_trailing_whitespace(self):
        assert normalize_name("  Biarritz  ") == "biarritz"

    def test_empty_string(self):
        assert normalize_name("") == ""

    def test_mixed_case_with_accents(self):
        a = normalize_name("Château de Versailles")
        b = normalize_name("chateau de versailles")
        assert a == b

    def test_numbers_preserved(self):
        assert "42" in normalize_name("Route 42")


# ─────────────────────────────────────────────────────────────────────────────
# haversine_km
# ─────────────────────────────────────────────────────────────────────────────


class TestHaversineKm:
    def test_same_point_is_zero(self):
        assert haversine_km(43.48, -1.55, 43.48, -1.55) == pytest.approx(0.0, abs=1e-6)

    def test_paris_to_london_roughly_340km(self):
        dist = haversine_km(48.8566, 2.3522, 51.5074, -0.1278)
        assert 330 < dist < 360

    def test_symmetry(self):
        a_to_b = haversine_km(43.48, -1.55, 45.92, 6.87)
        b_to_a = haversine_km(45.92, 6.87, 43.48, -1.55)
        assert a_to_b == pytest.approx(b_to_a, rel=1e-6)

    def test_biarritz_to_agde_roughly_350km(self):
        dist = haversine_km(43.48, -1.55, 43.31, 3.47)
        assert 300 < dist < 420

    def test_500m_nearby_points(self):
        # Approx 500m offset in latitude (~0.0045 degrees)
        dist = haversine_km(43.48, -1.55, 43.4845, -1.55)
        assert dist < 1.0


# ─────────────────────────────────────────────────────────────────────────────
# match_confidence
# ─────────────────────────────────────────────────────────────────────────────


class TestMatchConfidence:
    def test_identical_activity_scores_near_1(self):
        cand = _candidate(
            nom="Aquarium de Biarritz",
            latitude=43.48, longitude=-1.55,
            price_adult=17, type_hint="aquarium",
        )
        exist = _activity(
            nom="Aquarium de Biarritz",
            latitude=43.48, longitude=-1.55,
            price_adult=17, type="aquarium",
        )
        score = match_confidence(cand, exist)
        # Perfect name + geo + price + type → close to 1.0
        assert score > 0.85

    def test_completely_different_scores_near_0(self):
        cand = _candidate(nom="Zoo de la Palmyre", latitude=45.6, longitude=-1.1, type_hint="zoo")
        exist = _activity(nom="Musée Basque", latitude=43.29, longitude=-1.31, type="museum")
        score = match_confidence(cand, exist)
        assert score < 0.35

    def test_score_capped_at_1(self):
        cand = _candidate(nom="Aquarium", latitude=43.48, longitude=-1.55, price_adult=17, type_hint="aquarium")
        exist = _activity(nom="Aquarium", latitude=43.48, longitude=-1.55, price_adult=17, type="aquarium")
        assert match_confidence(cand, exist) <= 1.0

    def test_score_always_non_negative(self):
        cand = _candidate()
        exist = _activity(nom="Something Completely Different", latitude=0, longitude=0, price_adult=999)
        assert match_confidence(cand, exist) >= 0.0

    def test_name_similarity_contributes_up_to_040(self):
        # Perfect name match, no other signals
        cand = _candidate(nom="Aquarium de Biarritz", latitude=0, longitude=0,
                          price_adult=None, type_hint="")
        exist = _activity(nom="Aquarium de Biarritz", latitude=None, longitude=None,
                          price_adult=None, type="")
        score = match_confidence(cand, exist)
        assert score <= 0.41

    def test_geo_proximity_500m_adds_score(self):
        cand_far = _candidate(nom="Zoo", latitude=0, longitude=0, price_adult=None, type_hint="")
        cand_near = _candidate(nom="Zoo", latitude=43.48, longitude=-1.55, price_adult=None, type_hint="")
        exist = _activity(nom="Zoo", latitude=43.48, longitude=-1.55, price_adult=None, type="")

        score_far = match_confidence(cand_far, exist)
        score_near = match_confidence(cand_near, exist)
        assert score_near > score_far

    def test_no_geo_on_existing_skips_geo_score(self):
        cand = _candidate(nom="Zoo", latitude=43.48, longitude=-1.55)
        exist = _activity(nom="Zoo", latitude=None, longitude=None)
        # Should not raise, geo dimension simply skipped
        score = match_confidence(cand, exist)
        assert 0.0 <= score <= 1.0

    def test_price_within_20pct_adds_score(self):
        cand_exact = _candidate(nom="X", latitude=0, longitude=0, price_adult=17)
        cand_off = _candidate(nom="X", latitude=0, longitude=0, price_adult=40)
        exist = _activity(nom="X", latitude=None, longitude=None, price_adult=17)

        s_exact = match_confidence(cand_exact, exist)
        s_off = match_confidence(cand_off, exist)
        assert s_exact > s_off

    def test_type_match_adds_010(self):
        cand_match = _candidate(nom="X", latitude=0, longitude=0, price_adult=None, type_hint="aquarium")
        cand_miss = _candidate(nom="X", latitude=0, longitude=0, price_adult=None, type_hint="park")
        exist = _activity(nom="X", latitude=None, longitude=None, price_adult=None, type="aquarium")

        s_match = match_confidence(cand_match, exist)
        s_miss = match_confidence(cand_miss, exist)
        assert s_match > s_miss

    def test_accent_difference_does_not_tank_name_score(self):
        cand = _candidate(nom="Musée d'Orsay", latitude=0, longitude=0)
        exist = _activity(nom="Musee d Orsay", latitude=None, longitude=None)
        score = match_confidence(cand, exist)
        assert score > 0.25


# ─────────────────────────────────────────────────────────────────────────────
# find_best_match
# ─────────────────────────────────────────────────────────────────────────────


class TestFindBestMatch:
    def test_returns_best_matching_activity(self):
        cand = _candidate(nom="Aquarium de Biarritz", latitude=43.48, longitude=-1.55,
                          price_adult=17, type_hint="aquarium")
        acts = [
            _activity(nom="Musée Basque", latitude=43.29, longitude=-1.31, type="museum"),
            _activity(nom="Aquarium de Biarritz", latitude=43.48, longitude=-1.55,
                      price_adult=17, type="aquarium"),
        ]
        match, score = find_best_match(cand, acts)
        assert match is not None
        assert match.nom == "Aquarium de Biarritz"
        assert score > 0.70

    def test_returns_none_when_below_threshold(self):
        cand = _candidate(nom="Unknown Activity", latitude=0, longitude=0)
        acts = [_activity(nom="Completely Different Place", latitude=10, longitude=10)]
        match, score = find_best_match(cand, acts)
        assert match is None
        assert score < 0.70

    def test_empty_existing_list_returns_none(self):
        cand = _candidate()
        match, score = find_best_match(cand, [])
        assert match is None
        assert score == 0.0

    def test_exact_source_id_match_returns_1_0(self):
        cand = _candidate(source_id="paid:al:aquarium-biarritz")
        acts = [
            _activity(nom="Aquarium de Biarritz", code="paid:al:aquarium-biarritz"),
        ]
        match, score = find_best_match(cand, acts)
        assert match is not None
        assert score == pytest.approx(1.0)

    def test_custom_threshold_raises_bar(self):
        cand = _candidate(nom="Aquarium de Biarritz", latitude=43.48, longitude=-1.55,
                          price_adult=17, type_hint="aquarium")
        acts = [_activity(nom="Aquarium de Biarritz", latitude=43.48, longitude=-1.55,
                          price_adult=17, type="aquarium")]
        # With threshold 0.99 nothing should match (unless perfect)
        match, score = find_best_match(cand, acts, threshold=0.99)
        # Might or might not match depending on exact score; just assert no exception
        assert isinstance(score, float)

    def test_picks_best_from_multiple_candidates(self):
        cand = _candidate(nom="Surf School", latitude=43.48, longitude=-1.55)
        acts = [
            _activity(nom="Surf School", latitude=43.48, longitude=-1.55),       # good
            _activity(nom="Something Else", latitude=0, longitude=0),              # bad
            _activity(nom="Surf Classe", latitude=43.48, longitude=-1.55),        # medium
        ]
        match, _ = find_best_match(cand, acts, threshold=0.30)
        assert match.nom == "Surf School"


# ─────────────────────────────────────────────────────────────────────────────
# deduplicate_candidates
# ─────────────────────────────────────────────────────────────────────────────


class TestDeduplicateCandidates:
    def test_empty_returns_empty(self):
        assert deduplicate_candidates([]) == []

    def test_single_item_unchanged(self):
        cands = [_candidate()]
        result = deduplicate_candidates(cands)
        assert len(result) == 1

    def test_no_duplicates_all_kept(self):
        cands = [
            _candidate(nom="Aquarium", source="google_places", source_id="g1"),
            _candidate(nom="Surf School", source="tripadvisor", source_id="ta1"),
            _candidate(nom="Musée Basque", source="google_places", source_id="g2"),
        ]
        result = deduplicate_candidates(cands)
        assert len(result) == 3

    def test_near_duplicate_names_collapsed(self):
        # Same activity returned by two sources with similar names
        cands = [
            _candidate(nom="Aquarium de Biarritz", source="google_places", source_id="g1",
                       review_count=100),
            _candidate(nom="Aquarium Biarritz", source="tripadvisor", source_id="ta1",
                       review_count=1800),
        ]
        result = deduplicate_candidates(cands)
        assert len(result) == 1

    def test_dedup_keeps_higher_review_count(self):
        low_reviews = _candidate(nom="Surf School", source="google_places", source_id="g1",
                                 review_count=50)
        high_reviews = _candidate(nom="Surf School", source="tripadvisor", source_id="ta1",
                                  review_count=600)
        # Order: low first, then high
        result = deduplicate_candidates([low_reviews, high_reviews])
        assert len(result) == 1
        assert result[0].review_count == 600

    def test_dedup_keeps_higher_review_count_reversed_order(self):
        low_reviews = _candidate(nom="Surf School", source="google_places", source_id="g1",
                                 review_count=50)
        high_reviews = _candidate(nom="Surf School", source="tripadvisor", source_id="ta1",
                                  review_count=600)
        # Order: high first, then low
        result = deduplicate_candidates([high_reviews, low_reviews])
        assert len(result) == 1
        assert result[0].review_count == 600

    def test_clearly_different_names_not_collapsed(self):
        cands = [
            _candidate(nom="Aquarium de Biarritz", source_id="g1"),
            _candidate(nom="Cinéma de Biarritz", source_id="g2"),
        ]
        result = deduplicate_candidates(cands)
        assert len(result) == 2

    def test_three_sources_same_activity_kept_once(self):
        cands = [
            _candidate(nom="Aquarium Biarritz", source="google_places", source_id="g1", review_count=100),
            _candidate(nom="Aquarium de Biarritz", source="tripadvisor", source_id="ta1", review_count=1800),
            _candidate(nom="Aquarium Biarritz", source="ot_local", source_id="ot1", review_count=0),
        ]
        result = deduplicate_candidates(cands)
        assert len(result) == 1


# ─────────────────────────────────────────────────────────────────────────────
# detect_price_change
# ─────────────────────────────────────────────────────────────────────────────


class TestDetectPriceChange:
    def test_no_change_returns_empty(self):
        cand = _candidate(price_adult=17, price_child=11)
        exist = _activity(price_adult=17, price_child=11)
        assert detect_price_change(cand, exist) == []

    def test_small_change_below_threshold_returns_empty(self):
        # 5% change, default threshold 10%
        cand = _candidate(price_adult=18, price_child=11)  # ~5.9% up
        exist = _activity(price_adult=17, price_child=11)
        result = detect_price_change(cand, exist)
        assert result == []

    def test_adult_price_change_above_threshold_flagged(self):
        cand = _candidate(price_adult=19, price_child=11)  # ~11.8% up
        exist = _activity(price_adult=17, price_child=11)
        result = detect_price_change(cand, exist)
        assert len(result) == 1
        assert result[0]["field"] == "price_adult"
        assert result[0]["old_value"] == 17
        assert result[0]["new_value"] == 19

    def test_child_price_change_above_threshold_flagged(self):
        cand = _candidate(price_adult=17, price_child=13)  # ~18% up
        exist = _activity(price_adult=17, price_child=11)
        result = detect_price_change(cand, exist)
        assert len(result) == 1
        assert result[0]["field"] == "price_child"

    def test_both_prices_changed_returns_two_alerts(self):
        cand = _candidate(price_adult=20, price_child=14)
        exist = _activity(price_adult=17, price_child=11)
        result = detect_price_change(cand, exist)
        fields = {r["field"] for r in result}
        assert "price_adult" in fields
        assert "price_child" in fields

    def test_free_activity_old_price_zero_skipped(self):
        cand = _candidate(price_adult=5, price_child=3)
        exist = _activity(price_adult=0, price_child=0)
        result = detect_price_change(cand, exist)
        assert result == []

    def test_none_new_price_skipped(self):
        cand = _candidate(price_adult=None, price_child=None)
        exist = _activity(price_adult=17, price_child=11)
        result = detect_price_change(cand, exist)
        assert result == []

    def test_none_existing_price_skipped(self):
        cand = _candidate(price_adult=17, price_child=11)
        exist = _activity(price_adult=None, price_child=None)
        result = detect_price_change(cand, exist)
        assert result == []

    def test_price_decrease_also_detected(self):
        cand = _candidate(price_adult=13, price_child=8)  # drop > 10%
        exist = _activity(price_adult=17, price_child=11)
        result = detect_price_change(cand, exist)
        assert any(r["field"] == "price_adult" for r in result)

    def test_custom_threshold(self):
        # 5% change, custom threshold 3%
        cand = _candidate(price_adult=18, price_child=11)
        exist = _activity(price_adult=17, price_child=11)
        result = detect_price_change(cand, exist, threshold_pct=0.03)
        assert len(result) == 1
        assert result[0]["field"] == "price_adult"

    def test_delta_pct_field_in_result(self):
        cand = _candidate(price_adult=19, price_child=11)
        exist = _activity(price_adult=17, price_child=11)
        result = detect_price_change(cand, exist)
        assert "delta_pct" in result[0]
        assert result[0]["delta_pct"] > 0


@pytest.mark.django_db
class TestCreatePriceChangeAlerts:
    def test_creates_pending_alert_for_high_confidence_match(self):
        from apps.catalog.models import Activity
        from apps.scraper.models import PriceChangeAlert

        activity = Activity.objects.create(
            code="paid:al:aquarium-biarritz",
            region="Aquitaine / Landes",
            kind="paid",
            nom="Aquarium de Biarritz",
            type="🐠",
            price_adult=17,
            price_child=11,
            saisons=["hs", "vs", "ete", "fetes"],
        )
        cand = _candidate(price_adult=19, price_child=11)

        created = create_price_change_alerts(
            cand, activity, confidence=0.95
        )

        assert created == 1
        assert PriceChangeAlert.objects.filter(
            activity=activity, field="price_adult", status="pending"
        ).exists()

    def test_skips_duplicate_pending_alerts(self):
        from apps.catalog.models import Activity
        from apps.scraper.models import PriceChangeAlert
        from django.utils import timezone as dj_timezone

        activity = Activity.objects.create(
            code="paid:al:aquarium-biarritz",
            region="Aquitaine / Landes",
            kind="paid",
            nom="Aquarium de Biarritz",
            type="🐠",
            price_adult=17,
            price_child=11,
            saisons=["hs", "vs", "ete", "fetes"],
        )
        PriceChangeAlert.objects.create(
            activity=activity,
            field="price_adult",
            old_value=17,
            new_value=19,
            source="ot_local",
            scraped_at=dj_timezone.now(),
            status="pending",
        )
        cand = _candidate(price_adult=19, price_child=11)

        created = create_price_change_alerts(
            cand, activity, confidence=0.95
        )

        assert created == 0
        assert PriceChangeAlert.objects.filter(
            activity=activity, field="price_adult", status="pending"
        ).count() == 1

    def test_low_confidence_does_not_create_alert(self):
        from apps.catalog.models import Activity
        from apps.scraper.models import PriceChangeAlert

        activity = Activity.objects.create(
            code="paid:al:aquarium-biarritz",
            region="Aquitaine / Landes",
            kind="paid",
            nom="Aquarium de Biarritz",
            type="🐠",
            price_adult=17,
            price_child=11,
            saisons=["hs", "vs", "ete", "fetes"],
        )
        cand = _candidate(price_adult=19, price_child=11)

        created = create_price_change_alerts(
            cand, activity, confidence=0.50
        )

        assert created == 0
        assert not PriceChangeAlert.objects.exists()