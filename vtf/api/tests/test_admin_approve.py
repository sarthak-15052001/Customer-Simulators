"""Approving a scrape proposal from the Django admin.

`approve_tariff_approval` used to be reachable only from the REST endpoint.
The admin exposed `status` as an editable dropdown, so setting it to
"approved" flipped the label and did nothing else: no VillageTarif rows
activated, no Village.tarifs rewritten. A reviewer saw "approved" while
pricing kept serving the stale season buckets — which is exactly how a
village ends up with scraped snapshots and no live tariffs.

`status` is readonly now and the decision goes through the service.
"""
from datetime import date
from decimal import Decimal
from html import unescape

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.tariff_scraper.models import (
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    TariffApproval,
    VillageTarif,
)
from apps.tariff_scraper.services.scraper import VillageScrapeResult
from apps.tariff_scraper.services.tarif_builder import build_tarifs_from_scrape
from apps.tariff_scraper.services.tarif_query import get_active_tarif

from tests.test_season_tarifs_projection import ARECHES_OUVERTURE, areches_pc_bands


@pytest.fixture
def staff(client, db):
    user = get_user_model().objects.create_superuser(
        "approver-staff", "approve@example.test", "pw"
    )
    client.force_login(user)
    client.user = user
    return client


@pytest.fixture
def pending(db):
    from apps.catalog.models import Village

    Village.objects.create(
        id="approve-areches",
        nom="Arêches-Beaufort",
        region="Alpes / Savoie",
        env_emoji="",
        env_code="mountain",
        has_loc=False,
        ski=False,
        ouverture=ARECHES_OUVERTURE,
        tarifs={"PC": {"hs": 476, "vs": 532, "ete": 637, "fetes": 728}},
    )
    build = build_tarifs_from_scrape(
        VillageScrapeResult(
            village_id="approve-areches", url="https://example.test", bands=areches_pc_bands()
        )
    )
    assert not build.errors
    return TariffApproval.objects.get(pk=build.approval_id)


def _url(name, pk):
    return reverse(f"admin:tariff_scraper_tariffapproval_{name}", args=[pk])


# ─── The trap this closes ─────────────────────────────────────────────────


def test_status_cannot_be_flipped_by_editing_the_form(staff, pending):
    """Posting status=approved must not fake an approval."""
    staff.post(
        _url("change", pending.pk),
        {
            "village": "approve-areches",
            "status": STATUS_APPROVED,
            "source_url": "",
            "bands_count": pending.bands_count,
            "reject_reason": "",
        },
    )

    pending.refresh_from_db()
    assert pending.status == STATUS_PENDING
    assert not VillageTarif.objects.filter(
        village_id="approve-areches", is_active=True
    ).exists()


# ─── Approve ──────────────────────────────────────────────────────────────


def test_approve_button_is_offered_on_a_pending_proposal(staff, pending):
    html = unescape(staff.get(_url("change", pending.pk)).content.decode())

    assert f"/{pending.pk}/approve/" in html
    assert f"/{pending.pk}/reject/" in html


def test_get_on_approve_only_confirms(staff, pending):
    resp = staff.get(_url("approve", pending.pk))

    assert resp.status_code == 200
    assert "Oui, approuver et appliquer" in resp.content.decode()
    pending.refresh_from_db()
    assert pending.status == STATUS_PENDING
    assert not VillageTarif.objects.filter(village_id="approve-areches").exists()


def test_post_on_approve_activates_the_dated_bands(staff, pending):
    from apps.catalog.models import Village

    resp = staff.post(_url("approve", pending.pk))

    assert resp.status_code == 302
    pending.refresh_from_db()
    assert pending.status == STATUS_APPROVED
    assert pending.reviewed_by == staff.user
    # The whole point: pricing now resolves the peak week off a dated band.
    assert get_active_tarif("approve-areches", "PC", date(2026, 8, 1)) == Decimal("728")
    assert Village.objects.get(pk="approve-areches").tarifs["PC"]["ete"] == 728


def test_approve_button_disappears_once_arbitrated(staff, pending):
    staff.post(_url("approve", pending.pk))

    html = unescape(staff.get(_url("change", pending.pk)).content.decode())

    assert "Deja arbitre" in html
    assert f"/{pending.pk}/approve/" not in html


def test_approving_twice_is_refused(staff, pending):
    staff.post(_url("approve", pending.pk))
    resp = staff.post(_url("approve", pending.pk), follow=True)

    assert resp.status_code == 200
    assert any("expected 'pending'" in str(m) for m in resp.context["messages"])


def test_changelist_action_approves_selected(staff, pending):
    staff.post(
        reverse("admin:tariff_scraper_tariffapproval_changelist"),
        {"action": "approve_selected_approvals", "_selected_action": [str(pending.pk)]},
        follow=True,
    )

    pending.refresh_from_db()
    assert pending.status == STATUS_APPROVED
    assert get_active_tarif("approve-areches", "PC", date(2026, 8, 1)) == Decimal("728")


# ─── Reject ───────────────────────────────────────────────────────────────


def test_post_on_reject_records_the_reason_and_touches_no_price(staff, pending):
    from apps.catalog.models import Village

    before = Village.objects.get(pk="approve-areches").tarifs

    resp = staff.post(_url("reject", pending.pk), {"reject_reason": "grille illisible"})

    assert resp.status_code == 302
    pending.refresh_from_db()
    assert pending.status == STATUS_REJECTED
    assert pending.reject_reason == "grille illisible"
    assert not VillageTarif.objects.filter(village_id="approve-areches").exists()
    assert Village.objects.get(pk="approve-areches").tarifs == before


def test_get_on_reject_offers_a_reason_field(staff, pending):
    html = staff.get(_url("reject", pending.pk)).content.decode()

    assert 'name="reject_reason"' in html
    assert "Oui, rejeter" in html


# ─── Round trip ───────────────────────────────────────────────────────────


def test_approve_then_revert_returns_to_the_starting_state(staff, pending):
    from apps.catalog.models import Village

    before = Village.objects.get(pk="approve-areches").tarifs

    staff.post(_url("approve", pending.pk))
    staff.post(_url("revert", pending.pk))

    assert Village.objects.get(pk="approve-areches").tarifs == before
    assert not VillageTarif.objects.filter(
        village_id="approve-areches", is_active=True
    ).exists()
