"""Rollback of an applied TariffApproval, and the admin surface around it.

`approve` does three things — deactivate the live bands for the formules it
touches, create new ones, rewrite `Village.tarifs`. A revert that only undid
the third would leave pricing resolving off dated bands that no longer match
the season buckets, which is worse than not reverting at all. These tests pin
all three, plus the guard against reverting out of order.
"""
import base64
from datetime import date, timedelta
from decimal import Decimal
from html import unescape

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.tariff_scraper.models import (
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REVERTED,
    TariffApproval,
    VillageTarif,
)
from apps.tariff_scraper.services.approval import (
    ApprovalError,
    approve_tariff_approval,
    revert_tariff_approval,
)
from apps.tariff_scraper.services.scraper import VillageScrapeResult
from apps.tariff_scraper.services.tarif_builder import build_tarifs_from_scrape

from tests.test_season_tarifs_projection import ARECHES_OUVERTURE, areches_pc_bands, _band

STAFF_PASSWORD = "pw-test-only"

ORIGINAL_TARIFS = {
    "PC": {"hs": 476, "vs": 532, "ete": 637, "fetes": 728},
    "LOC": {"hs": 450, "vs": 500, "ete": 600, "fetes": 680},
}


def _make_village(village_id):
    from apps.catalog.models import Village

    return Village.objects.create(
        id=village_id,
        nom="Arêches-Beaufort",
        nom2="Le Rafour",
        region="Alpes / Savoie",
        env_emoji="",
        env_code="mountain",
        has_loc=True,
        ski=False,
        ouverture=ARECHES_OUVERTURE,
        tarifs={k: dict(v) for k, v in ORIGINAL_TARIFS.items()},
    )


def _scrape_and_approve(village_id, bands=None, user=None):
    build = build_tarifs_from_scrape(
        VillageScrapeResult(
            village_id=village_id,
            url="https://www.vtf-vacances.com/le-rafour",
            bands=bands if bands is not None else areches_pc_bands(),
        )
    )
    assert not build.errors
    approval = TariffApproval.objects.get(pk=build.approval_id)
    return approve_tariff_approval(approval, user=user, sync_fixture=False)


# ─── Service ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_revert_restores_season_buckets_exactly():
    from apps.catalog.models import Village

    _make_village("rev-buckets")
    approval = _scrape_and_approve("rev-buckets")

    applied = Village.objects.get(pk="rev-buckets").tarifs
    assert applied["PC"]["ete"] == 728 and "fetes" not in applied["PC"]

    revert_tariff_approval(approval, sync_fixture=False)

    assert Village.objects.get(pk="rev-buckets").tarifs == ORIGINAL_TARIFS


@pytest.mark.django_db
def test_revert_deactivates_the_bands_this_approval_created():
    _make_village("rev-bands")
    approval = _scrape_and_approve("rev-bands")
    assert VillageTarif.objects.filter(village_id="rev-bands", is_active=True).exists()

    revert_tariff_approval(approval, sync_fixture=False)

    assert not VillageTarif.objects.filter(
        village_id="rev-bands", is_active=True
    ).exists()
    # Rows are deactivated, never deleted — the audit trail survives.
    assert VillageTarif.objects.filter(village_id="rev-bands").exists()


@pytest.mark.django_db
def test_revert_reactivates_the_previous_generation_of_bands():
    """The hard half: `approve` deactivated the prior bands, revert brings them back."""
    from apps.catalog.models import Village
    from apps.tariff_scraper.services.tarif_query import get_active_tarif

    _make_village("rev-generations")

    # First scrape: the grille as it stood, peak week at 728.
    first = _scrape_and_approve("rev-generations")
    assert get_active_tarif("rev-generations", "PC", date(2026, 8, 1)) == Decimal("728")

    # Second scrape a moment later: VTF reprices the peak week to 750.
    reworked = [
        _band("PC", date(2026, 7, 25), date(2026, 8, 15), 750),
        _band("PC", date(2026, 6, 5), date(2026, 7, 4), 480),
    ]
    second = _scrape_and_approve("rev-generations", bands=reworked)
    assert get_active_tarif("rev-generations", "PC", date(2026, 8, 1)) == Decimal("750")

    revert_tariff_approval(second, sync_fixture=False)

    # Back to the first approval's prices, not to "no price at all".
    assert get_active_tarif("rev-generations", "PC", date(2026, 8, 1)) == Decimal("728")
    assert Village.objects.get(pk="rev-generations").tarifs["PC"]["ete"] == 728
    first.refresh_from_db()
    assert first.status == STATUS_APPROVED


@pytest.mark.django_db
def test_revert_refuses_when_a_newer_approval_superseded_it():
    """Reverting out of order would silently clobber the newer prices."""
    _make_village("rev-order")
    first = _scrape_and_approve("rev-order")
    _scrape_and_approve(
        "rev-order", bands=[_band("PC", date(2026, 7, 25), date(2026, 8, 15), 750)]
    )

    with pytest.raises(ApprovalError, match="superseded"):
        revert_tariff_approval(first, sync_fixture=False)

    first.refresh_from_db()
    assert first.status == STATUS_APPROVED


@pytest.mark.django_db
def test_revert_refuses_a_pending_approval():
    _make_village("rev-pending")
    build = build_tarifs_from_scrape(
        VillageScrapeResult(village_id="rev-pending", url="x", bands=areches_pc_bands())
    )
    approval = TariffApproval.objects.get(pk=build.approval_id)

    with pytest.raises(ApprovalError, match="expected 'approved'"):
        revert_tariff_approval(approval, sync_fixture=False)


@pytest.mark.django_db
def test_revert_keeps_the_review_trail_and_records_its_own():
    """`reviewed_at` is the join key to this approval's bands — it must survive."""
    User = get_user_model()
    approver = User.objects.create_user("approver", password="x")
    reverter = User.objects.create_user("reverter", password="x")

    _make_village("rev-trail")
    approval = _scrape_and_approve("rev-trail", user=approver)
    reviewed_at, reviewed_by = approval.reviewed_at, approval.reviewed_by

    revert_tariff_approval(approval, user=reverter, sync_fixture=False)
    approval.refresh_from_db()

    assert approval.status == STATUS_REVERTED
    assert approval.reviewed_at == reviewed_at
    assert approval.reviewed_by == reviewed_by
    assert approval.reverted_by == reverter
    assert approval.reverted_at is not None
    # The bands stay findable from the approval. NB the link is
    # source_snapshot_id, not effective_at: that column is auto_now_add, so the
    # value approve passes is discarded and never equals reviewed_at.
    snapshot_ids = [b["source_snapshot_id"] for b in approval.proposed_bands]
    assert VillageTarif.objects.filter(
        village_id="rev-trail", source_snapshot_id__in=snapshot_ids
    ).exists()


@pytest.mark.django_db
def test_revert_is_idempotent_by_refusing_a_second_run():
    _make_village("rev-twice")
    approval = _scrape_and_approve("rev-twice")
    revert_tariff_approval(approval, sync_fixture=False)

    with pytest.raises(ApprovalError, match="expected 'approved'"):
        revert_tariff_approval(approval, sync_fixture=False)


# ─── Admin surface ────────────────────────────────────────────────────────


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_superuser(
        "staff", "staff@example.test", STAFF_PASSWORD
    )


@pytest.fixture
def staff_client(client, staff_user):
    """Session-authenticated — what the Django admin uses."""
    client.force_login(staff_user)
    client.user = staff_user
    return client


@pytest.fixture
def api_client(staff_user):
    """Basic-auth — what `StaffAPIViewMixin` actually accepts.

    Deliberately real credentials rather than `force_authenticate`, so the
    documented auth scheme is exercised instead of bypassed.
    """
    from rest_framework.test import APIClient

    token = base64.b64encode(f"staff:{STAFF_PASSWORD}".encode()).decode()
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Basic {token}")
    api.user = staff_user
    return api


@pytest.mark.django_db
def test_revert_button_is_hidden_unless_the_approval_is_applied(staff_client):
    _make_village("rev-btn")
    build = build_tarifs_from_scrape(
        VillageScrapeResult(village_id="rev-btn", url="x", bands=areches_pc_bands())
    )
    url = reverse(
        "admin:tariff_scraper_tariffapproval_change", args=[build.approval_id]
    )

    # unescape: the admin renders the label as "Annuler l&#x27;approbation"
    html = unescape(staff_client.get(url).content.decode())

    assert "Annuler l'approbation" in html  # the label is present…
    assert "Disponible uniquement sur une approbation appliquee" in html  # …but disabled
    assert f"/{build.approval_id}/revert/" not in html


@pytest.mark.django_db
def test_revert_button_appears_once_applied(staff_client):
    _make_village("rev-btn-on")
    approval = _scrape_and_approve("rev-btn-on")
    url = reverse("admin:tariff_scraper_tariffapproval_change", args=[approval.pk])

    html = staff_client.get(url).content.decode()

    assert f"/{approval.pk}/revert/" in html


@pytest.mark.django_db
def test_get_on_revert_url_only_confirms_and_changes_nothing(staff_client):
    from apps.catalog.models import Village

    _make_village("rev-get")
    approval = _scrape_and_approve("rev-get")
    url = reverse("admin:tariff_scraper_tariffapproval_revert", args=[approval.pk])

    resp = staff_client.get(url)

    assert resp.status_code == 200
    assert "Oui, annuler l'approbation" in resp.content.decode()
    approval.refresh_from_db()
    assert approval.status == STATUS_APPROVED
    assert Village.objects.get(pk="rev-get").tarifs["PC"]["ete"] == 728


@pytest.mark.django_db
def test_post_on_revert_url_reverts_and_attributes_the_signed_in_user(staff_client):
    from apps.catalog.models import Village

    _make_village("rev-post")
    approval = _scrape_and_approve("rev-post")
    url = reverse("admin:tariff_scraper_tariffapproval_revert", args=[approval.pk])

    resp = staff_client.post(url)

    assert resp.status_code == 302
    approval.refresh_from_db()
    assert approval.status == STATUS_REVERTED
    assert approval.reverted_by == staff_client.user
    assert Village.objects.get(pk="rev-post").tarifs == ORIGINAL_TARIFS


@pytest.mark.django_db
def test_changelist_action_reverts_selected(staff_client):
    from apps.catalog.models import Village

    _make_village("rev-action")
    approval = _scrape_and_approve("rev-action")

    staff_client.post(
        reverse("admin:tariff_scraper_tariffapproval_changelist"),
        {
            "action": "revert_selected_approvals",
            "_selected_action": [str(approval.pk)],
        },
        follow=True,
    )

    approval.refresh_from_db()
    assert approval.status == STATUS_REVERTED
    assert Village.objects.get(pk="rev-action").tarifs == ORIGINAL_TARIFS


# ─── API ──────────────────────────────────────────────────────────────────


def _action_url(approval_id):
    return f"/api/v4/admin/tariff-scraper/approvals/{approval_id}/"


@pytest.mark.django_db
def test_api_revert_restores_tarifs_and_attributes_the_caller(api_client):
    from apps.catalog.models import Village

    _make_village("api-revert")
    approval = _scrape_and_approve("api-revert")

    resp = api_client.post(
        _action_url(approval.pk), {"action": "revert"}, content_type="application/json"
    )

    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == STATUS_REVERTED
    assert body["reverted_by_username"] == api_client.user.get_username()
    assert body["reverted_at"] is not None
    # The review trail is preserved alongside the rollback.
    assert body["reviewed_at"] is not None
    assert Village.objects.get(pk="api-revert").tarifs == ORIGINAL_TARIFS


@pytest.mark.django_db
def test_api_revert_on_a_pending_approval_is_a_400_not_a_silent_reject(api_client):
    """Regression: the view dispatched `else -> reject`, so an unhandled
    action would have quietly rejected the proposal instead of erroring."""
    _make_village("api-revert-pending")
    build = build_tarifs_from_scrape(
        VillageScrapeResult(
            village_id="api-revert-pending", url="x", bands=areches_pc_bands()
        )
    )
    approval = TariffApproval.objects.get(pk=build.approval_id)

    resp = api_client.post(
        _action_url(approval.pk), {"action": "revert"}, content_type="application/json"
    )

    assert resp.status_code == 400
    approval.refresh_from_db()
    assert approval.status == STATUS_PENDING  # NOT rejected


@pytest.mark.django_db
def test_api_revert_out_of_order_is_refused(api_client):
    _make_village("api-revert-order")
    first = _scrape_and_approve("api-revert-order")
    _scrape_and_approve(
        "api-revert-order",
        bands=[_band("PC", date(2026, 7, 25), date(2026, 8, 15), 750)],
    )

    resp = api_client.post(
        _action_url(first.pk), {"action": "revert"}, content_type="application/json"
    )

    assert resp.status_code == 400
    assert "superseded" in resp.json()["message"].lower()
    first.refresh_from_db()
    assert first.status == STATUS_APPROVED


@pytest.mark.django_db
def test_api_rejects_an_unknown_action(api_client):
    _make_village("api-bad-action")
    approval = _scrape_and_approve("api-bad-action")

    resp = api_client.post(
        _action_url(approval.pk), {"action": "destroy"}, content_type="application/json"
    )

    assert resp.status_code == 400
    approval.refresh_from_db()
    assert approval.status == STATUS_APPROVED


@pytest.mark.django_db
def test_api_approve_and_reject_still_behave(api_client):
    """The explicit dispatch must not have changed the two existing actions."""
    from apps.catalog.models import Village

    _make_village("api-approve")
    build = build_tarifs_from_scrape(
        VillageScrapeResult(village_id="api-approve", url="x", bands=areches_pc_bands())
    )
    resp = api_client.post(
        _action_url(build.approval_id),
        {"action": "approve"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert Village.objects.get(pk="api-approve").tarifs["PC"]["ete"] == 728

    _make_village("api-reject")
    build2 = build_tarifs_from_scrape(
        VillageScrapeResult(village_id="api-reject", url="x", bands=areches_pc_bands())
    )
    resp = api_client.post(
        _action_url(build2.approval_id),
        {"action": "reject", "reject_reason": "grille illisible"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["reject_reason"] == "grille illisible"
    assert Village.objects.get(pk="api-reject").tarifs == ORIGINAL_TARIFS


# ─── Reviewer auto-selection ──────────────────────────────────────────────


@pytest.mark.django_db
def test_change_form_preselects_the_signed_in_user_as_reviewer(staff_client):
    _make_village("rev-initial")
    build = build_tarifs_from_scrape(
        VillageScrapeResult(village_id="rev-initial", url="x", bands=areches_pc_bands())
    )
    approval = TariffApproval.objects.get(pk=build.approval_id)

    from apps.tariff_scraper.admin import TariffApprovalAdmin
    from django.contrib.admin.sites import site

    model_admin = TariffApprovalAdmin(TariffApproval, site)
    request = type("R", (), {"user": staff_client.user, "GET": {}})()

    initial = model_admin.get_changeform_initial_data(request)

    assert initial["reviewed_by"] == staff_client.user.pk
    assert approval.reviewed_by is None  # untouched until saved


@pytest.mark.django_db
def test_the_service_sets_the_reviewer_not_the_form(staff_client):
    """Attribution comes from the decision, never from opening the form.

    `status` is readonly now, so a review can only land through
    approve/reject/revert — each of which stamps the acting user itself.
    """
    _make_village("rev-save")
    build = build_tarifs_from_scrape(
        VillageScrapeResult(village_id="rev-save", url="x", bands=areches_pc_bands())
    )
    approval = TariffApproval.objects.get(pk=build.approval_id)

    staff_client.post(
        reverse("admin:tariff_scraper_tariffapproval_approve", args=[approval.pk])
    )

    approval.refresh_from_db()
    assert approval.status == STATUS_APPROVED
    assert approval.reviewed_by == staff_client.user
    assert approval.reviewed_at is not None


@pytest.mark.django_db
def test_existing_reviewer_is_never_overwritten(staff_client):
    User = get_user_model()
    other = User.objects.create_user("other", password="x")

    _make_village("rev-keep")
    build = build_tarifs_from_scrape(
        VillageScrapeResult(village_id="rev-keep", url="x", bands=areches_pc_bands())
    )
    approval = TariffApproval.objects.get(pk=build.approval_id)
    approval.reviewed_by = other
    approval.reviewed_at = timezone.now() - timedelta(days=1)
    approval.save(update_fields=["reviewed_by", "reviewed_at"])

    # Saving the form must not re-attribute a review someone else made.
    staff_client.post(
        reverse("admin:tariff_scraper_tariffapproval_change", args=[approval.pk]),
        {
            "village": "rev-keep",
            "source_url": "",
            "bands_count": approval.bands_count,
            "reject_reason": "deja arbitre",
            "reviewed_by": other.pk,
        },
    )

    approval.refresh_from_db()
    assert approval.reviewed_by == other


@pytest.mark.django_db
def test_pending_approval_is_not_attributed_to_anyone(staff_client):
    _make_village("rev-pending-save")
    build = build_tarifs_from_scrape(
        VillageScrapeResult(
            village_id="rev-pending-save", url="x", bands=areches_pc_bands()
        )
    )
    approval = TariffApproval.objects.get(pk=build.approval_id)

    staff_client.post(
        reverse("admin:tariff_scraper_tariffapproval_change", args=[approval.pk]),
        {
            "village": "rev-pending-save",
            "status": STATUS_PENDING,
            "source_url": "",
            "bands_count": approval.bands_count,
            "reject_reason": "",
        },
    )

    approval.refresh_from_db()
    assert approval.status == STATUS_PENDING
    assert approval.reviewed_by is None
