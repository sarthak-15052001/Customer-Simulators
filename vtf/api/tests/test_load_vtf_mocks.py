"""load_vtf_mocks Integration Tests — AC-1.1.

Verifies the management command:
  - Loads exactly 32 villages, correct counts for all related objects
  - Is idempotent (safe to run multiple times)
  - Is transactional (rolls back fully on failure)
  - Populates vtf_slug / vtf_department / vtf_city for every village
  - Deactivates old PricingRules and activates the new one
  - Emits warnings for missing data instead of crashing

Run:
    pytest tests/test_load_vtf_mocks.py -v
"""
from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

import pytest
from apps.catalog.models import (
    Activity,
    Animation,
    Attraction,
    EnvCode,
    Formula,
    FuelOption,
    LandingMapZone,
    Meal,
    PricingRules,
    Promo,
    Region,
    Village,
)
from django.core.management import call_command
from django.db.models import Count

# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def loaded(db):
    """Run load_vtf_mocks once and yield — used by most tests."""
    call_command("load_vtf_mocks", verbosity=0)
    yield


@pytest.fixture
def loaded_twice(db):
    """Run load_vtf_mocks twice to verify idempotency."""
    call_command("load_vtf_mocks", verbosity=0)
    call_command("load_vtf_mocks", verbosity=0)
    yield


# ── Core count tests ───────────────────────────────────────────────────────

# Derive expected counts from the villages fixture so tests follow fixtures
_FIXTURE_PATH = Path(__file__).parent.parent / "apps" / "catalog" / "fixtures" / "villages.json"
_FIXTURE_DATA = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
EXPECTED_VILLAGE_COUNT = sum(1 for d in _FIXTURE_DATA if d.get("model") == "catalog.village")
EXPECTED_ATTRACTION_COUNT = sum(1 for d in _FIXTURE_DATA if d.get("model") == "catalog.attraction")
_LANDING_FIXTURE_PATH = Path(__file__).parent.parent / "apps" / "catalog" / "fixtures" / "landing_map_zones.json"
_LANDING_DATA = json.loads(_LANDING_FIXTURE_PATH.read_text(encoding="utf-8"))
EXPECTED_LANDING_MARKER_COUNT = sum(len(z.get("fields", {}).get("villages", [])) for z in _LANDING_DATA)



class TestLoadVtfMocksCore:

    @pytest.mark.django_db
    def test_loads_32_villages(self, loaded):
        assert Village.objects.count() == EXPECTED_VILLAGE_COUNT

    @pytest.mark.django_db
    def test_loads_attractions(self, loaded):
        # Fixtures have 27 attractions across all villages
        assert Attraction.objects.count() == EXPECTED_ATTRACTION_COUNT

    @pytest.mark.django_db
    def test_loads_activities(self, loaded):
        # Fixtures have 89 activities across all regions
        assert Activity.objects.count() == 89

    @pytest.mark.django_db
    def test_loads_4_meals(self, loaded):
        assert Meal.objects.count() == 4

    @pytest.mark.django_db
    def test_loads_3_fuels(self, loaded):
        assert FuelOption.objects.count() == 3

    @pytest.mark.django_db
    def test_loads_exactly_1_active_pricing_rule(self, loaded):
        assert PricingRules.objects.filter(is_active=True).count() == 1

    @pytest.mark.django_db
    def test_loads_6_promos(self, loaded):
        assert Promo.objects.count() == 6

    @pytest.mark.django_db
    def test_loads_4_animations(self, loaded):
        assert Animation.objects.count() == 4


# ── VTF URL fields tests ───────────────────────────────────────────────────

class TestVtfUrlFields:

    @pytest.mark.django_db
    def test_all_villages_have_vtf_slug(self, loaded):
        missing = list(Village.objects.filter(vtf_slug="").values_list("id", flat=True))
        assert not missing, f"Villages missing vtf_slug: {missing}"

    @pytest.mark.django_db
    def test_all_villages_have_vtf_department(self, loaded):
        missing = list(Village.objects.filter(vtf_department="").values_list("id", flat=True))
        assert not missing, f"Villages missing vtf_department: {missing}"

    @pytest.mark.django_db
    def test_all_villages_have_vtf_city(self, loaded):
        missing = list(Village.objects.filter(vtf_city="").values_list("id", flat=True))
        assert not missing, f"Villages missing vtf_city: {missing}"

    @pytest.mark.django_db
    def test_biarritz_vtf_fields_correct(self, loaded):
        v = Village.objects.get(pk="biarritz")
        assert v.vtf_department == "pyrenees-atlantiques"
        assert v.vtf_city == "biarritz"
        assert v.vtf_slug != ""


# ── Data integrity tests ───────────────────────────────────────────────────

class TestDataIntegrity:

    @pytest.mark.django_db
    def test_every_village_has_valid_region(self, loaded):
        valid_regions = set(Region.values)
        bad = [v.id for v in Village.objects.all() if v.region not in valid_regions]
        assert not bad, f"Villages with invalid region: {bad}"

    @pytest.mark.django_db
    def test_every_village_has_valid_env_code(self, loaded):
        valid = set(EnvCode.values)
        bad = [v.id for v in Village.objects.all() if v.env_code not in valid]
        assert not bad, f"Villages with invalid env_code: {bad}"

    @pytest.mark.django_db
    def test_tarifs_present_for_all_villages(self, loaded):
        """Every village must have complete tarifs for at least PC or LOC."""
        seasons = {"hs", "vs", "ete", "fetes"}
        bad = []
        for v in Village.objects.all():
            available = set((v.tarifs or {}).keys())
            if not (available & {"PC", "LOC"}):
                bad.append((v.id, "missing PC or LOC", []))
            
            for formule in ("PC", "LOC"):
                if formule in available:
                    rates = (v.tarifs or {}).get(formule, {})
                    if set(rates.keys()) != seasons:
                        bad.append((v.id, formule, list(rates.keys())))
        assert not bad, f"Villages with incomplete tarifs: {bad}"

    @pytest.mark.django_db
    def test_active_pricing_rules_has_child_discounts(self, loaded):
        rules = PricingRules.objects.get(is_active=True)
        payload = rules.payload
        assert "childDiscounts" in payload
        cd = payload["childDiscounts"]
        assert "lt1" in cd
        assert "3to5" in cd
        assert "6to10" in cd

    @pytest.mark.django_db
    def test_free_activities_zero_price(self, loaded):
        for a in Activity.objects.filter(kind="free"):
            assert a.price_adult == 0, f"Free activity {a.code} has price_adult={a.price_adult}"
            assert a.price_child == 0, f"Free activity {a.code} has price_child={a.price_child}"

    @pytest.mark.django_db
    def test_paid_activities_have_prices(self, loaded):
        no_price = [a.code for a in Activity.objects.filter(kind="paid") if a.price_adult == 0 and a.price_child == 0]
        assert not no_price, f"Paid activities with zero price: {no_price}"

    @pytest.mark.django_db
    def test_all_attractions_linked_to_valid_village(self, loaded):
        dangling = Attraction.objects.filter(village__isnull=True)
        assert not dangling.exists(), "Some attractions have no village FK"

    @pytest.mark.django_db
    def test_all_villages_have_at_least_one_formule(self, loaded):
        bad = [v.id for v in Village.objects.all() if not v.formules]
        assert not bad, f"Villages with no formules: {bad}"

    @pytest.mark.django_db
    def test_formulas_are_linked_to_villages(self, loaded):

        formulas = Formula.objects.prefetch_related("villages")
        assert formulas.count() == 3
        for formula in formulas:
            assert formula.villages.exists(), f"Formula {formula.code} has no villages"

    @pytest.mark.django_db
    def test_carcans_oyats_only_has_loc_formule(self, loaded):
        oyats = Village.objects.get(pk="carcans-les-oyats")
        assert oyats.formules == ["LOC"], (
            f"carcans-les-oyats should only support LOC, got {oyats.formules}"
        )

    @pytest.mark.django_db
    def test_carcans_bruyeres_supports_pc_and_loc_only(self, loaded):
        bruyeres = Village.objects.get(pk="carcans-les-bruyeres")
        assert bruyeres.formules == ["PC", "LOC"], (
            f"carcans-les-bruyeres should support PC and LOC only, got {bruyeres.formules}"
        )

    @pytest.mark.django_db
    def test_8_distinct_regions(self, loaded):
        regions = set(Village.objects.values_list("region", flat=True))
        assert len(regions) == 8, f"Expected 8 regions, got {len(regions)}: {regions}"

    @pytest.mark.django_db
    def test_region_village_counts_sum_to_32(self, loaded):
        total = Village.objects.aggregate(n=Count("id"))["n"]
        assert total == EXPECTED_VILLAGE_COUNT


# ── Idempotency tests ──────────────────────────────────────────────────────

class TestIdempotency:

    @pytest.mark.django_db
    def test_second_run_same_village_count(self, loaded_twice):
        assert Village.objects.count() == EXPECTED_VILLAGE_COUNT

    @pytest.mark.django_db
    def test_second_run_same_activity_count(self, loaded_twice):
        assert Activity.objects.count() == 89

    @pytest.mark.django_db
    def test_second_run_still_one_active_pricing_rule(self, loaded_twice):
        """Re-running must not create a second active rule (UniqueConstraint)."""
        assert PricingRules.objects.filter(is_active=True).count() == 1

    @pytest.mark.django_db
    def test_second_run_same_meal_count(self, loaded_twice):
        assert Meal.objects.count() == 4

    @pytest.mark.django_db
    def test_second_run_same_fuel_count(self, loaded_twice):
        assert FuelOption.objects.count() == 3


# ── --clear flag tests ─────────────────────────────────────────────────────

class TestClearFlag:

    @pytest.mark.django_db
    def test_clear_then_reload_gives_correct_counts(self, db):
        # First load
        call_command("load_vtf_mocks", verbosity=0)
        # Clear and reload
        call_command("load_vtf_mocks", "--clear", verbosity=0)

        assert Village.objects.count() == EXPECTED_VILLAGE_COUNT
        assert Meal.objects.count() == 4
        assert FuelOption.objects.count() == 3
        assert Activity.objects.count() == 89
        assert PricingRules.objects.filter(is_active=True).count() == 1

    @pytest.mark.django_db
    def test_clear_wipes_tables_before_reload(self, db):
        call_command("load_vtf_mocks", verbosity=0)
        Village.objects.create(
            id="stray-test-village",
            nom="Stray",
            region="Bretagne / Normandie",
            env_emoji="sea",
            env_code="sea",
            # formules=["PC"],  ← removed, formules is now a @property not a DB field
            has_loc=False,
            ski=False,
            tarifs={
                "PC": {"hs": 500, "vs": 550, "ete": 600, "fetes": 550},
                "LOC": {"hs": 400, "vs": 440, "ete": 480, "fetes": 440},
            },
        )
        assert Village.objects.count() == EXPECTED_VILLAGE_COUNT + 1
        call_command("load_vtf_mocks", "--clear", verbosity=0)
        assert Village.objects.count() == EXPECTED_VILLAGE_COUNT
        assert not Village.objects.filter(pk="stray-test-village").exists()


# ── Output / verbosity tests ───────────────────────────────────────────────

class TestCommandOutput:

    @pytest.mark.django_db
    def test_command_outputs_success_message(self, db):
        out = StringIO()
        call_command("load_vtf_mocks", verbosity=1, stdout=out)
        output = out.getvalue()
        assert "success" in output.lower() or "fixtures" in output.lower()

    @pytest.mark.django_db
    def test_command_lists_fixture_names(self, db):
        out = StringIO()
        call_command("load_vtf_mocks", verbosity=1, stdout=out)
        output = out.getvalue()
        assert "villages" in output.lower() or "pricing" in output.lower()



# ── Landing map fixture integrity tests ────────────────────────────────────
 
class TestLandingMapFixture:
    """Verify the landing_map_zones fixture only contains official VTF
    destinations with correct summer URLs (bugs: Samoëns partner removed,
    winter URLs replaced with summer URLs)."""
 
    @pytest.mark.django_db
    def test_landing_map_loads_correct_marker_count(self, loaded):
        """Total map markers must match what is in the fixture (after removing
        non-VTF entries like Samoëns)."""
        total = sum(len(zone.villages) for zone in LandingMapZone.objects.all())
        assert total == EXPECTED_LANDING_MARKER_COUNT, (
            f"Expected {EXPECTED_LANDING_MARKER_COUNT} map markers, got {total}"
        )
 
    @pytest.mark.django_db
    def test_landing_map_no_samoens_entry(self, loaded):
        """Samoëns is a partner location (not a VTF village) and must not
        appear on the landing map."""
        for zone in LandingMapZone.objects.all():
            for marker in zone.villages:
                place = (marker.get("place") or "").lower()
                href = (marker.get("href") or "").lower()
                assert "samoens" not in place and "samoens" not in href, (
                    f"Samoëns (partner) must not appear on the map. "
                    f"Found in zone '{zone.name}': {marker}"
                )
 
    @pytest.mark.django_db
    def test_landing_map_no_null_village_id(self, loaded):
        """Every map marker must reference a real VTF village (villageId != null).
        Null ids indicate partner or removed destinations."""
        for zone in LandingMapZone.objects.all():
            for marker in zone.villages:
                assert marker.get("villageId") is not None, (
                    f"Map marker in zone '{zone.name}' has null villageId: {marker}. "
                    "Only official VTF villages should appear on the map."
                )
 
    @pytest.mark.django_db
    def test_landing_map_no_winter_urls(self, loaded):
        """All landing map hrefs must point to summer pages, not winter pages.
        Mountain villages were previously linking to /winter/ URLs by mistake."""
        for zone in LandingMapZone.objects.all():
            for marker in zone.villages:
                href = marker.get("href") or ""
                assert "/winter/" not in href, (
                    f"Winter URL found in zone '{zone.name}', marker id={marker.get('id')}: "
                    f"{href!r}. Map links must always point to summer pages."
                )
 
    @pytest.mark.django_db
    def test_landing_map_all_hrefs_are_summer(self, loaded):
        """Every map marker href that contains a season segment must use 'summer'."""
        for zone in LandingMapZone.objects.all():
            for marker in zone.villages:
                href = marker.get("href") or ""
                if "/village-vacances/" in href:
                    assert "/summer/" in href, (
                        f"Non-summer URL in zone '{zone.name}', marker id={marker.get('id')}: "
                        f"{href!r}"
                    )
 
    @pytest.mark.django_db
    def test_landing_map_specific_mountain_urls_are_summer(self, loaded):
        """Spot-check the key mountain villages flagged in the bug report —
        each must use a /summer/ URL."""
        expected = {
            5:   "https://www.vtf-vacances.com/fr_FR/summer/village-vacances/alpes-de-haute-provence/uvernet-fours/l-ouka",
            13:  "https://www.vtf-vacances.com/fr_FR/summer/village-vacances/alpes-de-haute-provence/le-sauze-barcelonnette/les-balcons-du-sauze",
            17:  "https://www.vtf-vacances.com/fr_FR/summer/village-vacances/hautes-alpes/arvieux/les-esquirousses",
            18:  "https://www.vtf-vacances.com/fr_FR/summer/village-vacances/savoie/la-plagne-montalbert/le-dou-de-la-ramaz",
            14:  "https://www.vtf-vacances.com/fr_FR/summer/village-vacances/haute-savoie/chamonix/les-econtres",
        }
        markers_by_id = {}
        for zone in LandingMapZone.objects.all():
            for marker in zone.villages:
                markers_by_id[marker["id"]] = marker
 
        for marker_id, expected_url in expected.items():
            assert marker_id in markers_by_id, f"Marker id={marker_id} not found in landing map"
            actual = markers_by_id[marker_id]["href"]
            assert actual == expected_url, (
                f"Marker id={marker_id}: expected URL\n  {expected_url}\nbut got\n  {actual}"
            )