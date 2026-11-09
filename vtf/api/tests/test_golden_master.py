"""Golden Master Test Suite — AC-1.3.

Validates that the Python `estimate_sejour_total` service produces results
identical (±1 € tolerance) to the pre-captured golden cases in golden_cases.json.

These cases were generated directly from the Python service running against
the fixture data, establishing the canonical expected values. The purpose is
to catch any future regressions — if the service output changes, at least one
of these 60 cases will fail immediately.

Run:
    pytest tests/test_golden_master.py -v
    pytest tests/test_golden_master.py -v -k "biarritz"
    pytest tests/test_golden_master.py -v -k "ete"
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from django.core.management import call_command
from apps.pricing.services.stay_estimate import estimate_sejour_total

pytestmark = pytest.mark.django_db

@pytest.fixture(scope="module", autouse=True)
def loaded_db(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("load_vtf_mocks", verbosity=0)
    yield

# ── Load fixture data once at import time ──────────────────────────────────

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "apps" / "catalog" / "fixtures"
_TESTS_DIR = Path(__file__).resolve().parent

with (_FIXTURE_DIR / "villages.json").open(encoding="utf-8") as _fh:
    _FIXTURE_DATA = json.load(_fh)

with (_FIXTURE_DIR / "pricing_rules.json").open(encoding="utf-8") as _fh:
    _PR_DATA = json.load(_fh)

with (_TESTS_DIR / "golden_cases.json").open(encoding="utf-8") as _fh:
    GOLDEN_CASES = json.load(_fh)

# Build raw village dict keyed by slug-id
_VILLAGES_RAW: dict[str, dict] = {
    d["pk"]: d["fields"]
    for d in _FIXTURE_DATA
    if d["model"] == "catalog.village"
}

PRICING_RULES: dict = _PR_DATA[0]["fields"]["payload"]

# formules were removed from villages.json. Build a village_id → [formula_code, ...] map from formulas.json (M2M source).
with (_FIXTURE_DIR / "formulas.json").open(encoding="utf-8") as _fh:
    _FORMULAS_DATA = json.load(_fh)

_VILLAGE_FORMULES: dict[str, list[str]] = {}
for _formula_entry in _FORMULAS_DATA:
    _code = _formula_entry["pk"]
    for _vid in (_formula_entry["fields"].get("villages") or []):
        _VILLAGE_FORMULES.setdefault(_vid, []).append(_code)

with (_FIXTURE_DIR / "meals.json").open(encoding="utf-8") as _fh:
    _MEALS_DATA = json.load(_fh)

# Build meals catalog list expected by the service
MEALS_CATALOG: list[dict] = [
    {
        "code": m["pk"],
        "label": m["fields"]["label"],
        "price_adult": m["fields"]["price_adult"],
        "price_child": m["fields"]["price_child"],
    }
    for m in _MEALS_DATA
]


def _get(expected: dict, camel_key: str, snake_key: str | None = None) -> object:
    """
    Read a key from an expected dict that may use camelCase (older cases)
    or snake_case (newer cases generated via dataclasses.asdict).
    Falls back to snake_key if camel_key is missing.
    """
    if camel_key in expected:
        return expected[camel_key]
    fallback = snake_key or camel_key  # use explicit snake or camelCase itself
    return expected[fallback]


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_village(vid: str) -> dict:
    """Convert DB fixture fields → camelCase dict expected by the service."""
    v = dict(_VILLAGES_RAW[vid])
    v["id"] = vid
    # formules is no longer in villages.json — read from M2M map.
    v["formules"] = _VILLAGE_FORMULES.get(vid, [])
    # Map snake_case DB fields → camelCase service keys
    v["bebeClub"] = v.pop("bebe_club")
    v["qfExc"] = v.pop("qf_exc")
    v["enfSoloHalf"] = v.pop("enf_solo_half")
    v["forfaitRM"] = v.pop("forfait_rm")
    # Remove fields that the service doesn't use
    v.pop("vtf_url_verified_at", None)
    v.pop("has_loc", None)
    v.pop("env_emoji", None)
    v.pop("env_code", None)
    return v


# ── Parametrized golden-master tests ──────────────────────────────────────

@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_master_total(case: dict):
    """total must match expected within ±1 € (JS Math.round vs Python jsround)."""
    village_id = case["input"]["villageId"]
    village = _make_village(village_id)

    result = estimate_sejour_total(
        family=case["input"]["family"],
        sejour=case["input"]["sejour"],
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )

    assert result is not None, (
        f"estimate_sejour_total returned None for case '{case['id']}'. "
        "Check village tarifs / formule / dates."
    )

    expected = case["expected"]
    assert abs(result.total - expected["total"]) <= 1, (
        f"[{case['id']}] total mismatch: got {result.total}, expected {expected['total']}"
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_master_saison_key(case: dict):
    """Season key must match exactly — drives tarif selection."""
    village = _make_village(case["input"]["villageId"])
    result = estimate_sejour_total(
        family=case["input"]["family"],
        sejour=case["input"]["sejour"],
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    assert result.saison_key == _get(case["expected"], "saisonKey", "saison_key"), (
        f"[{case['id']}] saisonKey: got '{result.saison_key}', "
        f"expected '{case['expected']['saisonKey']}'"
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_master_nuits(case: dict):
    """Night count must be derived from dates, not the fNuits field."""
    village = _make_village(case["input"]["villageId"])
    result = estimate_sejour_total(
        family=case["input"]["family"],
        sejour=case["input"]["sejour"],
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    assert result.nuits == case["expected"]["nuits"], (
        f"[{case['id']}] nuits: got {result.nuits}, expected {case['expected']['nuits']}"
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_master_discount_rate(case: dict):
    """Discount rate must match within floating-point epsilon."""
    village = _make_village(case["input"]["villageId"])
    result = estimate_sejour_total(
        family=case["input"]["family"],
        sejour=case["input"]["sejour"],
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    expected_rate = _get(case["expected"], "discountRate", "discount_rate")
    assert abs(result.discount_rate - expected_rate) < 1e-4, (
        f"[{case['id']}] discountRate: got {result.discount_rate:.6f}, "
        f"expected {expected_rate:.6f}"
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_master_transport_total(case: dict):
    """Transport total must match exactly (deterministic formula)."""
    village = _make_village(case["input"]["villageId"])
    result = estimate_sejour_total(
        family=case["input"]["family"],
        sejour=case["input"]["sejour"],
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    assert result.transport_total == _get(case["expected"], "transportTotal", "transport_total"), (
        f"[{case['id']}] transportTotal: got {result.transport_total}, "
        f"expected {case['expected']['transportTotal']}"
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_master_adhesion(case: dict):
    """Membership fee (adhesion) must match the rules table."""
    village = _make_village(case["input"]["villageId"])
    result = estimate_sejour_total(
        family=case["input"]["family"],
        sejour=case["input"]["sejour"],
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    assert result.adhesion == case["expected"]["adhesion"], (
        f"[{case['id']}] adhesion: got {result.adhesion}, "
        f"expected {case['expected']['adhesion']}"
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_master_child_lines_count(case: dict):
    """One ChildLine per child in the family — never more, never fewer."""
    village = _make_village(case["input"]["villageId"])
    result = estimate_sejour_total(
        family=case["input"]["family"],
        sejour=case["input"]["sejour"],
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    expected_lines = _get(case["expected"], "childLines", "child_lines")
    assert len(result.child_lines) == len(expected_lines), (
        f"[{case['id']}] child_lines count: got {len(result.child_lines)}, "
        f"expected {len(expected_lines)}"
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_master_child_line_amounts(case: dict):
    """Each child's individual amount must match within ±1 €."""
    village = _make_village(case["input"]["villageId"])
    result = estimate_sejour_total(
        family=case["input"]["family"],
        sejour=case["input"]["sejour"],
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    for i, (got, exp) in enumerate(
        zip(result.child_lines, _get(case["expected"], "childLines", "child_lines"))
    ):
        assert abs(got.amount - exp["amount"]) <= 1, (
            f"[{case['id']}] child_lines[{i}] amount: got {got.amount}, "
            f"expected {exp['amount']} (age={got.age})"
        )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_master_hotel_estimate_positive(case: dict):
    """Hotel comparison must always be positive (spec: non-optional)."""
    village = _make_village(case["input"]["villageId"])
    result = estimate_sejour_total(
        family=case["input"]["family"],
        sejour=case["input"]["sejour"],
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    assert result.hotel_estimate > 0, (
        f"[{case['id']}] hotel_estimate must be > 0, got {result.hotel_estimate}"
    )
    assert result.hotel_estimate == _get(case["expected"], "hotelEstimate", "hotel_estimate"), (
        f"[{case['id']}] hotel_estimate: got {result.hotel_estimate}, "
        f"expected {case['expected']['hotelEstimate']}"
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["id"] for c in GOLDEN_CASES])
def test_golden_master_stay_subtotal(case: dict):
    """stay_subtotal (adults + children + solo supplement, before extras) must match ±1€."""
    village = _make_village(case["input"]["villageId"])
    result = estimate_sejour_total(
        family=case["input"]["family"],
        sejour=case["input"]["sejour"],
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    assert abs(result.stay_subtotal - _get(case["expected"], "staySubtotal", "stay_subtotal")) <= 1, (
        f"[{case['id']}] staySubtotal: got {result.stay_subtotal}, "
        f"expected {case['expected']['staySubtotal']}"
    )


# ── Additional edge-case unit tests (not parametrized) ────────────────────

def test_estimate_returns_none_for_bad_dates():
    """dateFin <= dateDebut must return None, not raise."""
    village = _make_village("biarritz")
    result = estimate_sejour_total(
        family={"adultes": 2, "enfants": [], "qfVal": None, "maxiFamily": False},
        sejour={
            "dateDebut": "2026-07-12",
            "dateFin": "2026-07-05",  # reversed
            "formule": "PC",
        },
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is None, "Reversed dates must return None"


def test_estimate_returns_none_for_same_day():
    """Zero-night stay must return None."""
    village = _make_village("biarritz")
    result = estimate_sejour_total(
        family={"adultes": 1, "enfants": [], "qfVal": None, "maxiFamily": False},
        sejour={
            "dateDebut": "2026-07-05",
            "dateFin": "2026-07-05",  # same day
            "formule": "PC",
        },
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is None, "Zero-night stay must return None"


def test_qf_r1_gives_17_percent_discount():
    """QF < 880 → 17% discount when village.qfExc is False."""
    village = _make_village("biarritz")
    village["qfExc"] = False
    result = estimate_sejour_total(
        family={"adultes": 2, "enfants": [], "qfVal": 700, "maxiFamily": False},
        sejour={
            "dateDebut": "2026-07-05",
            "dateFin": "2026-07-12",
            "formule": "PC",
            "promos": {"promoSejourRate": 0.0, "quinzaineFutee": False},
        },
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    assert abs(result.discount_rate - 0.17) < 1e-6, (
        f"Expected QF r1 discount = 0.17, got {result.discount_rate}"
    )


def test_qf_r2_gives_10_percent_discount():
    """880 ≤ QF < 1350 → 10% discount when village.qfExc is False."""
    village = _make_village("biarritz")
    village["qfExc"] = False
    result = estimate_sejour_total(
        family={"adultes": 2, "enfants": [], "qfVal": 1000, "maxiFamily": False},
        sejour={
            "dateDebut": "2026-07-05",
            "dateFin": "2026-07-12",
            "formule": "PC",
            "promos": {"promoSejourRate": 0.0, "quinzaineFutee": False},
        },
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    assert abs(result.discount_rate - 0.10) < 1e-6, (
        f"Expected QF r2 discount = 0.10, got {result.discount_rate}"
    )


def test_qf_plein_no_discount():
    """QF ≥ 1350 → 0% QF discount."""
    village = _make_village("biarritz")
    result = estimate_sejour_total(
        family={"adultes": 2, "enfants": [], "qfVal": 2000, "maxiFamily": False},
        sejour={
            "dateDebut": "2026-07-05",
            "dateFin": "2026-07-12",
            "formule": "PC",
            "promos": {"promoSejourRate": 0.0, "quinzaineFutee": False},
        },
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    assert result.discount_rate == 0.0, (
        f"QF ≥ 1350 should give 0 discount, got {result.discount_rate}"
    )


def test_child_under_1_is_free():
    """Child age < 1 → 100% discount (discount_fraction=1.0, amount=0)."""
    village = _make_village("biarritz")
    result = estimate_sejour_total(
        family={"adultes": 2, "enfants": [{"age": 0}], "qfVal": None, "maxiFamily": False},
        sejour={
            "dateDebut": "2026-07-05",
            "dateFin": "2026-07-12",
            "formule": "PC",
            "promos": {"promoSejourRate": 0.0, "quinzaineFutee": False},
        },
        village=village,
        pricing_rules=PRICING_RULES,
        meals_catalog=MEALS_CATALOG,
    )
    assert result is not None
    assert result.child_lines[0].discount_fraction == 1.0
    assert result.child_lines[0].amount == 0


def test_maxi_family_reduces_children_cost():
    """maxiFamily=True with ≥3 children → each child gets extra -20% on top of age discount."""
    village = _make_village("biarritz")
    family_normal = {"adultes": 2, "enfants": [{"age": 6}, {"age": 8}, {"age": 10}], "qfVal": None, "maxiFamily": False}
    family_maxi   = {"adultes": 2, "enfants": [{"age": 6}, {"age": 8}, {"age": 10}], "qfVal": None, "maxiFamily": True}
    sejour = {
        "dateDebut": "2026-07-05",
        "dateFin": "2026-07-12",
        "formule": "PC",
        "promos": {"promoSejourRate": 0.0, "quinzaineFutee": False},
    }
    r_normal = estimate_sejour_total(family=family_normal, sejour=sejour, village=village, pricing_rules=PRICING_RULES)
    r_maxi   = estimate_sejour_total(family=family_maxi,   sejour=sejour, village=village, pricing_rules=PRICING_RULES)
    assert r_normal is not None
    assert r_maxi is not None
    assert r_maxi.total_children < r_normal.total_children, (
        "maxiFamily should reduce children cost"
    )


def test_maxi_family_requires_3_children():
    """maxiFamily=True with only 2 children → no discount applied."""
    village = _make_village("biarritz")
    family_2ch_maxi  = {"adultes": 2, "enfants": [{"age": 6}, {"age": 8}], "qfVal": None, "maxiFamily": True}
    family_2ch_norm  = {"adultes": 2, "enfants": [{"age": 6}, {"age": 8}], "qfVal": None, "maxiFamily": False}
    sejour = {
        "dateDebut": "2026-07-05",
        "dateFin": "2026-07-12",
        "formule": "PC",
        "promos": {"promoSejourRate": 0.0, "quinzaineFutee": False},
    }
    r_maxi = estimate_sejour_total(family=family_2ch_maxi, sejour=sejour, village=village, pricing_rules=PRICING_RULES)
    r_norm = estimate_sejour_total(family=family_2ch_norm, sejour=sejour, village=village, pricing_rules=PRICING_RULES)
    assert r_maxi is not None and r_norm is not None
    assert r_maxi.total_children == r_norm.total_children, (
        "maxiFamily with < 3 children should NOT apply discount"
    )


def test_14_night_quinzaine_futee_applies():
    """quinzaineFutee=True + PC + ≥14 nights → additional 10% discount."""
    village = _make_village("biarritz")
    sejour_normal   = {
        "dateDebut": "2026-07-01", "dateFin": "2026-07-15", "formule": "PC",
        "promos": {"promoSejourRate": 0.0, "quinzaineFutee": False},
    }
    sejour_quinzaine = {
        "dateDebut": "2026-07-01", "dateFin": "2026-07-15", "formule": "PC",
        "promos": {"promoSejourRate": 0.0, "quinzaineFutee": True},
    }
    family = {"adultes": 2, "enfants": [], "qfVal": None, "maxiFamily": False}
    r_normal   = estimate_sejour_total(family=family, sejour=sejour_normal,   village=village, pricing_rules=PRICING_RULES)
    r_quinzaine = estimate_sejour_total(family=family, sejour=sejour_quinzaine, village=village, pricing_rules=PRICING_RULES)
    assert r_normal is not None and r_quinzaine is not None
    assert r_quinzaine.discount_rate > r_normal.discount_rate, (
        "quinzaineFutee must increase the discount rate"
    )
    assert r_quinzaine.total < r_normal.total, (
        "quinzaineFutee must lower the total cost"
    )


def test_all_32_villages_produce_result_for_summer():
    """Every village must return a non-None estimate for a standard summer week."""
    family = {"adultes": 2, "enfants": [{"age": 8}], "qfVal": None, "maxiFamily": False}
    sejour_base = {
        "dateDebut": "2026-07-05",
        "dateFin": "2026-07-12",
        "promos": {"promoSejourRate": 0.0, "quinzaineFutee": False},
    }
    failed = []
    for vid, raw in _VILLAGES_RAW.items():
        # formules = raw.get("formules", [])
        
        # formules come from _VILLAGE_FORMULES (formulas.json M2M), not from raw village fields.
        formules = _VILLAGE_FORMULES.get(vid, [])
        formule = "PC" if "PC" in formules else (formules[0] if formules else None)
        if not formule:
            failed.append((vid, "no formule"))
            continue
        village = _make_village(vid)
        sejour = {**sejour_base, "formule": formule}
        result = estimate_sejour_total(family=family, sejour=sejour, village=village, pricing_rules=PRICING_RULES)
        if result is None:
            failed.append((vid, "returned None"))
    assert not failed, f"Villages with no result: {failed}"
