"""Tests for verify_ot_urls management command."""
from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command

from apps.scraper.services.ot_urls import VTF_OT_URLS


def _make_biarritz():
    from apps.catalog.models import Village
    from common.enums import EnvCode, Region

    return Village.objects.create(
        id="biarritz",
        nom="Biarritz",
        region=Region.AQUITAINE_LANDES,
        env_emoji="🌊",
        env_code=EnvCode.SEA,
        has_loc=False,
        ski=False,
        ouverture="",
        tarifs={},
        vtf_slug="le-domaine-de-francon",
        vtf_department="pyrenees-atlantiques",
        vtf_city="biarritz",
    )


@pytest.mark.django_db
def test_verify_ot_urls_reports_missing_mappings():
    from apps.catalog.models import Village
    from common.enums import EnvCode, Region

    Village.objects.create(
        id="test-village-no-ot",
        nom="Test Village",
        region=Region.AQUITAINE_LANDES,
        env_emoji="🌊",
        env_code=EnvCode.SEA,
        has_loc=False,
        ski=False,
        ouverture="",
        tarifs={},
        vtf_slug="test",
        vtf_department="test",
        vtf_city="test",
    )

    out = StringIO()
    call_command("verify_ot_urls", "--only-missing", stdout=out)
    output = out.getvalue()
    assert "test-village-no-ot" in output


@pytest.mark.django_db
def test_verify_ot_urls_dry_run_lists_configured_urls():
    _make_biarritz()
    out = StringIO()
    call_command(
        "verify_ot_urls",
        "--village",
        "biarritz",
        "--dry-run",
        stdout=out,
    )
    output = out.getvalue()
    assert "biarritz" in output
    assert VTF_OT_URLS["biarritz"] in output


@pytest.mark.django_db
@patch("apps.scraper.management.commands.verify_ot_urls.requests.Session")
def test_verify_ot_urls_marks_http_200_as_ok(mock_session_cls):
    _make_biarritz()
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.url = VTF_OT_URLS["biarritz"]
    session.get.return_value = response
    mock_session_cls.return_value = session

    out = StringIO()
    call_command("verify_ot_urls", "--village", "biarritz", stdout=out)
    assert "OK" in out.getvalue()
