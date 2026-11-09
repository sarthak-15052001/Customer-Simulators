"""Regression tests for the season-bucket projection (hs / vs / ete / fetes).

Ground truth is the live Arêches-Beaufort ("Le Rafour") grille tarifaire and
the price its booking funnel actually charges:

    Grille — Pension complète, colonne Adultes, semaine 8j/7n
      Hors vacances  5/06–4/07, 29/08–19/09/26   476 €
      Été            4–11/07,   22–29/08/26      532 €
      Été            11–25/07,  15–22/08/26      637 €
      Été            25/07–15/08/26              728 €
    Ouverture: 5/06–12/09/26
    Note grille: "1/2 pension possible = 15% de remise sur le tarif en
    pension complète" → DP is derived, not scraped.

    Funnel, 01/08→08/08/2026, 2 adultes, PC:
      2 × 728 € + 2 × 6,16 € taxe de séjour = 1 468,32 €

Seven of those date sub-ranges fall inside what the API calls one season
(``ete`` = 20/06–01/09), at four different prices. The bug this file pins:
approval #94 proposed ``PC {hs: 476, vs: 532, ete: 476, fetes: 728}`` — ``ete``
took the *cheapest* row and the peak 728 € vanished, while ``vs`` and ``fetes``
were untouched fixture leftovers for seasons this village is never open in.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.tariff_scraper.services.scraper import RawPriceBand, VillageScrapeResult
from apps.tariff_scraper.services.tarif_builder import (
    build_season_tarifs_patch,
    build_season_tarifs_proposal,
    build_tarifs_from_scrape,
)

ARECHES_OUVERTURE = "5/06–12/09/26"

# (price, [(date_start, date_end), ...]) in the order the grille emits rows —
# top-to-bottom, so the cheap "Hors vacances" row comes first. That ordering is
# what the old first-band-wins projection tripped over.
ARECHES_PC_GRID = [
    (476, [(date(2026, 6, 5), date(2026, 7, 4)), (date(2026, 8, 29), date(2026, 9, 19))]),
    (532, [(date(2026, 7, 4), date(2026, 7, 11)), (date(2026, 8, 22), date(2026, 8, 29))]),
    (637, [(date(2026, 7, 11), date(2026, 7, 25)), (date(2026, 8, 15), date(2026, 8, 22))]),
    (728, [(date(2026, 7, 25), date(2026, 8, 15))]),
]


def _band(formule, date_start, date_end, price, unit_type="Adultes", **kwargs):
    return RawPriceBand(
        formule=formule,
        source_page="price_grid",
        date_label=f"{date_start:%d/%m} au {date_end:%d/%m/%y}",
        date_start=date_start,
        date_end=date_end,
        scraped_price=Decimal(str(price)),
        unit_type=unit_type,
        **kwargs,
    )


def areches_pc_bands():
    return [
        _band("PC", start, end, price)
        for price, ranges in ARECHES_PC_GRID
        for start, end in ranges
    ]


# ─── Aggregation: peak, not first row ─────────────────────────────────────


def test_ete_bucket_takes_the_peak_week_not_the_first_grille_row():
    """The 728 € peak must win `ete`, not the 476 € shoulder listed first."""
    patch = build_season_tarifs_patch(areches_pc_bands(), ouverture=ARECHES_OUVERTURE)

    assert patch["PC"]["ete"] == 728


def test_hs_bucket_keeps_the_pre_season_shoulder_price():
    """5/06 is before the API's `ete` window (20/06) and stays in `hs`."""
    patch = build_season_tarifs_patch(areches_pc_bands(), ouverture=ARECHES_OUVERTURE)

    assert patch["PC"]["hs"] == 476


def test_scrape_only_produces_the_seasons_it_actually_saw():
    """A village open 5/06–12/09 can never yield `vs` or `fetes` bands."""
    patch = build_season_tarifs_patch(areches_pc_bands(), ouverture=ARECHES_OUVERTURE)

    assert set(patch["PC"]) == {"hs", "ete"}


def test_peak_selection_is_independent_of_grille_row_order():
    """Reversing the grille must not change the projection."""
    forward = build_season_tarifs_patch(areches_pc_bands(), ouverture=ARECHES_OUVERTURE)
    reversed_ = build_season_tarifs_patch(
        list(reversed(areches_pc_bands())), ouverture=ARECHES_OUVERTURE
    )

    assert forward == reversed_


def test_loc_takes_cheapest_unit_but_that_unit_s_peak_week():
    """LOC buckets are "à partir de" across *units*, not across *weeks*.

    Two units, two weeks each. The bucket must be the cheap unit's peak (610),
    never its shoulder (450) and never the expensive unit (880).
    """
    bands = [
        _band("LOC", date(2026, 7, 4), date(2026, 7, 11), 450, "2 pieces 4 pers."),
        _band("LOC", date(2026, 7, 25), date(2026, 8, 15), 610, "2 pieces 4 pers."),
        _band("LOC", date(2026, 7, 4), date(2026, 7, 11), 700, "3 pieces 6 pers."),
        _band("LOC", date(2026, 7, 25), date(2026, 8, 15), 880, "3 pieces 6 pers."),
    ]

    patch = build_season_tarifs_patch(bands, ouverture=ARECHES_OUVERTURE)

    assert patch["LOC"]["ete"] == 610


def test_gratuit_zero_price_band_is_still_recorded():
    """PS-08: a genuine 0 € stays; only *missing* prices are dropped."""
    bands = [_band("PC", date(2026, 4, 11), date(2026, 5, 2), 0)]

    patch = build_season_tarifs_patch(bands)

    assert patch["PC"]["hs"] == 0


def test_band_without_a_price_is_ignored():
    bands = [
        _band("PC", date(2026, 7, 25), date(2026, 8, 15), 728),
        RawPriceBand(
            formule="PC",
            source_page="price_grid",
            date_label="sur demande",
            date_start=date(2026, 7, 4),
            date_end=date(2026, 7, 11),
            scraped_price=None,
            unit_type="Adultes",
        ),
    ]

    patch = build_season_tarifs_patch(bands, ouverture=ARECHES_OUVERTURE)

    assert patch["PC"]["ete"] == 728


def test_unavailable_band_is_ignored():
    bands = [
        _band("PC", date(2026, 7, 25), date(2026, 8, 15), 728),
        _band("PC", date(2026, 8, 22), date(2026, 8, 29), 999, is_available=False),
    ]

    patch = build_season_tarifs_patch(bands, ouverture=ARECHES_OUVERTURE)

    assert patch["PC"]["ete"] == 728


def test_scraped_season_absent_from_the_fixture_is_no_longer_discarded():
    """The fixture must not veto a season the page actually quotes.

    The old projection restricted the patch to keys already present in
    `Village.tarifs`, so a village whose grille grew a December band could
    never gain a `fetes` bucket.
    """
    bands = [_band("PC", date(2026, 12, 26), date(2027, 1, 2), 903)]

    patch = build_season_tarifs_patch(
        bands,
        existing_tarifs={"PC": {"hs": 469}},
        ouverture="20/12/25–11/04/26 · 5/06–12/09/26",
    )

    assert patch["PC"]["fetes"] == 903


# ─── Opening-calendar gating + staleness reporting ────────────────────────


def test_closed_all_season_bucket_is_dropped_and_reported():
    """`fetes: 728` on a village that shuts 12/09 is a phantom price."""
    existing = {"PC": {"hs": 476, "vs": 532, "ete": 637, "fetes": 728}}

    proposed, notes = build_season_tarifs_proposal(
        areches_pc_bands(), existing, ARECHES_OUVERTURE
    )

    assert "fetes" not in proposed["PC"]
    assert "vs" not in proposed["PC"]
    assert {(e["formule"], e["season"], e["price"]) for e in notes["dropped_closed"]} == {
        ("PC", "vs", 532),
        ("PC", "fetes", 728),
    }


def test_carried_over_bucket_of_an_open_season_is_flagged_unverified():
    """Kept, but never presented as if this scrape had confirmed it."""
    existing = {"PC": {"hs": 476, "vs": 532, "ete": 637, "fetes": 728}}
    bands = [_band("PC", date(2026, 7, 25), date(2026, 8, 15), 728)]

    proposed, notes = build_season_tarifs_proposal(
        bands, existing, ouverture="1/01–31/12/26"
    )

    assert proposed["PC"] == {"hs": 476, "vs": 532, "ete": 728, "fetes": 728}
    assert [(e["formule"], e["season"]) for e in notes["unverified"]] == [
        ("PC", "fetes"),
        ("PC", "hs"),
        ("PC", "vs"),
    ]
    assert notes["dropped_closed"] == []


def test_fully_scraped_proposal_reports_nothing_stale():
    proposed, notes = build_season_tarifs_proposal(
        areches_pc_bands(), {}, ARECHES_OUVERTURE
    )

    assert proposed["PC"] == {"hs": 476, "ete": 728}
    assert notes == {"unverified": [], "dropped_closed": []}


def test_missing_ouverture_never_deletes_a_curated_price():
    """No opening calendar means no information — fail open, never destructive."""
    existing = {"PC": {"hs": 476, "fetes": 728}}
    bands = [_band("PC", date(2026, 7, 25), date(2026, 8, 15), 728)]

    proposed, notes = build_season_tarifs_proposal(bands, existing, ouverture="")

    assert proposed["PC"]["fetes"] == 728
    assert notes["dropped_closed"] == []
    # Neither carried-over bucket was scraped: the single band lands in `ete`.
    assert [(e["formule"], e["season"]) for e in notes["unverified"]] == [
        ("PC", "fetes"),
        ("PC", "hs"),
    ]


def test_unparseable_ouverture_never_deletes_a_curated_price():
    existing = {"PC": {"hs": 476, "fetes": 728}}
    bands = [_band("PC", date(2026, 7, 25), date(2026, 8, 15), 728)]

    proposed, _ = build_season_tarifs_proposal(
        bands, existing, ouverture="nous confirmer les dates"
    )

    assert proposed["PC"]["fetes"] == 728


def test_winter_village_keeps_its_fetes_bucket():
    """Gating must not fire on a village that *is* open over New Year."""
    existing = {"PC": {"hs": 469, "fetes": 903}}
    bands = [_band("PC", date(2026, 2, 20), date(2026, 2, 27), 812)]

    proposed, notes = build_season_tarifs_proposal(
        bands, existing, ouverture="20/12/25–11/04/26"
    )

    assert proposed["PC"]["fetes"] == 903
    assert notes["dropped_closed"] == []


# ─── End to end: scrape → approve → what pricing resolves ─────────────────


@pytest.mark.django_db
def test_areches_scrape_to_approval_matches_the_booking_funnel():
    """The full path, asserted against the price VTF actually charges.

    Funnel: 01/08→08/08/2026, PC, adulte → 728 €/pers.
    """
    from apps.catalog.models import Village
    from apps.tariff_scraper.models import TariffApproval
    from apps.tariff_scraper.services.approval import approve_tariff_approval
    from apps.tariff_scraper.services.tarif_query import get_active_tarif

    # Own village id rather than the fixture's "areches": this test mutates
    # Village.tarifs, and other suites load the villages fixture, so sharing
    # the pk makes the two collide depending on run order.
    Village.objects.create(
        id="areches-projection-test",
        nom="Arêches-Beaufort",
        nom2="Le Rafour",
        region="Alpes / Savoie",
        env_emoji="",
        env_code="mountain",
        has_loc=True,
        ski=False,
        ouverture=ARECHES_OUVERTURE,
        # Hand-seeded fixture: a human spread the four grille tiers across the
        # four season keys. Only `hs` and `ete` are reachable by a scrape.
        tarifs={
            "PC": {"hs": 476, "vs": 532, "ete": 637, "fetes": 728},
            "LOC": {"hs": 450, "vs": 500, "ete": 600, "fetes": 680},
        },
    )

    build = build_tarifs_from_scrape(
        VillageScrapeResult(
            village_id="areches-projection-test",
            url="https://www.vtf-vacances.com/le-rafour",
            bands=areches_pc_bands(),
        )
    )
    assert not build.errors

    approval = TariffApproval.objects.get(pk=build.approval_id)
    assert approval.proposed_season_tarifs["PC"]["ete"] == 728
    assert "fetes" not in approval.proposed_season_tarifs["PC"]
    # LOC was not scraped this run — every LOC bucket is carried over.
    assert {(e["formule"], e["season"]) for e in approval.season_tarifs_notes["unverified"]} == {
        ("LOC", "hs"),
        ("LOC", "ete"),
    }

    approve_tariff_approval(approval, sync_fixture=False)
    village = Village.objects.get(pk="areches-projection-test")

    # Dated bands are what pricing reads first — peak week resolves exactly.
    assert get_active_tarif("areches-projection-test", "PC", date(2026, 8, 1)) == Decimal("728")
    # ... and the season fallback no longer undercuts it by 35 %.
    assert village.tarifs["PC"]["ete"] == 728
    # Phantom out-of-season prices are gone from the live tarifs.
    assert "fetes" not in village.tarifs["PC"]
    assert "vs" not in village.tarifs["PC"]
    # Untouched formules survive the merge.
    assert village.tarifs["LOC"]["ete"] == 600


@pytest.mark.django_db
def test_season_fallback_quotes_the_peak_when_no_dated_band_exists():
    """Villages with no scrape yet are served from the buckets — check those.

    This is the path that produced 476 €/pers for a 728 € week.
    """
    from apps.catalog.models import Village
    from apps.pricing.services.stay_estimate import _resolve_base_tarif

    Village.objects.create(
        id="areches-fallback",
        nom="Arêches-Beaufort",
        region="Alpes / Savoie",
        env_emoji="",
        env_code="mountain",
        has_loc=False,
        ski=False,
        ouverture=ARECHES_OUVERTURE,
        tarifs={},
    )
    proposed, _ = build_season_tarifs_proposal(
        areches_pc_bands(), {}, ARECHES_OUVERTURE
    )

    base, coef, is_per_night = _resolve_base_tarif(
        village={"id": "areches-fallback", "tarifs": proposed},
        formule="PC",
        stay_date=date(2026, 8, 1),
        saison="ete",
        pricing_rules={},
    )

    assert base * coef == 728
    assert is_per_night is False
