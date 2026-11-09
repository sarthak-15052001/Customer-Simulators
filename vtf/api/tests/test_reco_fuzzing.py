"""Recommendation fuzzing — AC-2.1 (100 random inputs, never empty)."""
from __future__ import annotations

import random
from unittest.mock import patch

from apps.recommender.views import RecommendVillagesView
from django.test import TestCase
from rest_framework.test import APIClient

from tests.test_phase2 import _random_reco_input


class TestRecoFuzzing(TestCase):
    def test_never_empty_100_inputs(self):


        random.seed(99)
        client = APIClient()
        with patch.object(RecommendVillagesView, "throttle_classes", []):
            for i in range(100):
                body = _random_reco_input()
                response = client.post("/api/v2/recommend/villages", body, format="json")
                assert response.status_code == 200, f"#{i} status {response.status_code}"
                data = response.json()
                villages = data.get("data", {}).get("villages") or data.get("villages") or []
                assert len(villages) >= 1, f"#{i} empty villages"
