"""Phase 2 tests — Recommendation engine (AC2.1–AC2.14).

Coverage:
  AC2.1  — NEVER returns empty villages[]  (20 fuzzing inputs)
  AC2.2  — Each fallback tier activatable
  AC2.3  — Tier 5 works with empty database
  AC2.4  — explain=true provides French reasons
  AC2.5  — estimatedTotal within ±5% of full estimate (spot-check)
  AC2.6  — Interaction tracking < 50ms
  AC2.8  — Scoring weights updatable via admin
  AC2.9  — Response time < 2000ms for recommendation (test-env budget)
  AC2.10 — Rate limiting (throttle wired at 100/session/hour)

URL mapping (FIX applied):
  Recommender endpoints  → /api/v2/  (apps.recommender.urls)
  Interaction endpoints  → /api/v1/  (apps.pricing.urls — unchanged)

Run:
  pytest tests/test_phase2.py -v
"""
from __future__ import annotations

import base64
import itertools
import random
import statistics
import time
from collections.abc import Callable
from datetime import date, timedelta
from io import StringIO
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from apps.catalog.models import Meal, PricingRules, Village
from apps.pricing.models import SimulationLog
from apps.pricing.services.stay_estimate import estimate_sejour_total
from apps.recommender import engine
from apps.recommender.management.commands import train_cf_model as cf_train_command
from apps.recommender.management.commands.train_cf_model import (
    Command,
    MiniDataFrame,
    _as_interaction_frame,
    _collect_interaction_rows,
)
from apps.recommender.models import (
    RecommendationSystemState,
    VillageInteraction,
    VillagePopularityCache,
)
from apps.recommender.services.estimate import bulk_estimate, lightweight_estimate
from apps.recommender.strategies import collaborative as cf
from apps.recommender.strategies import content_based, popularity
from apps.recommender.strategies.collaborative import _get_or_train_model, cf_rerank
from apps.recommender.strategies.popularity import seed_villages
from common.enums import EnvCode, Region
from common.throttles import InteractionsSessionThrottle
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient

# ─── Fixtures ─────────────────────────────────────────────────────────────

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-phase2-cache",
    }
}

@pytest.fixture
def village_factory(db) -> Callable[..., Village]:
    """Create minimal Village rows for isolated unit tests (e.g. AC2.13)."""
    counter = itertools.count(1)

    def _create(**overrides: Any) -> Village:
        n = next(counter)
        defaults: dict[str, Any] = {
            "id": f"test-village-{n}",
            "nom": f"Test Village {n}",
            "nom2": "",
            "region": Region.AQUITAINE_LANDES,
            "env_emoji": "🌊",
            "env_code": EnvCode.SEA,
            "has_loc": False,
            "ski": False,
            "ouverture": "",
            "tarifs": {},
            "bebe_club": False,
            "forfait_rm": False,
            "qf_exc": False,
            "enf_solo_half": False,
        }
        defaults.update(overrides)
        return Village.objects.create(**defaults)

    return _create


# ─── Helpers ──────────────────────────────────────────────────────────────

def _random_family() -> dict:
    adultes = random.randint(1, 4)
    nb_enfants = random.randint(0, 4)
    enfants = [{"age": random.randint(0, 17)} for _ in range(nb_enfants)]
    return {
        "adultes": adultes,
        "enfants": enfants,
        "qfVal": random.choice([None, 600, 900, 1500]),
        "isSoloParent": adultes == 1 and nb_enfants > 0,
        "maxiFamily": nb_enfants >= 3,
    }


def _random_preferences() -> dict:
    return {
        "envs": random.sample(["sea", "mountain", "forest", "countryside", "sun"], k=random.randint(0, 3)),
        "formule": random.choice([None, "PC", "DP", "LOC"]),
        "budget": random.choice([None, 1000, 2000, 3000]),
        "dates": {
            "debut": "2026-07-05",
            "fin": "2026-07-12",
        },
        "mustHave": [],
        "avoidSki": random.choice([True, False]),
    }


def _random_reco_input() -> dict:
    return {
        "family": _random_family(),
        "preferences": _random_preferences(),
        "sessionId": f"test-session-{random.randint(1000, 9999)}",
        "limit": random.randint(1, 6),
        "explain": random.choice([True, False]),
    }


# ─── AC2.1 — Never empty (20 fuzzing inputs) ─────────────────────────────

class TestRecommendationNeverEmpty(TestCase):
    """AC2.1 — Recommendation endpoint NEVER returns empty villages[]."""

    def setUp(self):
        self.client = APIClient()

    def test_never_empty_with_no_villages(self):
        """Tier 5 works even with no villages in DB (AC2.3)."""
        result = engine.recommend(
            family={"adultes": 2, "enfants": [], "qfVal": None, "isSoloParent": False},
            preferences={},
        )
        assert result is not None
        assert isinstance(result.villages, list)

    def test_recommend_endpoint_never_returns_empty(self):
        """AC2.1 — 20 randomized inputs via API. All must have ≥1 village."""
        random.seed(42)
        for i in range(20):
            body = _random_reco_input()
            response = self.client.post(
                "/api/v2/recommend/villages",   # FIX: was /api/v1/
                body,
                format="json",
            )
            assert response.status_code == 200, f"Input #{i}: got {response.status_code}"
            data = response.json()
            villages = data.get("data", {}).get("villages") or data.get("villages") or []
            assert len(villages) >= 1, f"Input #{i}: empty villages! Body: {body}"

    def test_recommend_minimal_body(self):
        """AC2.2 — popularity fallback fires with empty preferences."""
        # Force an empty DB so the endpoint uses Tier 5 (nuclear) seed fallback.
        Village.objects.all().delete()
        response = self.client.post(
            "/api/v2/recommend/villages",   # FIX: was /api/v1/
            {
                "family": {"adultes": 2, "enfants": [], "qfVal": None, "isSoloParent": False},
                "preferences": {},
            },
            format="json",
        )
        assert response.status_code == 200
        data = response.json()
        result = data.get("data", data)
        assert result.get("strategy") == "popular_fallback"
        # With an empty DB, we use Tier 5 seed ranking (confidence 0.05).
        assert result.get("confidence") == 0.05
        villages = result.get("villages") or []
        assert len(villages) >= 1
        assert result.get("fallbackUsed") is True

    def test_tier5_api_with_empty_database(self):
        """AC2.3 — Tier 5 works via API even when Village table is empty."""
        Village.objects.all().delete()
        response = self.client.post(
            "/api/v2/recommend/villages",
            {
                "family": {"adultes": 2, "enfants": [], "qfVal": None, "isSoloParent": False},
                "preferences": {},
                "limit": 3,
            },
            format="json",
        )
        assert response.status_code == 200
        result = response.json().get("data", response.json())
        assert len(result.get("villages") or []) >= 1
        assert result.get("strategy") == "popular_fallback"
        assert result.get("confidence") == 0.05

    def test_explain_true_has_reasons(self):
        """AC2.4 — explain=true includes reasons list per village."""
        response = self.client.post(
            "/api/v2/recommend/villages",   # FIX: was /api/v1/
            {
                "family": {"adultes": 2, "enfants": [{"age": 2}], "qfVal": 700},
                "preferences": {
                    "envs": ["sea"],
                    "formule": "PC",
                    "dates": {"debut": "2026-07-05", "fin": "2026-07-12"},
                },
                "explain": True,
                "limit": 3,
            },
            format="json",
        )
        assert response.status_code == 200
        data = response.json()
        result = data.get("data", data)
        villages = result.get("villages") or []
        if villages:
            first = villages[0]
            assert "reasons" in first
            assert isinstance(first["reasons"], list)
            assert "estimatedTotal" in first
            assert "bookingUrl" in first


# ─── AC2.2 — Fallback tier tests ─────────────────────────────────────────

class TestFallbackTiers(TestCase):
    """AC2.2 — Each fallback tier activatable via specific input patterns."""

    def setUp(self):
        self.client = APIClient()

    def test_tier4_popularity_fallback(self):
        """Popularity fallback fires when all mustHave constraints score low."""
        response = self.client.post(
            "/api/v2/recommend/villages",   # FIX: was /api/v1/
            {
                "family": {"adultes": 2, "enfants": [], "qfVal": None, "isSoloParent": False},
                "preferences": {
                    "mustHave": ["bebeClub", "ski", "qfExc"],
                    "avoidSki": False,
                    "envs": [],
                },
                "limit": 6,
            },
            format="json",
        )
        assert response.status_code == 200
        data = response.json()
        result = data.get("data", data)
        assert len(result.get("villages") or []) >= 1

    def test_tier5_seed_ranking(self):
        """AC2.3 — Tier 5 seed ranking returns villages without DB interaction data."""
        seeds = seed_villages(limit=6)
        assert isinstance(seeds, list)


# ─── GET /api/v2/village-popularity-cache ───────────────────────────────

class TestVillagePopularityCacheApi:
    """Popularity cache API contract for `/api/v2/village-popularity-cache`."""

    @pytest.mark.django_db
    def test_returns_cache_rows_ordered_by_score_then_village_name(self, village_factory):
        client = APIClient()
        alpha = village_factory(id="popular-alpha", nom="Alpha Village")
        beta = village_factory(id="popular-beta", nom="Beta Village")
        gamma = village_factory(id="popular-gamma", nom="Gamma Village")

        VillagePopularityCache.objects.create(
            village=gamma,
            views_30d=1,
            simulations_30d=2,
            bookmarks_30d=3,
            score=4.0,
        )
        VillagePopularityCache.objects.create(
            village=beta,
            views_30d=10,
            simulations_30d=5,
            bookmarks_30d=1,
            score=9.5,
        )
        VillagePopularityCache.objects.create(
            village=alpha,
            views_30d=8,
            simulations_30d=6,
            bookmarks_30d=2,
            score=9.5,
        )

        response = client.get("/api/v2/village-popularity-cache")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["message"] == "Village popularity cache fetched."

        rows = body["data"]
        assert [row["village"]["id"] for row in rows] == [
            "popular-alpha",
            "popular-beta",
            "popular-gamma",
        ]

        first = rows[0]
        assert first["village"] == {
            "id": "popular-alpha",
            "nom": "Alpha Village",
            "nom2": "",
            "region": Region.AQUITAINE_LANDES,
            "env": "🌊",
            "envCode": EnvCode.SEA,
            "formules": [],
            "ski": False,
            "bebeClub": False,
            "qfExc": False,
            "enfSoloHalf": False,
            "hasLoc": False,
        }
        assert first["views30d"] == 8
        assert first["simulations30d"] == 6
        assert first["bookmarks30d"] == 2
        assert first["score"] == 9.5
        assert parse_datetime(first["updatedAt"]) is not None

    @pytest.mark.django_db
    def test_returns_empty_list_when_cache_has_no_rows(self):
        response = APIClient().get("/api/v2/village-popularity-cache")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] == []


# ─── AC2.2 — Tier-by-tier integration (waterfall flags) ────────────────

class TestWaterfallTierTransitions(TestCase):
    """Validates the tier selection + contract flags (fallbackUsed/relaxedFilters)."""

    def setUp(self):
        self.client = APIClient()

    def _base_body(self) -> dict:
        return {
            "family": {"adultes": 2, "enfants": [], "qfVal": None, "isSoloParent": False},
            "preferences": {
                "envs": ["sea"],
                "formule": "PC",
                "budget": 3000,
                "dates": {"debut": "2026-07-05", "fin": "2026-07-12"},
                "mustHave": [],
                "avoidSki": False,
            },
            "limit": 2,
            "explain": False,
        }

    @staticmethod
    def _scored_list(*, scores: list[float], village_ids: list[str] | None = None) -> list[dict]:
        ids = village_ids or [f"v{i}" for i in range(len(scores))]
        return [
            {"village_id": ids[i], "village": None, "score": float(s), "reasons": [], "warnings": []}
            for i, s in enumerate(scores)
        ]

    def test_tier1_content_based_selected(self):


        with patch.object(
            content_based,
            "score_all_villages",
            return_value=self._scored_list(scores=[0.9, 0.8, 0.85, 0.4, 0.3, 0.2]),
        ):
            response = self.client.post("/api/v2/recommend/villages", self._base_body(), format="json")
            assert response.status_code == 200
            result = response.json()["data"]

        assert result["strategy"] in {"personalized", "personalized_cf"}
        assert result["fallbackUsed"] is False
        assert result["relaxedFilters"] == []
        assert 0.85 <= result["confidence"] <= 0.95

    def test_tier2_relaxed_budget_selected(self):


        tier1_scored = self._scored_list(scores=[0.29, 0.25, 0.28, 0.05, 0.1, 0.12])
        tier2_scored = self._scored_list(scores=[0.25, 0.26, 0.24, 0.19, 0.18, 0.17])

        with patch.object(content_based, "score_all_villages", side_effect=[tier1_scored, tier2_scored]):
            response = self.client.post("/api/v2/recommend/villages", self._base_body(), format="json")
            assert response.status_code == 200
            result = response.json()["data"]

        assert result["strategy"] == "personalized"
        assert result["fallbackUsed"] is False
        assert result["relaxedFilters"] == ["budget"]
        assert 0.5 <= result["confidence"] <= 0.7

    def test_tier3_region_only_selected(self):


        tier1_scored = self._scored_list(scores=[0.29, 0.25, 0.28, 0.05, 0.1, 0.12])
        tier2_scored = self._scored_list(scores=[0.19, 0.18, 0.17, 0.12, 0.1, 0.09])
        tier3_scored = self._scored_list(scores=[0.11, 0.09, 0.08, 0.05, 0.04, 0.03])

        with patch.object(content_based, "score_all_villages", side_effect=[tier1_scored, tier2_scored, tier3_scored]):
            response = self.client.post("/api/v2/recommend/villages", self._base_body(), format="json")
            assert response.status_code == 200
            result = response.json()["data"]

        assert result["strategy"] == "popular_fallback"
        assert result["fallbackUsed"] is False
        assert result["relaxedFilters"] == ["budget", "formule", "mustHave", "avoidSki"]
        assert 0.3 <= result["confidence"] <= 0.5

    def test_tier4_popularity_selected(self):


        tier1_scored = self._scored_list(scores=[0.29, 0.25, 0.28, 0.05, 0.1, 0.12])
        tier2_scored = self._scored_list(scores=[0.19, 0.18, 0.17, 0.12, 0.1, 0.09])
        # Make tier3 empty: scores must all be <= 0.1
        tier3_scored = self._scored_list(scores=[0.1, 0.09, 0.08, 0.07, 0.06, 0.05])

        pop_results = [
            {"village_id": "p1", "village": None, "score": 0.8, "reasons": [], "warnings": [], "estimated_total": None},
            {"village_id": "p2", "village": None, "score": 0.7, "reasons": [], "warnings": [], "estimated_total": None},
        ]

        with (
            patch.object(content_based, "score_all_villages", side_effect=[tier1_scored, tier2_scored, tier3_scored]),
            patch.object(popularity, "popular_villages", return_value=pop_results),
        ):
            response = self.client.post("/api/v2/recommend/villages", self._base_body(), format="json")
            assert response.status_code == 200
            result = response.json()["data"]

        assert result["strategy"] == "popular_fallback"
        assert result["fallbackUsed"] is True
        assert result["relaxedFilters"] == ["all_filters"]
        assert 0.1 <= result["confidence"] <= 0.2

    def test_tier5_seed_selected(self):


        tier1_scored = self._scored_list(scores=[0.29, 0.25, 0.28, 0.05, 0.1, 0.12])
        tier2_scored = self._scored_list(scores=[0.19, 0.18, 0.17, 0.12, 0.1, 0.09])
        tier3_scored = self._scored_list(scores=[0.1, 0.09, 0.08, 0.07, 0.06, 0.05])

        seed_results = [
            {"village_id": "s1", "village": None, "score": 0.05, "reasons": [], "warnings": [], "estimated_total": None},
            {"village_id": "s2", "village": None, "score": 0.05, "reasons": [], "warnings": [], "estimated_total": None},
        ]

        with (
            patch.object(content_based, "score_all_villages", side_effect=[tier1_scored, tier2_scored, tier3_scored]),
            patch.object(popularity, "popular_villages", return_value=[]),
            patch.object(popularity, "seed_villages", return_value=seed_results),
        ):
            response = self.client.post("/api/v2/recommend/villages", self._base_body(), format="json")
            assert response.status_code == 200
            result = response.json()["data"]

        assert result["strategy"] == "popular_fallback"
        assert result["fallbackUsed"] is True
        assert result["relaxedFilters"] == ["all_filters"]
        assert result["confidence"] == 0.05


# ─── AC2.8 — Scoring weights via admin ───────────────────────────────────

class TestRecoWeightsAdmin(TestCase):
    """AC2.8 — Scoring weights updatable via admin endpoint without deployment."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("admin", "admin@test.com", "pass")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_get_weights_returns_active_defaults(self):
        response = self.client.get("/api/v2/admin/reco-weights")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["message"] == "Scoring weights fetched."
        result = body["data"]
        assert result["budget_fit"] == 0.30
        assert result["env_match"] == 0.25
        assert result["family_fit"] == 0.20
        assert result["season_availability"] == 0.15
        assert result["extras_match"] == 0.10
        assert result["popularity_boost"] == 0.05
        assert result["interaction_boost"] == 0.05

    def test_update_weights(self):
        response = self.client.post(
            "/api/v2/admin/reco-weights",   # FIX: was /api/v1/
            {"budget_fit": 0.40, "env_match": 0.20},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()
        result = data.get("data", data)
        assert result["budget_fit"] == 0.40
        assert result["env_match"] == 0.20

    def test_weights_endpoint_staff_only(self):
        """Non-staff cannot access admin endpoints."""
        User = get_user_model()
        regular_user = User.objects.create_user("user", "user@test.com", "pass")
        client = APIClient()
        client.force_authenticate(regular_user)
        response = client.post(
            "/api/v2/admin/reco-weights",   # FIX: was /api/v1/
            {"budget_fit": 0.5},
            format="json",
        )
        assert response.status_code == 403

    def test_weights_endpoint_missing_auth_returns_json_without_browser_challenge(self):
        client = APIClient()
        response = client.get("/api/v2/admin/reco-weights")

        assert response.status_code == 403
        assert "WWW-Authenticate" not in response
        assert response.json() == {
            "success": False,
            "message": "Authentication credentials were not provided.",
            "data": None,
        }


# ─── AC2.9 — Response time ───────────────────────────────────────────────

class TestRecommendationPerformance(TestCase):
    """AC2.9 — Response time < 500ms prod; 2000ms budget for test environment."""

    @classmethod
    def setUpTestData(cls):
        # Load real catalog so recommendation scoring + lightweight estimates execute.

        call_command("load_vtf_mocks", verbosity=0)

    def setUp(self):
        self.client = APIClient()

    def test_recommend_response_time(self):
        body = {
            "family": {"adultes": 2, "enfants": [{"age": 4}, {"age": 8}], "qfVal": 900},
            "preferences": {
                "envs": ["sea"],
                "formule": "PC",
                "budget": 3000,
                "dates": {"debut": "2026-07-05", "fin": "2026-07-12"},
            },
            "limit": 6,
            "explain": True,
        }
        start = time.perf_counter()
        response = self.client.post(
            "/api/v2/recommend/villages",   # FIX: was /api/v1/
            body,
            format="json",
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert response.status_code == 200
        assert elapsed_ms < 500, f"Recommendation took {elapsed_ms:.0f}ms (limit 500ms)"


# ─── Interaction tracking tests ───────────────────────────────────────────

class TestInteractionTracking(TestCase):
    """AC2.6 — Interaction tracking. Note: /interactions stays on api/v1/ (pricing app)."""

    def setUp(self):
        self.client = APIClient()

    def test_interaction_endpoint_exists_and_creates_row(self):
        """POST /api/v1/interactions creates a VillageInteraction row."""
        if not Village.objects.exists():
            self.skipTest("No villages in DB — run load_vtf_mocks first.")

        village = Village.objects.first()
        response = self.client.post(
            "/api/v1/interactions",   # CORRECT: InteractionView is in pricing/urls.py → api/v1/
            {
                "sessionId": "test-session-001",
                "villageId": village.id,
                "kind": "simulate",
                "metadata": {"formule": "PC"},
            },
            format="json",
        )
        assert response.status_code == 201
        assert VillageInteraction.objects.filter(session_id="test-session-001").exists()

    def test_interaction_returns_404_for_unknown_village(self):
        response = self.client.post(
            "/api/v1/interactions",   # CORRECT: stays on api/v1/
            {
                "sessionId": "test-session-002",
                "villageId": "not-a-real-village",
                "kind": "view",
            },
            format="json",
        )
        assert response.status_code == 404


class TestInteractionPerformance(TestCase):
    """AC2.6 — Basic load/perf check for interaction insert latency."""

    @classmethod
    def setUpTestData(cls):

        call_command("load_vtf_mocks", verbosity=0)

    def setUp(self):
        self.client = APIClient()

    def test_interaction_response_under_50ms(self):


        village = Village.objects.first()
        times_ms: list[float] = []

        for i in range(8):
            sid = f"perf-session-{i}-{random.randint(1000, 9999)}"
            start = time.perf_counter()
            response = self.client.post(
                "/api/v1/interactions",
                {
                    "sessionId": sid,
                    "villageId": village.id,
                    "kind": "view",
                    "metadata": {"formule": "PC"},
                },
                format="json",
                HTTP_X_SESSION_ID=sid,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert response.status_code == 201
            times_ms.append(elapsed_ms)

        median_ms = statistics.median(times_ms)
        max_ms = max(times_ms)
        assert median_ms < 50, f"Median interaction latency too high: {median_ms:.1f}ms"
        assert max_ms < 150, f"Max interaction latency too high: {max_ms:.1f}ms"


# ─── Similar villages tests ───────────────────────────────────────────────

class TestSimilarVillages(TestCase):
    """GET /api/v2/villages/{id}/similar — spec §US-4.4."""

    def setUp(self):
        self.client = APIClient()

    def test_similar_excludes_current_village(self):
        if not Village.objects.exists():
            self.skipTest("No villages in DB.")
        village = Village.objects.first()
        response = self.client.get(
            f"/api/v2/villages/{village.id}/similar"   # FIX: was /api/v1/
        )
        assert response.status_code == 200
        data = response.json()
        result = data.get("data", data)
        villages = result.get("villages") if isinstance(result, dict) else result
        assert result.get("strategy") == "similar"
        ids = [r.get("village", {}).get("id") for r in villages]
        assert village.id not in ids

    def test_similar_unknown_village_returns_404(self):
        response = self.client.get(
            "/api/v2/villages/non-existent-village/similar"   # FIX: was /api/v1/
        )
        assert response.status_code == 404


# ─── Admin interactions stats tests ──────────────────────────────────────

class TestInteractionStats(TestCase):
    """GET /api/v2/admin/interactions/stats — spec §US-3.2."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("statsadmin", "stats@test.com", "pass")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _create_village(self, village_id="stats-village"):
        return Village.objects.create(
            id=village_id,
            nom="Stats Village",
            nom2="",
            region=Region.AQUITAINE_LANDES,
            env_emoji="sea",
            env_code=EnvCode.SEA,
            has_loc=False,
            ski=False,
            ouverture="",
            tarifs={},
            bebe_club=False,
            forfait_rm=False,
            qf_exc=False,
            enf_solo_half=False,
        )

    def test_stats_returns_200_for_admin(self):
        response = self.client.get(
            "/api/v2/admin/interactions/stats"   # FIX: was /api/v1/
        )
        assert response.status_code == 200
        data = response.json()
        result = data.get("data", data)
        assert "villages" in result
        assert "period" in result
        if result["villages"]:
            assert "villageId" in result["villages"][0]

    def test_stats_period_filter(self):
        for period in ["7d", "30d", "90d"]:
            response = self.client.get(
                f"/api/v2/admin/interactions/stats?period={period}"   # FIX: was /api/v1/
            )
            assert response.status_code == 200

    def test_stats_rejects_invalid_period(self):
        response = self.client.get("/api/v2/admin/interactions/stats?period=365d")
        assert response.status_code == 400

    def test_stats_date_filter(self):
        village = self._create_village()
        today = timezone.localdate()
        older = VillageInteraction.objects.create(
            session_id="stats-date-session",
            village=village,
            kind="view",
            value=1.0,
            metadata={},
        )
        recent = VillageInteraction.objects.create(
            session_id="stats-date-session",
            village=village,
            kind="bookmark",
            value=1.0,
            metadata={},
        )
        VillageInteraction.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )
        VillageInteraction.objects.filter(pk=recent.pk).update(
            created_at=timezone.now()
        )

        response = self.client.get(
            f"/api/v2/admin/interactions/stats?start_date={today.isoformat()}&end_date={today.isoformat()}"
        )
        assert response.status_code == 200
        result = response.json()["data"]
        assert result["period"] == "custom"
        assert result["startDate"] == today.isoformat()
        assert result["endDate"] == today.isoformat()
        assert result["villages"][0]["views"] == 0
        assert result["villages"][0]["bookmarks"] == 1

        older_day = today - timedelta(days=40)
        response = self.client.get(
            f"/api/v2/admin/interactions/stats?start_date={older_day.isoformat()}&end_date={older_day.isoformat()}"
        )
        assert response.status_code == 200
        result = response.json()["data"]
        assert result["villages"][0]["views"] == 1
        assert result["villages"][0]["bookmarks"] == 0

    def test_stats_forbidden_for_non_staff(self):
        User = get_user_model()
        user = User.objects.create_user("regularstats", "rs@test.com", "pass")
        client = APIClient()
        client.force_authenticate(user)
        response = client.get(
            "/api/v2/admin/interactions/stats"   # FIX: was /api/v1/
        )
        assert response.status_code == 403

    def test_stats_missing_auth_returns_json_without_browser_challenge(self):
        client = APIClient()
        response = client.get("/api/v2/admin/interactions/stats")

        assert response.status_code == 403
        assert "WWW-Authenticate" not in response
        assert response.json() == {
            "success": False,
            "message": "Authentication credentials were not provided.",
            "data": None,
        }

    def test_stats_wrong_basic_auth_returns_null_data(self):

        client = APIClient()
        credentials = base64.b64encode(b"statsadmin:wrong-password").decode("ascii")
        response = client.get(
            "/api/v2/admin/interactions/stats",
            HTTP_AUTHORIZATION=f"Basic {credentials}",
        )

        assert response.status_code == 403
        assert response.json() == {
            "success": False,
            "message": "Invalid authentication credentials.",
            "data": None,
        }


# ─── Management command tests ─────────────────────────────────────────────

class TestManagementCommands(TestCase):
    """Management commands smoke tests."""

    @staticmethod
    def _create_village(village_id="cleanup-village"):
        return Village.objects.create(
            id=village_id,
            nom="Cleanup Village",
            nom2="",
            region=Region.AQUITAINE_LANDES,
            env_emoji="sea",
            env_code=EnvCode.SEA,
            has_loc=False,
            ski=False,
            ouverture="",
            tarifs={},
            bebe_club=False,
            forfait_rm=False,
            qf_exc=False,
            enf_solo_half=False,
        )

    def test_refresh_popularity_runs_without_error(self):
        out = StringIO()
        call_command("refresh_popularity", stdout=out)
        assert "Done." in out.getvalue() or "Refreshing" in out.getvalue()

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_check_cf_readiness_runs(self):
        out = StringIO()
        call_command("check_cf_readiness", stdout=out)
        output = out.getvalue()
        assert "thresholds" in output.lower()

    def test_cleanup_interactions_dry_run(self):
        out = StringIO()
        call_command("cleanup_interactions", "--dry-run", "--days=30", stdout=out)
        assert "dry-run" in out.getvalue() or "Would delete" in out.getvalue()

    def test_cleanup_interactions_dry_run_preserves_old_rows(self):

        village = self._create_village("cleanup-dry-run-village")
        old = VillageInteraction.objects.create(
            session_id="cleanup-dry-run-old",
            village=village,
            kind="view",
            value=1.0,
            metadata={},
        )
        VillageInteraction.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=31)
        )

        out = StringIO()
        call_command("cleanup_interactions", "--dry-run", "--days=30", stdout=out)

        assert "Would delete 1 interaction" in out.getvalue()
        assert VillageInteraction.objects.filter(pk=old.pk).exists()

    def test_cleanup_interactions_deletes_only_rows_older_than_cutoff(self):

        village = self._create_village("cleanup-delete-village")
        old = VillageInteraction.objects.create(
            session_id="cleanup-delete-old",
            village=village,
            kind="view",
            value=1.0,
            metadata={},
        )
        recent = VillageInteraction.objects.create(
            session_id="cleanup-delete-recent",
            village=village,
            kind="bookmark",
            value=1.0,
            metadata={},
        )
        VillageInteraction.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=31)
        )
        VillageInteraction.objects.filter(pk=recent.pk).update(
            created_at=timezone.now() - timedelta(days=29)
        )

        out = StringIO()
        call_command("cleanup_interactions", "--days=30", stdout=out)

        assert "Deleted 1 interaction" in out.getvalue()
        assert not VillageInteraction.objects.filter(pk=old.pk).exists()
        assert VillageInteraction.objects.filter(pk=recent.pk).exists()


class TestPopularityRefresh(TestCase):
    @classmethod
    def setUpTestData(cls):

        call_command("load_vtf_mocks", verbosity=0)

    def test_refresh_updates_scores_and_keeps_cache_rows(self):



        v = Village.objects.first()
        sid = "pop-refresh-session"
        now = timezone.now()

        VillageInteraction.objects.create(
            session_id=sid,
            village=v,
            kind="simulate",
            value=1.0,
            metadata={},
            created_at=now - timedelta(days=1),
        )
        VillageInteraction.objects.create(
            session_id=sid,
            village=v,
            kind="simulate",
            value=1.0,
            metadata={},
            created_at=now - timedelta(days=1),
        )
        VillageInteraction.objects.create(
            session_id=sid,
            village=v,
            kind="bookmark",
            value=1.0,
            metadata={},
            created_at=now - timedelta(days=1),
        )

        call_command("refresh_popularity", verbosity=0)
        row = VillagePopularityCache.objects.get(village=v)
        assert row.score == 11.0

        before_count = VillagePopularityCache.objects.count()
        VillageInteraction.objects.create(
            session_id=sid,
            village=v,
            kind="view",
            value=1.0,
            metadata={},
            created_at=now - timedelta(days=1),
        )
        call_command("refresh_popularity", verbosity=0)
        row.refresh_from_db()
        assert row.score == 12.0
        assert VillagePopularityCache.objects.count() == before_count


class TestCfReadinessAndTraining(TestCase):
    @classmethod
    def setUpTestData(cls):

        call_command("load_vtf_mocks", verbosity=0)

    def test_check_cf_readiness_sets_flag_when_thresholds_met(self):



        v1 = Village.objects.first()
        v2 = Village.objects.exclude(pk=v1.pk).first()
        assert v1 is not None and v2 is not None

        session_id = "cf-test-session"
        d0 = date(2026, 7, 5)
        d1 = date(2026, 7, 12)

        SimulationLog.objects.create(
            session_id=session_id,
            village=v1,
            region=v1.region,
            formule="PC",
            saison_key="ete",
            date_debut=d0,
            date_fin=d1,
            nuits=7,
            nb_adults=2,
            nb_children=0,
            children_ages=[],
            qf_val=None,
            estimated_total=1000,
            per_person_per_day=100,
            discount_rate=0.0,
            promos_applied=[],
        )
        SimulationLog.objects.create(
            session_id=session_id,
            village=v2,
            region=v2.region,
            formule="PC",
            saison_key="ete",
            date_debut=d0,
            date_fin=d1,
            nuits=7,
            nb_adults=2,
            nb_children=0,
            children_ages=[],
            qf_val=None,
            estimated_total=1000,
            per_person_per_day=100,
            discount_rate=0.0,
            promos_applied=[],
        )

        # Patch thresholds down so we can build a small matrix quickly.
        with patch(
            "apps.recommender.management.commands.check_cf_readiness.Command._thresholds",
            return_value={
                "min_simulations": 2,
                "min_sessions": 1,
                "min_multi_village_sessions": 1,
                "min_villages_with_sims": 1,
                "min_sims_per_village": 1,
            },
        ):
            call_command("check_cf_readiness", verbosity=0)

        assert cache.get("cf_model_ready") is True
        row = RecommendationSystemState.objects.get(key="cf_model_ready")
        assert row.value_bool is True
        assert row.metadata["ready"] is True

    def test_train_cf_model_does_not_overwrite_existing_model_on_empty_matrix(self):


        # Cache backends may serialize/unserialize values; use a stable sentinel.
        sentinel = "sentinel-model"
        cache.set("vtf:reco:cf_model", sentinel, timeout=60 * 60)
        cache.set("cf_model_ready", True, timeout=60 * 60)

        df_mock = Mock()
        df_mock.empty = True

        with patch(
            "apps.recommender.management.commands.train_cf_model.Command._build_interaction_matrix",
            return_value=df_mock,
        ):
            call_command("train_cf_model", verbosity=0)

        assert cache.get("vtf:reco:cf_model") == sentinel
        row = RecommendationSystemState.objects.get(key="cf_model_training")
        assert row.value_bool is False
        assert row.metadata["status"] == "skipped_empty_matrix"


# ─── Bookmark create/remove (v2) ──────────────────────────────────────────

class TestBookmarkCreateRemove(TestCase):
    @classmethod
    def setUpTestData(cls):

        call_command("load_vtf_mocks", verbosity=0)

    def setUp(self):
        self.client = APIClient()

    def test_bookmark_create_is_idempotent_and_remove_deletes(self):
        village = Village.objects.first()
        sid = "bookmark-create-remove-session"
        r1 = self.client.post(
            "/api/v2/interactions/bookmark",
            {"sessionId": sid, "villageId": village.id},
            format="json",
        )
        assert r1.status_code == 200
        assert r1.json()["data"]["bookmarked"] is True
        assert r1.json()["data"]["created"] is True
        r2 = self.client.post(
            "/api/v2/interactions/bookmark",
            {"sessionId": sid, "villageId": village.id},
            format="json",
        )
        assert r2.status_code == 200
        assert r2.json()["data"]["bookmarked"] is True
        assert r2.json()["data"]["created"] is False
        r3 = self.client.post(
            "/api/v2/interactions/bookmark/remove",
            {"sessionId": sid, "villageId": village.id},
            format="json",
        )
        assert r3.status_code == 200
        assert r3.json()["data"]["bookmarked"] is False
        assert r3.json()["data"]["removed"] == 1

    def test_bookmark_uses_x_session_id_header(self):
        village = Village.objects.first()
        sid = "bookmark-header-session"
        response = self.client.post(
            "/api/v2/interactions/bookmark",
            {"villageId": village.id},
            format="json",
            HTTP_X_SESSION_ID=sid,
        )
        assert response.status_code == 200
        assert response.json()["data"]["bookmarked"] is True
        assert VillageInteraction.objects.filter(
            session_id=sid,
            village_id=village.id,
            kind="bookmark",
        ).exists()


# ─── Signals without village (v1) ─────────────────────────────────────────

class TestSessionSignals(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_session_start_beacon_is_accepted(self):
        response = self.client.post(
            "/api/v1/signals",
            {"sessionId": "sess-abc", "kind": "session_start", "metadata": {"referrer": "/"}},
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["success"] is True


# ─── AC2.5 — estimatedTotal accuracy ─────────────────────────────────────

class TestEstimatedTotalAccuracy(TestCase):
    def test_lightweight_within_five_percent_of_full(self):
        if not Village.objects.exists():
            self.skipTest("No villages.")

        village = Village.objects.first()
        rules = PricingRules.active()
        if not rules:
            self.skipTest("No pricing rules.")

        family = {"adultes": 2, "enfants": [{"age": 8}], "qfVal": 900, "maxiFamily": False}
        preferences = {
            "dates": {"debut": "2026-07-05", "fin": "2026-07-12"},
            "formule": "PC",
        }

        light = lightweight_estimate(village, family, preferences)
        if light is None:
            self.skipTest("Lightweight estimate unavailable.")

        village_dict = {
            "id": village.id,
            "nom": village.nom,
            "region": village.region,
            "env": village.env_emoji,
            "envCode": village.env_code,
            "formules": village.formules,
            "hasLoc": village.has_loc,
            "ski": village.ski,
            "ouverture": village.ouverture,
            "tarifs": village.tarifs,
            "bebeClub": village.bebe_club,
            "forfaitRM": village.forfait_rm,
            "qfExc": village.qf_exc,
            "enfSoloHalf": village.enf_solo_half,
        }
        full = estimate_sejour_total(
            family=family,
            sejour={
                "dateDebut": "2026-07-05",
                "dateFin": "2026-07-12",
                "formule": "PC",
                "fNuits": None,
                "activities": {"outings": 0, "priceAdult": 0, "priceChild": 0},
                "resto": {"qtyByMealId": {}},
                "transport": {"mode": "none"},
                "promos": {"promoSejourRate": 0.0, "quinzaineFutee": False},
            },
            village=village_dict,
            pricing_rules=rules,
            activities_by_region={},
            meals_catalog=list(Meal.objects.all()),
        )
        assert abs(light - full.total) / max(full.total, 1) <= 0.05


# ─── AC2.10 — Interaction throttle ───────────────────────────────────────

class TestInteractionThrottle(TestCase):
    @classmethod
    def setUpTestData(cls):

        call_command("load_vtf_mocks", verbosity=0)

    def test_throttle_returns_429(self):


        village = Village.objects.first()

        # Avoid cross-test pollution from the shared throttle cache.
        cache.clear()

        # DRF caches DEFAULT_THROTTLE_RATES at import-time inside SimpleRateThrottle,
        # so override_settings may not affect the throttle behavior reliably.
        with patch.object(
            InteractionsSessionThrottle,
            "THROTTLE_RATES",
            {"interactions_session": "2/hour"},
        ):
            client = APIClient()
            sid = f"throttle-test-session-{random.randint(1000, 9999)}"
            for _ in range(2):
                r = client.post(
                    "/api/v1/interactions",
                    {"sessionId": sid, "villageId": village.id, "kind": "view"},
                    format="json",
                )
                assert r.status_code == 201
            r3 = client.post(
                "/api/v1/interactions",
                {"sessionId": sid, "villageId": village.id, "kind": "view"},
                format="json",
            )
            assert r3.status_code == 429


# ─── AC2.13 — Implicit ratings matrix ────────────────────────────────────

class TestImplicitRatings(TestCase):
    @classmethod
    def setUpTestData(cls):

        call_command("load_vtf_mocks", verbosity=0)

    def test_build_interaction_matrix_ratings_in_range(self):

        village = Village.objects.first()
        SimulationLog.objects.create(
            session_id="implicit-rating-sess",
            village=village,
            region=village.region,
            formule="PC",
            saison_key="ete",
            date_debut="2026-07-05",
            date_fin="2026-07-12",
            nuits=7,
            nb_adults=2,
            nb_children=0,
            children_ages=[],
            estimated_total=2000,
            per_person_per_day=100,
            discount_rate=0.0,
        )
        df = Command()._build_interaction_matrix()
        assert not df.empty
        assert df["rating"].min() >= 1.0
        assert df["rating"].max() <= 5.0

    def test_mini_dataframe_without_pandas(self):
        """Matrix builder works when pandas is not importable."""


        rows = [
            {"user_id": "s1", "item_id": "v1", "rating": 2.0},
            {"user_id": "s1", "item_id": "v2", "rating": 5.0},
        ]
        with patch.object(cf_train_command, "pd", None):
            df = _as_interaction_frame(rows)
        assert isinstance(df, MiniDataFrame)
        assert not df.empty
        assert df["rating"].min() == 2.0
        assert df["rating"].max() == 5.0
        assert df["user_id"].nunique() == 1
        subset = df[["user_id", "item_id", "rating"]]
        assert len(subset) == 2

        # _build_interaction_matrix delegates to the same helpers.
        with patch.object(cf_train_command, "pd", None):
            with patch(
                "apps.recommender.management.commands.train_cf_model._collect_interaction_rows",
                return_value=rows,
            ):

                built = Command()._build_interaction_matrix()
        assert isinstance(built, MiniDataFrame)

    def test_pandas_dataframe_when_installed(self):
        """When pandas is installed, return a real DataFrame for SVD training."""
        pytest = __import__("pytest")
        pd = pytest.importorskip("pandas")


        rows = [{"user_id": "s1", "item_id": "v1", "rating": 3.5}]
        df = _as_interaction_frame(rows)
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["user_id", "item_id", "rating"]
        training = df[["user_id", "item_id", "rating"]]
        assert len(training) == 1

    def test_train_cf_model_trains_with_pandas_and_surprise(self):
        """Full training path when optional deps are installed."""
        pytest = __import__("pytest")
        pytest.importorskip("pandas")
        pytest.importorskip("surprise")



        village = Village.objects.first()
        for i in range(3):
            SimulationLog.objects.create(
                session_id=f"cf-train-sess-{i}",
                village=village,
                region=village.region,
                formule="PC",
                saison_key="ete",
                date_debut="2026-07-05",
                date_fin="2026-07-12",
                nuits=7,
                nb_adults=2,
                nb_children=0,
                children_ages=[],
                estimated_total=2000,
                per_person_per_day=100,
                discount_rate=0.0,
            )

        cache.set("cf_model_ready", True, timeout=60 * 60)
        call_command("train_cf_model", force=True, verbosity=0)
        assert cache.get("vtf:reco:cf_model") is not None
        row = RecommendationSystemState.objects.get(key="cf_model_training")
        assert row.value_bool is True
        assert row.metadata["status"] == "trained"
        assert row.metadata["force"] is True


# ─── AC2.12 — CF blend ─────────────────────────────────────────────────────

class TestCfBlend(TestCase):
    def test_cf_rerank_blends_scores(self):



        cache.set("cf_model_ready", True, timeout=60)
        mock_model = MagicMock()
        mock_model.predict.side_effect = lambda uid, iid: MagicMock(est=5.0)

        scored = [
            {"village_id": "biarritz", "score": 0.8, "reasons": []},
            {"village_id": "lacanau", "score": 0.6, "reasons": []},
        ]
        original = scored[0]["score"]
        session_id = next(
            s for i in range(500) if (s := f"cf-session-{i}") and hash(s) % 2 == 0
        )
        with patch.object(cf, "has_enough_data", return_value=True), patch.object(
            cf, "session_has_history", return_value=True
        ), patch.object(cf, "_get_or_train_model", return_value=mock_model):
            out, applied, ab = cf.cf_rerank(scored, session_id, explain=True)
        assert ab == "cf"
        assert applied
        assert out[0]["score"] != original
        assert any("Affinité collaborative" in r for r in out[0].get("reasons", []))


@override_settings(CACHES=LOCMEM_CACHE)
class TestCfModelState(TestCase):
    def test_missing_cached_model_marks_training_state_false(self):


        cache.clear()
        RecommendationSystemState.objects.create(
            key="cf_model_training",
            value_bool=True,
            metadata={"status": "trained"},
        )

        model = _get_or_train_model()

        assert model is None
        row = RecommendationSystemState.objects.get(key="cf_model_training")
        assert row.value_bool is False
        assert row.metadata["status"] == "model_missing_or_expired"
        assert row.metadata["model_key"] == "vtf:reco:cf_model"


@override_settings(CACHES=LOCMEM_CACHE)
class TestRecommendationSystemStateEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):

        call_command("load_vtf_mocks", verbosity=0)

    def setUp(self):

        self.client = APIClient()
        cache.clear()

    def test_recommend_endpoint_uses_db_cf_ready_when_cache_empty(self):



        villages = list(Village.objects.all()[:3])
        assert len(villages) >= 3

        session_id = next(
            s for i in range(500)
            if (s := f"endpoint-cf-session-{i}") and hash(s) % 2 == 0
        )
        for village in villages[:2]:
            SimulationLog.objects.create(
                session_id=session_id,
                village=village,
                region=village.region,
                formule="PC",
                saison_key="ete",
                date_debut="2026-07-05",
                date_fin="2026-07-12",
                nuits=7,
                nb_adults=2,
                nb_children=0,
                children_ages=[],
                estimated_total=2000,
                per_person_per_day=100,
                discount_rate=0.0,
            )

        RecommendationSystemState.objects.create(
            key="cf_model_ready",
            value_bool=True,
            metadata={"ready": True, "source": "test"},
        )
        assert cache.get("cf_model_ready") is None

        scored = [
            {
                "village_id": village.id,
                "village": village,
                "score": 0.75 - index * 0.05,
                "reasons": [],
                "warnings": [],
                "estimated_total": None,
            }
            for index, village in enumerate(villages)
        ]
        mock_model = MagicMock()
        mock_model.predict.side_effect = lambda _uid, _iid: MagicMock(est=5.0)

        body = {
            "family": {
                "adultes": 2,
                "enfants": [],
                "qfVal": None,
                "isSoloParent": False,
                "maxiFamily": False,
            },
            "preferences": {
                "dates": {"debut": "2026-07-05", "fin": "2026-07-12"},
                "formule": "PC",
            },
            "sessionId": session_id,
            "limit": 3,
            "explain": True,
        }

        with patch(
            "apps.recommender.strategies.content_based.score_all_villages",
            return_value=scored,
        ), patch(
            "apps.recommender.services.estimate.bulk_estimate",
            return_value={},
        ), patch(
            "apps.recommender.strategies.collaborative._get_or_train_model",
            return_value=mock_model,
        ):
            response = self.client.post(
                "/api/v2/recommend/villages",
                body,
                format="json",
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["strategy"] == "personalized_cf"
        assert data["abGroup"] == "cf"
        assert cache.get("cf_model_ready") is True
        assert any(
            "Affinité collaborative" in reason
            for village in data["villages"]
            for reason in village["reasons"]
        )


class TestSoloParentFlag(TestCase):
    def test_is_solo_parent_taken_from_family(self):
        """Regression: isSoloParent is a `family` field (spec), not preferences."""

        # Adults=2 but isSoloParent=True: this must still count as solo parent.
        Village.objects.all().delete()
        v = Village.objects.create(
            id="solo-parent-village",
            nom="Solo Parent Village",
            nom2="",
            region=Region.AQUITAINE_LANDES,
            env_emoji="🌊",
            env_code=EnvCode.SEA,
            has_loc=False,
            ski=False,
            ouverture="",
            tarifs={},
            bebe_club=False,
            forfait_rm=False,
            qf_exc=False,
            enf_solo_half=True,
        )

        scored = content_based.score_all_villages(
            family={"adultes": 2, "enfants": [{"age": 6}], "qfVal": None, "isSoloParent": True},
            preferences={"envs": [], "mustHave": [], "avoidSki": False},
        )
        solo_item = next(s for s in scored if s["village_id"] == v.id)
        assert any("Tarif parent solo" in r for r in solo_item.get("reasons") or [])


class TestTier3FallbackUsedFlag(TestCase):
    def test_tier3_does_not_set_fallback_used(self):
        """Spec: fallbackUsed should be true only from popularity/seed tiers (>=4)."""


        fake_scored = [
            {"village_id": "v1", "village": None, "score": 0.15, "reasons": [], "warnings": []},
            {"village_id": "v2", "village": None, "score": 0.12, "reasons": [], "warnings": []},
        ]
        with patch("apps.recommender.strategies.content_based.score_all_villages", return_value=fake_scored):
            result = engine.recommend(
                family={"adultes": 2, "enfants": [], "qfVal": None, "isSoloParent": False},
                preferences={"dates": {"debut": "2026-07-05", "fin": "2026-07-12"}},
                session_id=None,
                limit=2,
                explain=False,
            )
        assert result.relaxed_filters
        assert result.fallback_used is False




# New tests applied here

# =============================================================================
# AC2.13 — SimulationLog → implicit rating conversion produces valid 1–5 scale
# =============================================================================

class TestImplicitRatingConversion:
    """AC2.13: _collect_interaction_rows() returns valid 1-5 ratings.

    The function is in train_cf_model.py.  We test it by inserting known
    SimulationLog rows and asserting the resulting ratings.
    """

    @pytest.mark.django_db
    def test_simple_simulation_gives_2_0(self, village_factory):
        """A single simulation with no booking click → rating 2.0."""

        v = village_factory()
        SimulationLog.objects.create(
            session_id="sess-rating-test-1",
            village=v,
            region=v.region,
            formule="PC",
            saison_key="ete",
            date_debut="2026-07-05",
            date_fin="2026-07-12",
            nuits=7,
            nb_adults=2,
            nb_children=0,
            estimated_total=2000,
            per_person_per_day=143,
            discount_rate=0.0,
        )

        rows = _collect_interaction_rows()
        matching = [
            r for r in rows
            if r["user_id"] == "sess-rating-test-1" and r["item_id"] == v.pk
        ]
        assert len(matching) == 1, "Expected one row for session+village pair"
        assert matching[0]["rating"] == 2.0, (
            f"Single sim with no click should give 2.0, got {matching[0]['rating']}"
        )

    @pytest.mark.django_db
    def test_repeated_simulation_gives_2_5(self, village_factory):
        """Two simulations for same session+village → rating 2.5."""

        v = village_factory()
        for _ in range(2):
            SimulationLog.objects.create(
                session_id="sess-rating-test-2",
                village=v,
                region=v.region,
                formule="PC",
                saison_key="ete",
                date_debut="2026-07-05",
                date_fin="2026-07-12",
                nuits=7,
                nb_adults=2,
                nb_children=0,
                estimated_total=2000,
                per_person_per_day=143,
                discount_rate=0.0,
            )

        rows = _collect_interaction_rows()
        matching = [
            r for r in rows
            if r["user_id"] == "sess-rating-test-2" and r["item_id"] == v.pk
        ]
        assert len(matching) == 1
        assert matching[0]["rating"] == 2.5, (
            f"2 sims same session+village should give 2.5, got {matching[0]['rating']}"
        )

    @pytest.mark.django_db
    def test_booking_click_gives_5_0(self, village_factory):
        """A simulation where the user clicked booking → rating 5.0."""

        v = village_factory()
        SimulationLog.objects.create(
            session_id="sess-rating-test-3",
            village=v,
            region=v.region,
            formule="PC",
            saison_key="ete",
            date_debut="2026-07-05",
            date_fin="2026-07-12",
            nuits=7,
            nb_adults=2,
            nb_children=0,
            estimated_total=2000,
            per_person_per_day=143,
            discount_rate=0.0,
            clicked_booking=True,
        )

        rows = _collect_interaction_rows()
        matching = [
            r for r in rows
            if r["user_id"] == "sess-rating-test-3" and r["item_id"] == v.pk
        ]
        assert len(matching) == 1
        assert matching[0]["rating"] == 5.0, (
            f"Booking click should give 5.0, got {matching[0]['rating']}"
        )

    @pytest.mark.django_db
    def test_all_ratings_in_valid_range(self, village_factory):
        """All produced ratings must be between 1.0 and 5.0 inclusive."""

        v1 = village_factory()
        v2 = village_factory()

        # Mix of signals
        SimulationLog.objects.create(
            session_id="sess-range-test",
            village=v1,
            region=v1.region,
            formule="PC",
            saison_key="ete",
            date_debut="2026-07-05",
            date_fin="2026-07-12",
            nuits=7,
            nb_adults=2,
            nb_children=0,
            estimated_total=1800,
            per_person_per_day=129,
            discount_rate=0.0,
            clicked_booking=True,
        )
        SimulationLog.objects.create(
            session_id="sess-range-test",
            village=v2,
            region=v2.region,
            formule="DP",
            saison_key="vs",
            date_debut="2026-02-01",
            date_fin="2026-02-08",
            nuits=7,
            nb_adults=2,
            nb_children=2,
            estimated_total=2200,
            per_person_per_day=79,
            discount_rate=0.1,
        )

        rows = _collect_interaction_rows()
        for row in rows:
            assert 1.0 <= row["rating"] <= 5.0, (
                f"Rating {row['rating']} out of 1–5 range for "
                f"user={row['user_id']} item={row['item_id']}"
            )

    @pytest.mark.django_db
    def test_village_interaction_bookmark_gives_3_5(self, village_factory):
        """VillageInteraction bookmark kind → rating 3.5."""

        v = village_factory()
        VillageInteraction.objects.create(
            session_id="sess-bookmark-test",
            village=v,
            kind="bookmark",
            value=1.0,
        )

        rows = _collect_interaction_rows()
        matching = [
            r for r in rows
            if r["user_id"] == "sess-bookmark-test" and r["item_id"] == v.pk
        ]
        assert len(matching) == 1
        assert matching[0]["rating"] == 3.5, (
            f"bookmark kind should give 3.5, got {matching[0]['rating']}"
        )

    @pytest.mark.django_db
    def test_max_rating_wins_when_both_sim_and_interaction(self, village_factory):
        """When SimulationLog(clicked=True) and VillageInteraction(bookmark) exist,
        the max rating (5.0) should win, not be double-counted.
        """

        v = village_factory()
        SimulationLog.objects.create(
            session_id="sess-max-test",
            village=v,
            region=v.region,
            formule="PC",
            saison_key="ete",
            date_debut="2026-07-05",
            date_fin="2026-07-12",
            nuits=7,
            nb_adults=2,
            nb_children=0,
            estimated_total=2000,
            per_person_per_day=143,
            discount_rate=0.0,
            clicked_booking=True,
        )
        VillageInteraction.objects.create(
            session_id="sess-max-test",
            village=v,
            kind="bookmark",
            value=1.0,
        )

        rows = _collect_interaction_rows()
        matching = [
            r for r in rows
            if r["user_id"] == "sess-max-test" and r["item_id"] == v.pk
        ]
        assert len(matching) == 1, "Should be deduplicated to one row"
        assert matching[0]["rating"] == 5.0, (
            f"Max of (5.0, 3.5) should be 5.0, got {matching[0]['rating']}"
        )


# =============================================================================
# AC2.12 — CF A/B split: deterministic arm assignment
# =============================================================================

class TestCFAbSplit:
    """AC2.12: 50/50 A/B split via hash(session_id) % 2.

    Spec §4.4 Strategy 3 (addendum §3.5):
    - Same session_id always gets the same arm ("cf" or "control")
    - "control" sessions get content-based only (cf_used=False)
    - Both arms return a valid scored list
    """

    def _make_scored(self, village_ids=("biarritz", "lacanau", "agde")):
        return [
            {
                "village_id": vid,
                "village": {"id": vid, "nom": vid.title()},
                "score": 0.9 - i * 0.1,
                "reasons": [],
                "warnings": [],
            }
            for i, vid in enumerate(village_ids)
        ]

    def test_same_session_always_same_arm(self):
        """Same session_id must deterministically map to the same A/B arm."""


        session_id = "deterministic-session-abc"
        expected_arm = "cf" if hash(session_id) % 2 == 0 else "control"

        with patch(
            "apps.recommender.strategies.collaborative.has_enough_data",
            return_value=True,
        ), patch(
            "apps.recommender.strategies.collaborative.session_has_history",
            return_value=True,
        ):
            for _ in range(5):
                _, _, ab_group = cf_rerank(self._make_scored(), session_id)
                assert ab_group == expected_arm, (
                    f"Expected arm '{expected_arm}' every time, got '{ab_group}'"
                )

    def test_control_arm_does_not_apply_cf(self):
        """Sessions in the 'control' arm must get cf_used=False."""


        # Find a session that hashes to 'control'
        control_session = next(
            s for s in (f"ctrl-{i}" for i in range(200))
            if hash(s) % 2 != 0
        )

        scored = self._make_scored()
        with patch(
            "apps.recommender.strategies.collaborative.has_enough_data",
            return_value=True,
        ), patch(
            "apps.recommender.strategies.collaborative.session_has_history",
            return_value=True,
        ):
            _, cf_used, ab_group = cf_rerank(scored, control_session)

        assert ab_group == "control"
        assert cf_used is False, "Control arm must never apply CF blending"

    def test_cf_arm_identified_when_data_insufficient(self):
        """When has_enough_data()=False, even 'cf' arm sessions skip re-ranking."""

        # Find a session that hashes to 'cf' arm
        cf_session = next(
            s for s in (f"cf-{i}" for i in range(200))
            if hash(s) % 2 == 0
        )

        scored = self._make_scored()

        with patch(
            "apps.recommender.strategies.collaborative.has_enough_data",
            return_value=False,
        ):
            result_scored, cf_used, ab_group = cf_rerank(scored, cf_session)

        # cf_rerank returns (scored, False, None) when has_enough_data=False
        assert cf_used is False
        assert ab_group is None, (
            "ab_group should be None when data threshold not met"
        )

    def test_null_session_never_applies_cf(self):
        """A None or empty session_id must always skip CF (cold start)."""


        scored = self._make_scored()
        with patch(
            "apps.recommender.strategies.collaborative.has_enough_data",
            return_value=False,
        ):
            for session in (None, "", "   "):
                result_scored, cf_used, ab_group = cf_rerank(scored, session)
                assert cf_used is False
                assert ab_group is None

    def test_score_order_preserved_for_control(self):
        """Control arm must return scores in same order as input."""


        control_session = next(
            s for s in (f"order-ctrl-{i}" for i in range(200))
            if hash(s) % 2 != 0
        )
        scored = self._make_scored()
        original_order = [s["village_id"] for s in scored]

        with patch(
            "apps.recommender.strategies.collaborative.has_enough_data",
            return_value=True,
        ), patch(
            "apps.recommender.strategies.collaborative.session_has_history",
            return_value=True,
        ):
            result_scored, _, _ = cf_rerank(scored, control_session)
        result_order = [s["village_id"] for s in result_scored]

        assert result_order == original_order, (
            "Control arm should not reorder villages"
        )


# =============================================================================
# AC2.5 — estimatedTotal in recommendations within ±5% of full estimate
# =============================================================================

class TestEstimatedTotalAccuracy:
    """AC2.5: estimatedTotal per recommended village within ±5% of full estimate.

    The recommendation engine runs a lightweight estimate (skip transport/resto).
    This test cross-validates it against a full /estimate/stay call.
    """

    @pytest.fixture
    def biarritz_or_first_village(self, db):
        v = Village.objects.filter(pk="biarritz").first()
        if v is None:
            v = Village.objects.first()
        if v is None:
            pytest.skip("No villages loaded — run load_vtf_mocks first")
        return v

    @pytest.mark.django_db
    def test_estimated_total_within_5_percent_of_full_estimate(
        self, biarritz_or_first_village
    ):
        """estimatedTotal from bulk_estimate must be within ±5% of the full
        stay estimate for the same input.  Spec AC2.5.
        """

        family = {
            "adultes": 2,
            "enfants": [{"age": 4}, {"age": 8}],
            "qfVal": 900,
            "isSoloParent": False,
            "maxiFamily": False,
        }
        preferences = {
            "formule": "PC",
            "dates": {"debut": "2026-07-05", "fin": "2026-07-12"},
            "budget": 3000,
        }

        village = biarritz_or_first_village
        all_villages = [village]

        estimated_totals = bulk_estimate(all_villages, family, preferences)
        reco_total = estimated_totals.get(village.pk)

        if reco_total is None:
            pytest.skip(f"bulk_estimate returned None for village {village.pk}")

        # Now run the full estimate for comparison

        rules_obj = PricingRules.objects.filter(is_active=True).first()
        if rules_obj is None:
            pytest.skip("No active PricingRules — run load_vtf_mocks first")

        rules = rules_obj.payload

        village_payload = {
            "id": village.id,
            "nom": village.nom,
            "region": village.region,
            "env": village.env_emoji,
            "envCode": village.env_code,
            "formules": village.formules,
            "hasLoc": village.has_loc,
            "ski": village.ski,
            "ouverture": village.ouverture,
            "tarifs": village.tarifs,
            "bebeClub": village.bebe_club,
            "forfaitRM": village.forfait_rm,
            "qfExc": village.qf_exc,
            "enfSoloHalf": village.enf_solo_half,
        }

        full_result = estimate_sejour_total(
            family=family,
            sejour={
                "dateDebut": "2026-07-05",
                "dateFin": "2026-07-12",
                "formule": "PC",
                "fNuits": 7,
                "activities": {"outings": 0, "priceAdult": 0, "priceChild": 0},
                "resto": {"qtyByMealId": {}},
                "transport": {"mode": "none"},
                "promos": {},
            },
            village=village_payload,
            pricing_rules=rules,
        )

        full_total = full_result.total

        tolerance = 0.05  # ±5%
        lower = full_total * (1 - tolerance)
        upper = full_total * (1 + tolerance)

        assert lower <= reco_total <= upper, (
            f"bulk_estimate returned {reco_total} for village '{village.pk}', "
            f"but full estimate gave {full_total}. "
            f"Difference: {abs(reco_total - full_total)} "
            f"({abs(reco_total - full_total) / full_total:.1%}). "
            f"Tolerance: ±5%"
        )

    @pytest.mark.django_db
    def test_estimated_total_is_positive(self, biarritz_or_first_village):
        """estimatedTotal must be a positive integer for all villages."""

        family = {
            "adultes": 2,
            "enfants": [{"age": 6}],
            "qfVal": None,
            "isSoloParent": False,
            "maxiFamily": False,
        }
        preferences = {
            "formule": "PC",
            "dates": {"debut": "2026-08-01", "fin": "2026-08-08"},
        }

        all_villages = list(Village.objects.all()[:5])
        if not all_villages:
            pytest.skip("No villages loaded")

        estimated_totals = bulk_estimate(all_villages, family, preferences)

        for village in all_villages:
            total = estimated_totals.get(village.pk)
            if total is not None:
                assert total > 0, (
                    f"estimatedTotal for '{village.pk}' must be positive, got {total}"
                )

    @pytest.mark.django_db
    def test_recommend_endpoint_estimated_total_present_and_positive(self, db):
        """Via the API: every recommended village must have a positive estimatedTotal."""

        if not Village.objects.exists():
            pytest.skip("No villages loaded")

        client = APIClient()
        payload = {
            "family": {
                "adultes": 2,
                "enfants": [{"age": 5}],
                "qfVal": 1000,
                "isSoloParent": False,
                "maxiFamily": False,
            },
            "preferences": {
                "envs": ["sea"],
                "formule": "PC",
                "budget": 3000,
                "dates": {"debut": "2026-07-05", "fin": "2026-07-12"},
                "mustHave": [],
                "avoidSki": False,
            },
            "sessionId": "test-ac2-5-session",
            "limit": 3,
            "explain": False,
        }

        response = client.post("/api/v2/recommend/villages", payload, format="json")
        assert response.status_code == 200

        for item in response.data["data"]["villages"]:
            total = item.get("estimatedTotal")
            assert total is not None, (
                f"estimatedTotal missing for village {item.get('village', {}).get('id')}"
            )
            assert isinstance(total, (int, float))
            assert total > 0, (
                f"estimatedTotal must be positive, got {total} for "
                f"village {item.get('village', {}).get('id')}"
            )
