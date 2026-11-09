"""Pytest tests for dual-season scrape URL resolution.
...
"""
from __future__ import annotations

import pytest

from apps.tariff_scraper.services.village_urls import (
    DUAL_SEASON_VILLAGE_IDS,
    SCRAPE_SOURCE_SUMMER,
    SCRAPE_SOURCE_WINTER,
    get_village_scrape_urls,
    get_village_url,
)

EXPECTED_DUAL_SEASON_IDS = {
    "karellis",
    "montricher-albanne",
    "la-plagne",
    "le-sauze",
    "arvieux",
    "savines",
    "saint-sauves",
    "metabief",
    "soultzeren",
    "font-durle",
    "areches",
    "chamonix",
}

def test_dual_season_village_returns_two_urls():
    urls = get_village_scrape_urls("chamonix")
    assert len(urls) == 2
    ...

@pytest.mark.parametrize("village_id", sorted(EXPECTED_DUAL_SEASON_IDS))
def test_all_dual_season_ids_resolve_to_two_urls(village_id):
    urls = get_village_scrape_urls(village_id)
    assert len(urls) == 2
    ...