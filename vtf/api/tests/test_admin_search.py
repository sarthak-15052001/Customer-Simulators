"""The admin search box must work on every tariff_scraper changelist.

All four ModelAdmins declared `search_fields = ["village_id", ...]`. On a
ForeignKey, `village_id` is the attname, and Django resolves it back to the
relation itself — so the admin's generated `village_id__icontains` lands on the
ForeignKey and raises:

    FieldError: Unsupported lookup 'icontains' for ForeignKey
                or join on the field not permitted.

i.e. every one of these changelists returned a 500 as soon as anyone typed in
the search box. The fix is to traverse the relation (`village__id`) so the
lookup applies to Village's CharField primary key.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.tariff_scraper.models import (
    PriceSnapshot,
    TariffApproval,
    VillageTarif,
    FormatChangeLog,
)


@pytest.fixture
def admin_client_(client, db):
    user = get_user_model().objects.create_superuser(
        "search-staff", "search@example.test", "pw"
    )
    client.force_login(user)
    return client


@pytest.fixture
def village(db):
    from apps.catalog.models import Village

    return Village.objects.create(
        id="areches",
        nom="Arêches-Beaufort",
        nom2="Le Rafour",
        region="Alpes / Savoie",
        env_emoji="",
        env_code="mountain",
        has_loc=True,
        ski=False,
        ouverture="5/06–12/09/26",
        tarifs={"PC": {"hs": 476}},
    )


@pytest.fixture
def rows(village):
    snapshot = PriceSnapshot.objects.create(
        village=village,
        formule="PC",
        source_page="price_grid",
        date_label="25/07 au 15/08/26",
        date_start=date(2026, 7, 25),
        date_end=date(2026, 8, 15),
        unit_type="Adultes",
        scraped_price=Decimal("728"),
        is_available=True,
    )
    TariffApproval.objects.create(
        village=village, status="pending", proposed_bands=[], proposed_season_tarifs={}
    )
    VillageTarif.objects.create(
        village=village,
        formule="PC",
        date_start=date(2026, 7, 25),
        date_end=date(2026, 8, 15),
        pricing_type="per_person",
        unit_type="Adultes",
        price=Decimal("728"),
        is_active=True,
        source_snapshot=snapshot,
    )
    FormatChangeLog.objects.create(
        village=village, change_type="parse_failure", source_url="https://example.test"
    )


CHANGELISTS = [
    "admin:tariff_scraper_pricesnapshot_changelist",
    "admin:tariff_scraper_tariffapproval_changelist",
    "admin:tariff_scraper_villagetarif_changelist",
    "admin:tariff_scraper_formatchangelog_changelist",
]


@pytest.mark.parametrize("route", CHANGELISTS)
def test_searching_by_village_id_does_not_500(admin_client_, rows, route):
    """The exact request that crashed: ?q=areches."""
    resp = admin_client_.get(reverse(route), {"q": "areches"})

    assert resp.status_code == 200


@pytest.mark.parametrize("route", CHANGELISTS)
def test_searching_by_village_id_actually_matches(admin_client_, rows, route):
    resp = admin_client_.get(reverse(route), {"q": "areches"})

    assert resp.context["cl"].result_count == 1


@pytest.mark.parametrize("route", CHANGELISTS)
def test_search_excludes_non_matching_rows(admin_client_, rows, route):
    resp = admin_client_.get(reverse(route), {"q": "lacanau"})

    assert resp.status_code == 200
    assert resp.context["cl"].result_count == 0


def test_approvals_are_searchable_by_village_name(admin_client_, rows):
    """`village_id` alone made staff type internal slugs; the name is what
    they read in the list."""
    resp = admin_client_.get(
        reverse("admin:tariff_scraper_tariffapproval_changelist"), {"q": "Beaufort"}
    )

    assert resp.status_code == 200
    assert resp.context["cl"].result_count == 1


def test_other_search_fields_still_work(admin_client_, rows):
    resp = admin_client_.get(
        reverse("admin:tariff_scraper_pricesnapshot_changelist"), {"q": "15/08/26"}
    )

    assert resp.status_code == 200
    assert resp.context["cl"].result_count == 1
