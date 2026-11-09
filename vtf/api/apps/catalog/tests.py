"""Catalog smoke tests.

Run with:
    make test                        # all tests
    pytest apps/catalog/tests.py -v  # just this file

These guard the Phase 1 invariants: fixtures load, the singleton constraint
holds, and the data shape downstream services rely on (env_code, tarifs) is
intact. Expand with mock-parity, choice-coverage, and idempotence cases as
described in vtf/api/docs/01-frontend-source-of-truth.md.
"""
from __future__ import annotations

import pytest
from django.core.management import call_command
from django.db import IntegrityError

from apps.catalog.models import (
    Activity,
    Animation,
    Attraction,
    EnvCode,
    Formula,
    FuelOption,
    MarketingSeasonEnvironment,
    MarketingSeasons,
    Meal,
    PricingRules,
    Promo,
    Village,
    VillageClubsEte,
    VillageInfra,
)
from apps.catalog.serializers import FormulaSerializer

CATALOG_FIXTURES = [
    "pricing_rules",
    "villages",
    "activities",
    "meals",
    "fuel_options",
    "promos",
    "marketing_seasons",
    "marketing_season_environments",
]


@pytest.fixture
def loaded_catalog(db):
    call_command("loaddata", *CATALOG_FIXTURES, verbosity=0)


def test_fixture_counts(loaded_catalog):
    assert Village.objects.count() == 32
    assert Attraction.objects.count() == 26
    assert Activity.objects.count() == 89
    assert Animation.objects.count() == 4
    assert VillageInfra.objects.count() == 1
    assert VillageClubsEte.objects.count() == 1
    assert PricingRules.objects.count() == 1
    assert Meal.objects.count() == 4
    assert FuelOption.objects.count() == 3
    assert Promo.objects.count() == 6
    assert MarketingSeasons.objects.count() == 4
    assert MarketingSeasonEnvironment.objects.count() == 13


def test_active_pricing_rules_singleton_constraint(loaded_catalog):
    with pytest.raises(IntegrityError):
        PricingRules.objects.create(
            updated_at="2026-04-01", payload={}, is_active=True
        )


def test_every_village_env_code_is_known(loaded_catalog):
    allowed = {c.value for c in EnvCode}
    bad = [v.id for v in Village.objects.all() if v.env_code not in allowed]
    assert not bad, f"Villages with unknown env_code: {bad}"


def test_tarifs_shape(loaded_catalog):
    saisons = {"hs", "vs", "ete", "fetes"}
    for v in Village.objects.all():
        available = set((v.tarifs or {}).keys())
        assert available & {"PC", "LOC"}, v.id
        for formule in ("PC", "LOC"):
            if formule in available:
                row = v.tarifs[formule]
                assert set(row.keys()) == saisons, (v.id, formule)
                assert all(isinstance(x, int) for x in row.values()), (v.id, formule)


def test_free_activities_have_no_price(loaded_catalog):
    for a in Activity.objects.filter(kind=Activity.KIND_FREE):
        assert a.price_adult == 0, a.code
        assert a.price_child == 0, a.code


@pytest.mark.django_db
def test_formula_serializer_exposes_include_text_as_text():
    formula = Formula.objects.create(
        code="PC",
        icon="🍽️",
        icon_key="pc",
        label="Pension complète",
        short_description="Petit-déj + déjeuner + dîner",
        include_text="Inclus en pension complète",
        sort_order=0,
    )

    data = FormulaSerializer(formula).data

    assert data["text"] == "Inclus en pension complète"
    assert "include_text" not in data


def test_attractions_link_back_to_villages(loaded_catalog):
    for a in Attraction.objects.select_related("village"):
        assert a.village_id, a.pk
        assert a.km >= 0, a.pk
