"""Tests for Django admin scraper control panel."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.scraper.models import ScrapingCandidate, ScrapingImportLog, ScrapingJob


@pytest.fixture
def admin_user(db):
    User = get_user_model()
    return User.objects.create_superuser("admin_scraper", "admin@test.com", "pass")


@pytest.fixture
def admin_client_logged(admin_user, client):
    client.force_login(admin_user)
    return client


@pytest.fixture
def village_biarritz(db):
    from apps.catalog.models import Village
    from common.enums import EnvCode, Region

    return Village.objects.create(
        id="biarritz",
        nom="Biarritz",
        nom2="Domaine de Françon",
        region=Region.AQUITAINE_LANDES,
        env_emoji="🌊",
        env_code=EnvCode.SEA,
        has_loc=False,
        ski=False,
        ouverture="",
        tarifs={},
        bebe_club=False,
        forfait_rm=False,
        qf_exc=False,
        enf_solo_half=False,
        vtf_slug="le-domaine-de-francon",
    )


@pytest.fixture
def scraping_job(db, village_biarritz):
    return ScrapingJob.objects.create(
        id="scrape-biarritz-test",
        target_type="village",
        target_id="biarritz",
        sources=["google_places", "tripadvisor", "ot_local"],
        radius_km=30,
        status="queued",
        triggered_by="test",
    )


@pytest.fixture
def scraping_candidate(db, scraping_job, village_biarritz):
    return ScrapingCandidate.objects.create(
        id="cand-admin-hide",
        job=scraping_job,
        village=village_biarritz,
        region="Aquitaine / Landes",
        source="google_places",
        source_url="https://example.com/competitor",
        source_id="competitor-admin-001",
        nom="Competitor Surf School",
        type_emoji="surf",
        price_adult=40,
        price_child=30,
        distance_km=2.0,
        status="new",
    )


@pytest.mark.django_db
class TestScraperAdminViews:
    CONTROL_URL = reverse("admin:scraper_control")
    START_URL = reverse("admin:scraper_start")
    STOP_URL = reverse("admin:scraper_stop")

    def test_control_page_requires_login(self, client):
        resp = client.get(self.CONTROL_URL)
        assert resp.status_code == 302
        assert "login" in resp.url

    def test_control_page_renders_for_staff(
        self, admin_client_logged, village_biarritz
    ):
        resp = admin_client_logged.get(self.CONTROL_URL)
        assert resp.status_code == 200
        assert "Scraper d'activités" in resp.content.decode()

    def test_start_creates_job_and_redirects(
        self, admin_client_logged, village_biarritz
    ):
        with patch("apps.scraper.tasks.task_run_scraping_job.delay") as mock_delay:
            resp = admin_client_logged.post(
                self.START_URL,
                {
                    "target": "village",
                    "village_id": "biarritz",
                    "sources": ["google_places", "ot_local"],
                    "radius_km": 25,
                },
            )
        assert resp.status_code == 302
        job = ScrapingJob.objects.get(target_id="biarritz")
        assert job.sources == ["google_places", "ot_local"]
        assert job.radius_km == 25
        mock_delay.assert_called_once_with(job.id)

    def test_start_blocks_when_job_already_running(
        self, admin_client_logged, village_biarritz, scraping_job
    ):
        with patch("apps.scraper.tasks.task_run_scraping_job.delay"):
            resp = admin_client_logged.post(
                self.START_URL,
                {"target": "village", "village_id": "biarritz"},
            )
        assert resp.status_code == 302
        assert ScrapingJob.objects.count() == 1

    def test_stop_cancels_active_job(
        self, admin_client_logged, scraping_job
    ):
        resp = admin_client_logged.post(
            self.STOP_URL,
            {"job_id": scraping_job.id},
        )
        assert resp.status_code == 302
        scraping_job.refresh_from_db()
        assert scraping_job.status == "failed"
        assert scraping_job.result_summary.get("cancelled") is True

    def test_status_endpoint_returns_json(
        self, admin_client_logged, scraping_job
    ):
        url = reverse("admin:scraper_status", kwargs={"job_id": scraping_job.id})
        resp = admin_client_logged.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert data["jobId"] == scraping_job.id
        assert data["status"] == "queued"
        assert data["isActive"] is True

    def test_candidate_changelist_shows_hide_button(
        self, admin_client_logged, scraping_candidate
    ):
        url = reverse("admin:scraper_scrapingcandidate_changelist")

        resp = admin_client_logged.get(url)

        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Hide" in content
        assert reverse(
            "admin:scraper_scrapingcandidate_hide",
            args=[scraping_candidate.pk],
        ) in content

    def test_candidate_hide_button_marks_candidate_hidden(
        self, admin_client_logged, scraping_candidate
    ):
        url = reverse(
            "admin:scraper_scrapingcandidate_hide",
            args=[scraping_candidate.pk],
        )

        resp = admin_client_logged.post(url)

        assert resp.status_code == 302
        scraping_candidate.refresh_from_db()
        assert scraping_candidate.status == "hidden"
        assert ScrapingImportLog.objects.filter(
            candidate=scraping_candidate,
            action="hide",
            reason="Hidden from Django admin",
        ).exists()

    def test_hidden_candidate_changelist_shows_unhide_button(
        self, admin_client_logged, scraping_candidate
    ):
        scraping_candidate.status = "hidden"
        scraping_candidate.save(update_fields=["status"])
        url = reverse("admin:scraper_scrapingcandidate_changelist")

        resp = admin_client_logged.get(url)

        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Unhide" in content
        assert reverse(
            "admin:scraper_scrapingcandidate_unhide",
            args=[scraping_candidate.pk],
        ) in content

    def test_candidate_unhide_button_marks_candidate_new(
        self, admin_client_logged, scraping_candidate
    ):
        scraping_candidate.status = "hidden"
        scraping_candidate.save(update_fields=["status"])
        url = reverse(
            "admin:scraper_scrapingcandidate_unhide",
            args=[scraping_candidate.pk],
        )

        resp = admin_client_logged.post(url)

        assert resp.status_code == 302
        scraping_candidate.refresh_from_db()
        assert scraping_candidate.status == "new"
        assert ScrapingImportLog.objects.filter(
            candidate=scraping_candidate,
            action="unhide",
            reason="Unhidden from Django admin",
        ).exists()
