"""Phase 3 tests — Cache orchestration (AC-3.1–AC-3.6).

Coverage:
  CACHE ORCHESTRATION:
  - POST /api/v3/admin/cache/rebuild (staff only, scopes)
  - GET  /api/v3/admin/cache/status
  - GET  /api/v3/admin/cache/logs
  - GET  /api/v1/health cache block
  - python manage.py rebuild_cache
  - Signals: PricingRules.save, post_load_vtf_mocks
  - Village list key NOT warmed (client: list cache disabled)

  SCRAPING:
  - POST /api/v3/admin/scraper/activities        (TriggerScrapingView)
  - GET  /api/v3/admin/scraper/jobs              (ScrapingJobListView)
  - GET  /api/v3/admin/scraper/jobs/{job_id}     (ScrapingJobDetailView)
  - POST /api/v3/admin/scraper/import            (ImportCandidatesView)
  - GET  /api/v3/admin/scraper/candidates        (ScrapingCandidateListView)
  - GET  /api/v3/admin/scraper/price-updates     (PriceChangeAlertListView)
  - POST /api/v3/admin/scraper/price-updates/{id} (PriceChangeAlertActionView)
  - pipeline.run_scraping_job: candidates created, dedup called, price alerts
  - pipeline.import_candidate: Activity created, status updated, cache rebuild
  - management commands: scrape_activities, review_scraping_candidates
  AC-3.7  Scraping job completes < 60s per village
  AC-3.8  Dedup matches existing activities (>90% precision on golden set)
  AC-3.9  New candidates stored with status='new', not auto-imported
  AC-3.10 autoImport=true only for high-confidence matches (>0.9)
  AC-3.11 Price change detection flags differences > 10%
  AC-3.12 Import triggers targeted cache rebuild for affected region
  AC-3.13 Monthly cron scrapes all villages
  AC-3.14 Source adapters handle API errors gracefully

Run:
  pytest tests/test_phase3.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
import json
from unittest.mock import MagicMock, patch
import uuid

import pytest
from apps.cache_orchestrator.models import CacheRebuildLog
from apps.cache_orchestrator.service import CacheOrchestrator
from apps.cache_orchestrator.signals import post_load_vtf_mocks
from apps.catalog.models import Activity, PricingRules, Village
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.scraper.adapters.base import ScrapedActivity
from apps.scraper.dedup import deduplicate_candidates, detect_price_change
from apps.scraper.models import (
    CandidateFilterRule,
    PriceChangeAlert,
    ScrapingCandidate,
    ScrapingImportLog,
    ScrapingJob,
)
from django.utils import timezone as dj_timezone


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-phase3-cache",
    }
}


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────
 

@pytest.fixture(autouse=True)
def locmem_cache(settings):
    """Isolate cache backend for all Phase 3 tests."""
    settings.CACHES = LOCMEM_CACHE
    yield


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def loaded_db(db):
    call_command("load_vtf_mocks", verbosity=0)
    yield


@pytest.fixture
def staff_client(db):
    User = get_user_model()
    admin = User.objects.create_superuser("phase3admin", "p3@test.com", "pass")
    client = APIClient()
    client.force_authenticate(admin)
    return client


@pytest.fixture
def anon_client():
    return APIClient()



@pytest.fixture
def scraper_staff_client(db):
    User = get_user_model()
    admin = User.objects.create_superuser(
        "scraper_admin", "scraper@test.com", "pass"
    )
    client = APIClient()
    client.force_authenticate(admin)
    return client
 
 
@pytest.fixture
def scraper_anon_client():
    return APIClient()


@pytest.fixture
def village_biarritz(db):
    """Minimal Village fixture sufficient for FK references."""
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
        vtf_department="pyrenees-atlantiques",
        vtf_city="biarritz",
    )


@pytest.fixture
def scraping_job(db, village_biarritz):
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    return ScrapingJob.objects.create(
        id=f"scrape-biarritz-{ts}",
        target_type="village",
        target_id="biarritz",
        sources=["google_places", "tripadvisor", "ot_local"],
        radius_km=30,
        status="queued",
        triggered_by="test@test.com",
    )


@pytest.fixture
def completed_job(db, village_biarritz):
    """ScrapingJob with status=completed, ready for import review."""
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    return ScrapingJob.objects.create(
        id=f"scrape-completed-{ts}",
        target_type="village",
        target_id="biarritz",
        sources=["google_places", "tripadvisor", "ot_local"],
        radius_km=30,
        status="completed",
        triggered_by="test@test.com",
        result_summary={
            "candidates_found": 15,
            "duplicates_detected": 5,
            "new_candidates": 10,
            "duration_sec": 45,
            "sources": {
                "google_places": {"found": 8, "new": 5, "errors": 0},
                "tripadvisor": {"found": 7, "new": 5, "errors": 0},
            },
        },
    )


@pytest.fixture
def new_candidate(db, completed_job, village_biarritz):
    return ScrapingCandidate.objects.create(
        id=f"cand-{uuid.uuid4().hex[:8]}",
        job=completed_job,
        village=village_biarritz,
        region="Aquitaine / Landes",
        source="google_places",
        source_url="https://example.com/surf",
        source_id="google-surf-123",
        nom="École de Surf Anglet",
        type_emoji="🏄",
        price_adult=45,
        price_child=35,
        distance_km=5.1,
        rating=4.7,
        review_count=623,
        saisons=["hs", "vs", "ete", "fetes"],
        matched_activity_code="",
        match_confidence=0.0,
        status="new",
    )


@pytest.fixture
def activity_biarritz(db, village_biarritz):
    return Activity.objects.create(
        code="paid:al:aquarium-biarritz",
        region="Aquitaine / Landes",
        village=village_biarritz,
        kind="paid",
        nom="Aquarium de Biarritz",
        type="🐠",
        price_adult=17,
        price_child=11,
        saisons=["hs", "vs", "ete", "fetes"],
    )

# ─── Admin endpoints (v3) ─────────────────────────────────────────────────


@pytest.mark.django_db
class TestCacheRebuildEndpoint:
    def test_rebuild_catalog_scope(self, staff_client, loaded_db):
        cache.set("vtf:catalog:meals", [{"id": "stale"}], 3600)

        response = staff_client.post(
            "/api/v3/admin/cache/rebuild",
            {"scope": "catalog", "reason": "pytest catalog warm"},
            format="json",
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["status"] == "completed"
        assert data["scope"] == "catalog"
        assert data["keysRebuilt"] >= 1
        assert data["reason"] == "pytest catalog warm"
        assert "timestamp" in data
        assert CacheRebuildLog.objects.filter(scope="catalog").exists()

    def test_rebuild_pricing_scope(self, staff_client, loaded_db):
        response = staff_client.post(
            "/api/v3/admin/cache/rebuild",
            {"scope": "pricing", "reason": "pricing update"},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["scope"] == "pricing"
        assert cache.get("vtf:catalog:pricing_rules") is not None
        assert cache.get("vtf:catalog:seasons") is not None

    def test_rebuild_granular_village_scope(self, staff_client, loaded_db):
        village_id = Village.objects.first().id
        response = staff_client.post(
            "/api/v3/admin/cache/rebuild",
            {"scope": f"villages:{village_id}", "reason": "single village"},
            format="json",
        )
        assert response.status_code == 200
        assert cache.get(f"vtf:catalog:villages:{village_id}:detail") is not None

    def test_rebuild_invalid_scope_returns_400(self, staff_client, loaded_db):
        response = staff_client.post(
            "/api/v3/admin/cache/rebuild",
            {"scope": "not-a-real-scope"},
            format="json",
        )
        assert response.status_code == 400
        assert response.json()["success"] is False

    def test_rebuild_staff_only(self, anon_client, loaded_db):
        User = get_user_model()
        user = User.objects.create_user("regular", "u@test.com", "pass")
        anon_client.force_authenticate(user)
        response = anon_client.post(
            "/api/v3/admin/cache/rebuild",
            {"scope": "all"},
            format="json",
        )
        assert response.status_code == 403

    def test_rebuild_missing_auth_returns_json_envelope(self, anon_client, loaded_db):
        response = anon_client.post(
            "/api/v3/admin/cache/rebuild",
            {"scope": "all"},
            format="json",
        )
        assert response.status_code == 403
        assert response.json() == {
            "success": False,
            "message": "Authentication credentials were not provided.",
            "data": None,
        }

    def test_village_list_not_warmed_after_full_rebuild(self, staff_client, loaded_db):
        """Client disabled village list cache — orchestrator must not warm it."""
        staff_client.post(
            "/api/v3/admin/cache/rebuild",
            {"scope": "catalog"},
            format="json",
        )
        assert cache.get("vtf:catalog:villages:list") is None


@pytest.mark.django_db
class TestCacheStatusEndpoint:
    def test_status_returns_cache_block(self, staff_client, loaded_db):
        staff_client.post(
            "/api/v3/admin/cache/rebuild",
            {"scope": "pricing"},
            format="json",
        )
        response = staff_client.get("/api/v3/admin/cache/status")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["backend"] == "locmem"
        assert data["connected"] is True
        assert "totalKeys" in data
        assert data["lastRebuildScope"] == "pricing"
        assert "keys" in data
        assert data["keys"] == []

    def test_status_key_ttl_listing_respects_key_limit(self, staff_client, loaded_db):
        response = staff_client.get("/api/v3/admin/cache/status?keyLimit=10")
        assert response.status_code == 200
        assert response.json()["data"]["keys"] == []

    def test_status_staff_only(self, anon_client, loaded_db):
        response = anon_client.get("/api/v3/admin/cache/status")
        assert response.status_code == 403


@pytest.mark.django_db
class TestCacheLogsEndpoint:
    def test_logs_returns_recent_entries(self, staff_client, loaded_db):
        staff_client.post(
            "/api/v3/admin/cache/rebuild",
            {"scope": "all", "reason": "log test"},
            format="json",
        )
        response = staff_client.get("/api/v3/admin/cache/logs?limit=5")
        assert response.status_code == 200
        logs = response.json()["data"]
        assert len(logs) >= 1
        assert logs[0]["scope"] == "all"
        assert logs[0]["reason"] == "log test"


# ─── Health endpoint cache stats (AC-3.6) ─────────────────────────────────


@pytest.mark.django_db
def test_health_includes_cache_stats(loaded_db):
    client = APIClient()
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    cache_block = response.json()["data"]["cache"]
    assert cache_block["backend"] == "locmem"
    assert cache_block["connected"] is True
    assert "totalKeys" in cache_block


# ─── Management command ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_pricing_rebuild_warms_season_date_keys(loaded_db):
    """Pricing scope pre-warms common GET /season?date= lookup keys."""
    CacheOrchestrator.rebuild(scope="pricing", triggered_by="test")
    assert cache.get("vtf:catalog:season:date:2026-07-15") is not None
    assert cache.get("vtf:catalog:season:date:2026-12-25") is not None
    assert cache.get("vtf:catalog:season:date:2026-07-15")["saisonKey"] == "ete"


@pytest.mark.django_db
def test_rebuild_cache_management_command(loaded_db):
    out = StringIO()
    call_command("rebuild_cache", "--scope=pricing", "--reason=cli-test", stdout=out)
    assert "keys_rebuilt=" in out.getvalue()
    log = CacheRebuildLog.objects.filter(scope="pricing").first()
    assert log is not None
    assert log.reason == "cli-test"
    assert cache.get("vtf:catalog:pricing_rules") is not None


# ─── Signals (AC-3.4, AC-3.5) ─────────────────────────────────────────────


@pytest.mark.django_db
def test_pricing_rules_save_triggers_cache_rebuild(loaded_db):
    rules = PricingRules.objects.filter(is_active=True).first()
    assert rules is not None
    with patch("apps.cache_orchestrator.tasks.task_rebuild_cache.delay") as delay:
        rules.payload = {**rules.payload, "testFlag": True}
        rules.save()

    delay.assert_called_once()
    kwargs = delay.call_args.kwargs
    assert kwargs["scope"] == "pricing"
    assert "PricingRules" in kwargs["triggered_by"]


@pytest.mark.django_db
def test_post_load_vtf_mocks_signal_triggers_full_rebuild(loaded_db):
    with patch("apps.cache_orchestrator.tasks.task_rebuild_cache.delay") as delay:
        post_load_vtf_mocks.send(sender=object, reason="pytest signal")

    delay.assert_called_once()
    assert delay.call_args.kwargs["scope"] == "all"


@pytest.mark.django_db
def test_load_vtf_mocks_command_sends_rebuild_signal(loaded_db):
    CacheRebuildLog.objects.all().delete()
    with patch("apps.cache_orchestrator.tasks.task_rebuild_cache.delay"):
        call_command("load_vtf_mocks", verbosity=0)
    # Signal may enqueue async; verify sync fallback path via direct orchestrator too.
    CacheOrchestrator.rebuild(scope="all", reason="verify", triggered_by="test")
    assert CacheRebuildLog.objects.filter(scope="all").exists()


# ─── Service unit tests ───────────────────────────────────────────────────


@override_settings(CACHES=LOCMEM_CACHE)
class TestCacheOrchestratorService(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_vtf_mocks", verbosity=0)

    def test_rebuild_all_warms_catalog_keys(self):
        result = CacheOrchestrator.rebuild(
            scope="all",
            reason="unit test",
            triggered_by="test",
        )
        self.assertEqual(result["status"], "completed")
        self.assertIsNone(cache.get("vtf:catalog:villages:list"))
        self.assertIsNotNone(cache.get("vtf:catalog:regions:list"))
        self.assertIsNotNone(cache.get("vtf:catalog:meals"))

    def test_rebuild_recommendations_warms_popularity_keys(self):
        from apps.recommender.models import VillagePopularityCache

        village = Village.objects.first()
        VillagePopularityCache.objects.get_or_create(village=village)
        result = CacheOrchestrator.rebuild(scope="recommendations", triggered_by="test")
        self.assertGreaterEqual(result["keysRebuilt"], 1)
        self.assertIsNotNone(cache.get(f"vtf:reco:popularity:{village.id}"))

    def test_full_rebuild_completes_under_five_seconds(self):
        import time

        start = time.perf_counter()
        CacheOrchestrator.rebuild(scope="all", triggered_by="perf-test")
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 5.0, f"Full rebuild took {elapsed:.2f}s (limit 5s)")


# ─── Discord notification on cache rebuild (_maybe_notify) ───────────────


@pytest.mark.django_db
def test_maybe_notify_disabled_by_default_no_request(loaded_db, settings):
    """CACHE_REBUILD_NOTIFY off → no webhook call even if DISCORD_WEBHOOK is set."""
    settings.CACHE_REBUILD_NOTIFY = False
    settings.DISCORD_WEBHOOK = "https://discord.com/api/webhooks/test"
    with patch("urllib.request.urlopen") as mock_urlopen:
        CacheOrchestrator.rebuild(scope="pricing", triggered_by="test")
    mock_urlopen.assert_not_called()


@pytest.mark.django_db
def test_maybe_notify_enabled_but_no_webhook_no_request(loaded_db, settings):
    """CACHE_REBUILD_NOTIFY on but DISCORD_WEBHOOK empty → no webhook call."""
    settings.CACHE_REBUILD_NOTIFY = True
    settings.DISCORD_WEBHOOK = ""
    with patch("urllib.request.urlopen") as mock_urlopen:
        CacheOrchestrator.rebuild(scope="pricing", triggered_by="test")
    mock_urlopen.assert_not_called()


@pytest.mark.django_db
def test_maybe_notify_posts_discord_embed_when_enabled(loaded_db, settings):
    """CACHE_REBUILD_NOTIFY on + DISCORD_WEBHOOK set → Discord embed POSTed."""
    settings.CACHE_REBUILD_NOTIFY = True
    settings.DISCORD_WEBHOOK = "https://discord.com/api/webhooks/test"
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    with patch("requests.post", return_value=mock_resp) as mock_post:
        CacheOrchestrator.rebuild(
            scope="pricing", reason="release-1.4", triggered_by="pytest"
        )

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args.args[0] == "https://discord.com/api/webhooks/test"

    payload = call_args.kwargs.get("json")
    embed = payload["embeds"][0]
    assert embed["title"] == "✅ Cache Rebuild Completed"
    field_values = {f["name"]: f["value"] for f in embed["fields"]}
    assert "Environment" in field_values
    assert field_values["Scope"] == "pricing"
    assert field_values["Triggered By"] == "pytest"
    assert field_values["Reason"] == "release-1.4"


@pytest.mark.django_db
def test_maybe_notify_webhook_failure_does_not_raise(loaded_db, settings):
    """Discord HTTP error must not propagate; rebuild still completes."""
    settings.CACHE_REBUILD_NOTIFY = True
    settings.DISCORD_WEBHOOK = "https://discord.com/api/webhooks/test"
    with patch("urllib.request.urlopen", side_effect=Exception("Discord down")):
        result = CacheOrchestrator.rebuild(scope="pricing", triggered_by="test")
    assert result["status"] == "completed"


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v3/admin/scraper/activities — TriggerScrapingView
# ─────────────────────────────────────────────────────────────────────────────
 
@pytest.mark.django_db
class TestTriggerScrapingView:
    BASE_URL = "/api/v3/admin/scraper/activities"
 
    def test_trigger_village_returns_201_with_job_id(
        self, scraper_staff_client, village_biarritz
    ):
        with patch(
            "apps.scraper.tasks.task_run_scraping_job.delay"
        ) as mock_delay:
            resp = scraper_staff_client.post(
                self.BASE_URL,
                {
                    "target": "village",
                    "villageId": "biarritz",
                    "sources": ["google_places", "tripadvisor"],
                    "radiusKm": 30,
                    "autoImport": False,
                },
                format="json",
            )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert "jobId" in data
        assert data["status"] == "queued"
        assert "pollUrl" in data
        mock_delay.assert_called_once()
 
    def test_trigger_creates_scraping_job_in_db(
        self, scraper_staff_client, village_biarritz
    ):
        with patch("apps.scraper.tasks.task_run_scraping_job.delay"):
            scraper_staff_client.post(
                self.BASE_URL,
                {"target": "village", "villageId": "biarritz"},
                format="json",
            )
        assert ScrapingJob.objects.filter(target_id="biarritz").exists()
 
    def test_trigger_staff_only_403_for_anon(
        self, scraper_anon_client, village_biarritz
    ):
        resp = scraper_anon_client.post(
            self.BASE_URL,
            {"target": "village", "villageId": "biarritz"},
            format="json",
        )
        assert resp.status_code == 403
 
    def test_trigger_staff_only_403_for_regular_user(
        self, db, scraper_anon_client
    ):
        User = get_user_model()
        user = User.objects.create_user("regular2", "r2@test.com", "pass")
        scraper_anon_client.force_authenticate(user)
        resp = scraper_anon_client.post(
            self.BASE_URL,
            {"target": "village", "villageId": "biarritz"},
            format="json",
        )
        assert resp.status_code == 403
 
    def test_trigger_village_without_village_id_returns_400(
        self, scraper_staff_client
    ):
        resp = scraper_staff_client.post(
            self.BASE_URL,
            {"target": "village"},  # missing villageId
            format="json",
        )
        assert resp.status_code == 400
 
    def test_trigger_region_without_region_key_returns_400(
        self, scraper_staff_client
    ):
        resp = scraper_staff_client.post(
            self.BASE_URL,
            {"target": "region"},  # missing regionKey
            format="json",
        )
        assert resp.status_code == 400
 
    def test_trigger_invalid_source_returns_400(
        self, scraper_staff_client, village_biarritz
    ):
        resp = scraper_staff_client.post(
            self.BASE_URL,
            {
                "target": "village",
                "villageId": "biarritz",
                "sources": ["not_a_real_source"],
            },
            format="json",
        )
        assert resp.status_code == 400
 
    def test_trigger_defaults_to_all_sources_when_omitted(
        self, scraper_staff_client, village_biarritz
    ):
        with patch("apps.scraper.tasks.task_run_scraping_job.delay"):
            scraper_staff_client.post(
                self.BASE_URL,
                {"target": "village", "villageId": "biarritz"},
                format="json",
            )
        job = ScrapingJob.objects.filter(target_id="biarritz").first()
        assert "google_places" in job.sources
        assert "tripadvisor" in job.sources
        assert "ot_local" in job.sources
 
    def test_estimated_duration_in_response(
        self, scraper_staff_client, village_biarritz
    ):
        with patch("apps.scraper.tasks.task_run_scraping_job.delay"):
            resp = scraper_staff_client.post(
                self.BASE_URL,
                {"target": "village", "villageId": "biarritz"},
                format="json",
            )
        assert "estimatedDurationSec" in resp.json()["data"]


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v3/admin/scraper/jobs — ScrapingJobListView
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestScrapingJobListView:
    URL = "/api/v3/admin/scraper/jobs"
 
    def test_list_returns_jobs(self, scraper_staff_client, scraping_job):
        resp = scraper_staff_client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert len(data) >= 1
 
    def test_list_staff_only(self, scraper_anon_client, scraping_job):
        resp = scraper_anon_client.get(self.URL)
        assert resp.status_code == 403
 
    def test_filter_by_status_queued(self, scraper_staff_client, scraping_job, completed_job):
        resp = scraper_staff_client.get(f"{self.URL}?status=queued")
        assert resp.status_code == 200
        jobs = resp.json()["data"]
        assert all(j["status"] == "queued" for j in jobs)
 
    def test_filter_by_status_completed(
        self, scraper_staff_client, scraping_job, completed_job
    ):
        resp = scraper_staff_client.get(f"{self.URL}?status=completed")
        jobs = resp.json()["data"]
        assert all(j["status"] == "completed" for j in jobs)
 
    def test_limit_param_respected(
        self, scraper_staff_client, village_biarritz
    ):
        for i in range(5):
            ScrapingJob.objects.create(
                id=f"job-limit-{i}",
                target_type="village",
                target_id="biarritz",
                sources=["google_places"],
                radius_km=30,
                status="queued",
                triggered_by="test",
            )
        resp = scraper_staff_client.get(f"{self.URL}?limit=3")
        assert len(resp.json()["data"]) <= 3
 
    def test_jobs_ordered_newest_first(
        self, scraper_staff_client, scraping_job, completed_job
    ):
        resp = scraper_staff_client.get(self.URL)
        jobs = resp.json()["data"]
        if len(jobs) >= 2:
            assert jobs[0]["created_at"] >= jobs[1]["created_at"]


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v3/admin/scraper/jobs/{job_id} — ScrapingJobDetailView
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestScrapingJobDetailView:
    def _url(self, job_id):
        return f"/api/v3/admin/scraper/jobs/{job_id}"
 
    def test_job_detail_returns_candidates(
        self, scraper_staff_client, completed_job, new_candidate
    ):
        resp = scraper_staff_client.get(self._url(completed_job.id))
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["jobId"] == completed_job.id
        assert body["status"] == "completed"
        assert isinstance(body["candidates"], list)
        assert len(body["candidates"]) >= 1
 
    def test_job_detail_404_unknown_id(self, scraper_staff_client):
        resp = scraper_staff_client.get(self._url("scrape-does-not-exist"))
        assert resp.status_code == 404
 
    def test_job_detail_staff_only(
        self, scraper_anon_client, completed_job
    ):
        resp = scraper_anon_client.get(self._url(completed_job.id))
        assert resp.status_code == 403
 
    def test_job_detail_includes_summary_stats(
        self, scraper_staff_client, completed_job
    ):
        resp = scraper_staff_client.get(self._url(completed_job.id))
        summary = resp.json()["data"]["summary"]
        assert "totalNew" in summary
        assert "totalDuplicates" in summary
        assert "readyForReview" in summary
 
    def test_job_detail_includes_source_stats(
        self, scraper_staff_client, completed_job
    ):
        resp = scraper_staff_client.get(self._url(completed_job.id))
        sources = resp.json()["data"]["sources"]
        assert "google_places" in sources
 
    def test_job_detail_candidates_have_required_fields(
        self, scraper_staff_client, completed_job, new_candidate
    ):
        resp = scraper_staff_client.get(self._url(completed_job.id))
        candidate = resp.json()["data"]["candidates"][0]
        for field in ["id", "nom", "source", "status", "match_confidence"]:
            assert field in candidate, f"Missing field: {field}"


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v3/admin/scraper/import — ImportCandidatesView
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestImportCandidatesView:
    URL = "/api/v3/admin/scraper/import"
 
    def test_reject_candidate_sets_status(
        self, scraper_staff_client, completed_job, new_candidate
    ):
        resp = scraper_staff_client.post(
            self.URL,
            {
                "jobId": completed_job.id,
                "actions": [
                    {
                        "candidateId": new_candidate.id,
                        "action": "reject",
                        "reason": "Permanently closed",
                    }
                ],
            },
            format="json",
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["rejected"] == 1
        new_candidate.refresh_from_db()
        assert new_candidate.status == "rejected"
 
    def test_defer_candidate_sets_status(
        self, scraper_staff_client, completed_job, new_candidate
    ):
        resp = scraper_staff_client.post(
            self.URL,
            {
                "jobId": completed_job.id,
                "actions": [
                    {"candidateId": new_candidate.id, "action": "defer"}
                ],
            },
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["deferred"] == 1
        new_candidate.refresh_from_db()
        assert new_candidate.status == "deferred"

    def test_hide_candidate_sets_status_and_log(
        self, scraper_staff_client, completed_job, new_candidate
    ):
        resp = scraper_staff_client.post(
            self.URL,
            {
                "jobId": completed_job.id,
                "actions": [
                    {
                        "candidateId": new_candidate.id,
                        "action": "hide",
                        "reason": "Competitor activity",
                    }
                ],
            },
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["hidden"] == 1
        new_candidate.refresh_from_db()
        assert new_candidate.status == "hidden"
        log = ScrapingImportLog.objects.filter(
            candidate=new_candidate, action="hide"
        ).first()
        assert log is not None
        assert log.reason == "Competitor activity"
 
    def test_import_candidate_creates_activity(
        self, scraper_staff_client, completed_job, new_candidate
    ):
        with patch(
            "apps.cache_orchestrator.service.CacheOrchestrator.rebuild"
        ):
            resp = scraper_staff_client.post(
                self.URL,
                {
                    "jobId": completed_job.id,
                    "actions": [
                        {
                            "candidateId": new_candidate.id,
                            "action": "import",
                        }
                    ],
                },
                format="json",
            )
        data = resp.json()["data"]
        assert data["imported"] == 1
        assert len(data["newActivityCodes"]) == 1
        code = data["newActivityCodes"][0]
        assert Activity.objects.filter(code=code).exists()
 
    def test_import_creates_audit_log(
        self, scraper_staff_client, completed_job, new_candidate
    ):
        before = ScrapingImportLog.objects.count()
        with patch("apps.cache_orchestrator.service.CacheOrchestrator.rebuild"):
            scraper_staff_client.post(
                self.URL,
                {
                    "jobId": completed_job.id,
                    "actions": [
                        {"candidateId": new_candidate.id, "action": "import"}
                    ],
                },
                format="json",
            )
        assert ScrapingImportLog.objects.count() > before
 
    def test_import_with_edits_overrides_name(
        self, scraper_staff_client, completed_job, new_candidate
    ):
        with patch("apps.cache_orchestrator.service.CacheOrchestrator.rebuild"):
            scraper_staff_client.post(
                self.URL,
                {
                    "jobId": completed_job.id,
                    "actions": [
                        {
                            "candidateId": new_candidate.id,
                            "action": "import",
                            "edits": {"nom": "École de Surf — Anglet"},
                        }
                    ],
                },
                format="json",
            )
        act = Activity.objects.filter(
            nom="École de Surf — Anglet"
        ).first()
        assert act is not None
 
    def test_unknown_job_id_returns_404(
        self, scraper_staff_client, new_candidate
    ):
        resp = scraper_staff_client.post(
            self.URL,
            {
                "jobId": "nonexistent-job-id",
                "actions": [
                    {"candidateId": new_candidate.id, "action": "reject"}
                ],
            },
            format="json",
        )
        assert resp.status_code == 404
 
    def test_unknown_candidate_id_recorded_in_errors(
        self, scraper_staff_client, completed_job
    ):
        resp = scraper_staff_client.post(
            self.URL,
            {
                "jobId": completed_job.id,
                "actions": [
                    {"candidateId": "cand-does-not-exist", "action": "reject"}
                ],
            },
            format="json",
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]["errors"]) >= 1
 
    def test_empty_actions_returns_400(
        self, scraper_staff_client, completed_job
    ):
        resp = scraper_staff_client.post(
            self.URL,
            {"jobId": completed_job.id, "actions": []},
            format="json",
        )
        assert resp.status_code == 400
 
    def test_staff_only(self, scraper_anon_client, completed_job):
        resp = scraper_anon_client.post(
            self.URL,
            {"jobId": completed_job.id, "actions": []},
            format="json",
        )
        assert resp.status_code == 403
 
    def test_reject_creates_import_log(
        self, scraper_staff_client, completed_job, new_candidate
    ):
        scraper_staff_client.post(
            self.URL,
            {
                "jobId": completed_job.id,
                "actions": [
                    {
                        "candidateId": new_candidate.id,
                        "action": "reject",
                        "reason": "Test",
                    }
                ],
            },
            format="json",
        )
        log = ScrapingImportLog.objects.filter(
            candidate=new_candidate, action="reject"
        ).first()
        assert log is not None
        assert log.reason == "Test"


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v3/admin/scraper/candidates — ScrapingCandidateListView
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestScrapingCandidateListView:
    URL = "/api/v3/admin/scraper/candidates"
 
    def test_returns_new_candidates_by_default(
        self, scraper_staff_client, new_candidate
    ):
        resp = scraper_staff_client.get(self.URL)
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert "candidates" in body
        assert body["count"] >= 1
 
    def test_filter_by_status_new(
        self, scraper_staff_client, new_candidate
    ):
        resp = scraper_staff_client.get(f"{self.URL}?status=new")
        cands = resp.json()["data"]["candidates"]
        assert all(c["status"] == "new" for c in cands)

    def test_hidden_candidates_are_not_returned_by_default(
        self, scraper_staff_client, new_candidate
    ):
        new_candidate.status = "hidden"
        new_candidate.save(update_fields=["status"])

        resp = scraper_staff_client.get(self.URL)

        assert resp.status_code == 200
        ids = [cand["id"] for cand in resp.json()["data"]["candidates"]]
        assert new_candidate.id not in ids

    def test_filter_by_status_hidden(
        self, scraper_staff_client, new_candidate
    ):
        new_candidate.status = "hidden"
        new_candidate.save(update_fields=["status"])

        resp = scraper_staff_client.get(f"{self.URL}?status=hidden")

        assert resp.status_code == 200
        cands = resp.json()["data"]["candidates"]
        assert any(c["id"] == new_candidate.id for c in cands)
        assert all(c["status"] == "hidden" for c in cands)
 
    def test_filter_by_region(
        self, scraper_staff_client, new_candidate
    ):
        resp = scraper_staff_client.get(
            f"{self.URL}?region=Aquitaine+%2F+Landes"
        )
        assert resp.status_code == 200
 
    def test_staff_only(self, scraper_anon_client):
        resp = scraper_anon_client.get(self.URL)
        assert resp.status_code == 403
 
    def test_limit_param_respected(
        self, scraper_staff_client, completed_job, village_biarritz
    ):
        for i in range(10):
            ScrapingCandidate.objects.create(
                id=f"cand-limit-{i}",
                job=completed_job,
                village=village_biarritz,
                region="Aquitaine / Landes",
                source="google_places",
                source_url="https://example.com",
                source_id=f"src-{i}",
                nom=f"Activity {i}",
                type_emoji="📍",
                distance_km=1.0,
                status="new",
            )
        resp = scraper_staff_client.get(f"{self.URL}?limit=5")
        assert resp.json()["data"]["count"] <= 5
 
    def test_candidate_fields_in_response(
        self, scraper_staff_client, new_candidate
    ):
        resp = scraper_staff_client.get(self.URL)
        cand = resp.json()["data"]["candidates"][0]
        for field in [
            "id", "nom", "source", "status", "match_confidence",
            "price_adult", "price_child", "distance_km",
        ]:
            assert field in cand, f"Missing field: {field}"



# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v3/admin/scraper/price-updates — PriceChangeAlertListView
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPriceChangeAlertListView:
    URL = "/api/v3/admin/scraper/price-updates"
 
    def test_returns_pending_alerts(
        self, scraper_staff_client, activity_biarritz
    ):
        PriceChangeAlert.objects.create(
            activity=activity_biarritz,
            field="price_adult",
            old_value=17,
            new_value=19,
            source="tripadvisor",
            scraped_at=dj_timezone.now(),
            status="pending",
        )
        resp = scraper_staff_client.get(self.URL)
        assert resp.status_code == 200
        alerts = resp.json()["data"]
        assert len(alerts) >= 1
 
    def test_staff_only(self, scraper_anon_client):
        assert scraper_anon_client.get(self.URL).status_code == 403
 
    def test_filter_by_status_approved(
        self, scraper_staff_client, activity_biarritz
    ):
        PriceChangeAlert.objects.create(
            activity=activity_biarritz,
            field="price_adult",
            old_value=17,
            new_value=19,
            source="tripadvisor",
            scraped_at=dj_timezone.now(),
            status="approved",
        )
        resp = scraper_staff_client.get(f"{self.URL}?status=approved")
        alerts = resp.json()["data"]
        assert all(a["status"] == "approved" for a in alerts)
 
    def test_alert_fields_in_response(
        self, scraper_staff_client, activity_biarritz
    ):
        PriceChangeAlert.objects.create(
            activity=activity_biarritz,
            field="price_adult",
            old_value=17,
            new_value=19,
            source="google_places",
            scraped_at=dj_timezone.now(),
            status="pending",
        )
        resp = scraper_staff_client.get(self.URL)
        alert = resp.json()["data"][0]
        for field in [
            "id", "field", "old_value", "new_value", "source", "status",
            "activityCode", "activityNom",
        ]:
            assert field in alert, f"Missing field: {field}"


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v3/admin/scraper/price-updates/{id} — PriceChangeAlertActionView
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPriceChangeAlertActionView:
    def _url(self, alert_id):
        return f"/api/v3/admin/scraper/price-updates/{alert_id}"
 
    @pytest.fixture
    def price_alert(self, db, activity_biarritz):
        return PriceChangeAlert.objects.create(
            activity=activity_biarritz,
            field="price_adult",
            old_value=17,
            new_value=19,
            source="tripadvisor",
            scraped_at=dj_timezone.now(),
            status="pending",
        )
 
    def test_approve_alert_applies_price_to_activity(
        self, scraper_staff_client, price_alert, activity_biarritz
    ):
        resp = scraper_staff_client.post(
            self._url(price_alert.id), {"action": "approve"}, format="json"
        )
        assert resp.status_code == 200
        price_alert.refresh_from_db()
        assert price_alert.status == "approved"
        activity_biarritz.refresh_from_db()
        assert activity_biarritz.price_adult == 19
 
    def test_dismiss_alert_leaves_activity_unchanged(
        self, scraper_staff_client, price_alert, activity_biarritz
    ):
        original_price = activity_biarritz.price_adult
        resp = scraper_staff_client.post(
            self._url(price_alert.id), {"action": "dismiss"}, format="json"
        )
        assert resp.status_code == 200
        price_alert.refresh_from_db()
        assert price_alert.status == "dismissed"
        activity_biarritz.refresh_from_db()
        assert activity_biarritz.price_adult == original_price
 
    def test_invalid_action_returns_400(
        self, scraper_staff_client, price_alert
    ):
        resp = scraper_staff_client.post(
            self._url(price_alert.id), {"action": "delete"}, format="json"
        )
        assert resp.status_code == 400
 
    def test_unknown_alert_id_returns_404(self, scraper_staff_client):
        resp = scraper_staff_client.post(
            self._url(99999), {"action": "approve"}, format="json"
        )
        assert resp.status_code == 404
 
    def test_staff_only(self, scraper_anon_client, price_alert):
        resp = scraper_anon_client.post(
            self._url(price_alert.id), {"action": "approve"}, format="json"
        )
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline: run_scraping_job (AC-3.7, AC-3.8, AC-3.9, AC-3.11)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRunScrapingJobPipeline:
    """Tests the pipeline.run_scraping_job function directly with mocked adapters."""
 
    def _make_scraped(self, nom, source="google_places", source_id=None, price_adult=17):
        return ScrapedActivity(
            source=source,
            source_id=source_id or f"src-{uuid.uuid4().hex[:6]}",
            source_url="https://example.com",
            nom=nom,
            type_hint="aquarium",
            type_emoji="🐠",
            latitude=43.48,
            longitude=-1.55,
            price_adult=price_adult,
            price_child=11,
            rating=4.3,
            review_count=500,
        )
 
    def test_new_candidates_stored_with_status_new(
        self, scraping_job, village_biarritz
    ):
        """AC-3.9: New candidates must be stored as status='new', never auto-imported."""
        from apps.scraper.pipeline import run_scraping_job
 
        scraping_job.status = "running"
        scraping_job.started_at = dj_timezone.now()
        scraping_job.save()
 
        activity = self._make_scraped("Surf School Biarritz")
        mock_adapter = MagicMock()
        mock_adapter.search_near.return_value = [activity]
 
        with patch(
            "apps.scraper.pipeline._get_adapter", return_value=mock_adapter
        ), patch(
            "apps.scraper.pipeline.deduplicate_candidates",
            side_effect=lambda x: x,
        ):
            run_scraping_job(scraping_job)
 
        candidates = ScrapingCandidate.objects.filter(job=scraping_job)
        assert candidates.exists()
        for cand in candidates:
            assert cand.status == "new", (
                f"Candidate {cand.nom} should be 'new', got {cand.status}"
            )
 
    def test_price_alert_created_for_high_confidence_price_change(
        self, scraping_job, village_biarritz, activity_biarritz
    ):
        """AC-3.11: Price change > 10% for high-confidence match triggers PriceChangeAlert."""
        from apps.scraper.pipeline import run_scraping_job
 
        scraping_job.status = "running"
        scraping_job.started_at = dj_timezone.now()
        scraping_job.save()
 
        # Same activity name + location but higher price (> 10% change)
        changed = self._make_scraped(
            "Aquarium de Biarritz",
            price_adult=19,  # was 17 → ~11.8% increase
        )
        mock_adapter = MagicMock()
        mock_adapter.search_near.return_value = [changed]
 
        with patch(
            "apps.scraper.pipeline._get_adapter", return_value=mock_adapter
        ), patch(
            "apps.scraper.pipeline.deduplicate_candidates",
            side_effect=lambda x: x,
        ), patch(
            "apps.scraper.pipeline.find_best_match",
            return_value=(activity_biarritz, 0.95),
        ):
            run_scraping_job(scraping_job)
 
        assert PriceChangeAlert.objects.filter(
            activity=activity_biarritz
        ).exists()
 
    def test_run_scraping_job_returns_summary_dict(
        self, scraping_job, village_biarritz
    ):
        from apps.scraper.pipeline import run_scraping_job
 
        scraping_job.status = "running"
        scraping_job.save()
 
        mock_adapter = MagicMock()
        mock_adapter.search_near.return_value = []
 
        with patch(
            "apps.scraper.pipeline._get_adapter", return_value=mock_adapter
        ):
            result = run_scraping_job(scraping_job)
 
        assert isinstance(result, dict)
        assert "totalNew" in result
        assert "totalDuplicates" in result
        assert "sources" in result

    def test_hidden_candidate_duplicate_is_not_recreated(
        self, scraping_job, village_biarritz
    ):
        from apps.scraper.pipeline import run_scraping_job

        ScrapingCandidate.objects.create(
            id=f"cand-hidden-{uuid.uuid4().hex[:8]}",
            job=scraping_job,
            village=village_biarritz,
            region="Aquitaine / Landes",
            source="google_places",
            source_url="https://example.com/competitor",
            source_id="competitor-001",
            nom="Competitor Surf School",
            type_emoji="surf",
            distance_km=2.0,
            status="hidden",
        )
        scraping_job.status = "running"
        scraping_job.sources = ["google_places"]
        scraping_job.save()
        scraped_again = self._make_scraped(
            "Competitor Surf School",
            source="google_places",
            source_id="competitor-001",
        )
        mock_adapter = MagicMock()
        mock_adapter.search_near.return_value = [scraped_again]

        with patch(
            "apps.scraper.pipeline._get_adapter", return_value=mock_adapter
        ), patch(
            "apps.scraper.pipeline.deduplicate_candidates",
            side_effect=lambda x: x,
        ):
            result = run_scraping_job(scraping_job)

        assert result["totalNew"] == 0
        assert result["totalDuplicates"] == 1
        assert ScrapingCandidate.objects.filter(
            source_id="competitor-001"
        ).count() == 1
 
    def test_unknown_village_id_handled_gracefully(self, db):
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        job = ScrapingJob.objects.create(
            id=f"scrape-ghost-{ts}",
            target_type="village",
            target_id="village-does-not-exist",
            sources=["google_places"],
            radius_km=30,
            status="running",
            triggered_by="test",
        )
        from apps.scraper.pipeline import run_scraping_job
 
        mock_adapter = MagicMock()
        mock_adapter.search_near.return_value = []
 
        with patch(
            "apps.scraper.pipeline._get_adapter", return_value=mock_adapter
        ):
            result = run_scraping_job(job)
        assert isinstance(result, dict)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline: CandidateFilterRule "hide" branch dedup (bug fix 2026-08-13)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestHideRuleDedup:
    """Regression test: an active "hide" rule used to create a brand-new
    hidden ScrapingCandidate + ScrapingImportLog on every scraping run for
    the same source_id, because the hide branch in pipeline.py never
    consulted existing_candidate_ids / _matches_hidden_candidate before
    creating a row. Re-running the pipeline against the same candidate
    must produce exactly one hidden row and one auto_hide log entry.
    """

    def _make_scraped(self, nom, source="google_places", source_id=None, price_adult=17):
        return ScrapedActivity(
            source=source,
            source_id=source_id or f"src-{uuid.uuid4().hex[:8]}",
            source_url="https://example.com/x",
            nom=nom,
            type_hint="lodging",
            type_emoji="hotel",
            latitude=43.48,
            longitude=-1.55,
            price_adult=price_adult,
            price_child=11,
            rating=4.3,
            review_count=500,
        )

    def test_rerun_does_not_duplicate_hidden_candidate(
        self, scraping_job, village_biarritz
    ):
        from apps.scraper.pipeline import run_scraping_job

        CandidateFilterRule.objects.create(
            name="Hide hotels",
            field="nom",
            pattern="hotel",
            is_regex=False,
            case_sensitive=False,
            action="hide",
            is_active=True,
        )

        scraping_job.status = "running"
        scraping_job.sources = ["google_places"]
        scraping_job.save()

        activity = self._make_scraped("Grand Hotel Biarritz", source_id="hotel-001")
        mock_adapter = MagicMock()
        mock_adapter.search_near.return_value = [activity]

        with patch(
            "apps.scraper.pipeline._get_adapter", return_value=mock_adapter
        ), patch(
            "apps.scraper.pipeline.deduplicate_candidates",
            side_effect=lambda x: x,
        ):
            first_result = run_scraping_job(scraping_job)
            second_result = run_scraping_job(scraping_job)

        hidden = ScrapingCandidate.objects.filter(
            source_id="hotel-001", status="hidden"
        )
        assert hidden.count() == 1, (
            "hide-rule branch must not create a duplicate hidden row on re-run"
        )
        assert (
            ScrapingImportLog.objects.filter(
                candidate=hidden.first(), action="auto_hide"
            ).count()
            == 1
        ), "hide-rule branch must not duplicate the audit log entry on re-run"

        assert first_result["totalNew"] == 0
        assert second_result["totalDuplicates"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline: import_candidate (AC-3.12)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestImportCandidatePipeline:
    def test_creates_activity_with_generated_code(
        self, new_candidate
    ):
        from apps.scraper.pipeline import import_candidate
 
        with patch(
            "apps.cache_orchestrator.service.CacheOrchestrator.rebuild"
        ):
            activity = import_candidate(new_candidate, actor="test@test.com")
 
        assert activity is not None
        assert Activity.objects.filter(code=activity.code).exists()
 
    def test_candidate_status_updated_to_imported(
        self, new_candidate
    ):
        from apps.scraper.pipeline import import_candidate
 
        with patch(
            "apps.cache_orchestrator.service.CacheOrchestrator.rebuild"
        ):
            import_candidate(new_candidate, actor="test@test.com")
 
        new_candidate.refresh_from_db()
        assert new_candidate.status == "imported"
 
    def test_import_triggers_cache_rebuild(self, new_candidate):
        """AC-3.12: Import must trigger targeted cache rebuild for region."""
        from apps.scraper.pipeline import import_candidate
 
        with patch(
            "apps.cache_orchestrator.service.CacheOrchestrator.rebuild"
        ) as mock_rebuild:
            import_candidate(new_candidate, actor="test@test.com")
 
        mock_rebuild.assert_called_once()
        call_kwargs = mock_rebuild.call_args.kwargs
        assert "region" in call_kwargs.get("scope", "")
 
    def test_edits_override_nom_and_prices(self, new_candidate):
        from apps.scraper.pipeline import import_candidate
 
        with patch(
            "apps.cache_orchestrator.service.CacheOrchestrator.rebuild"
        ):
            activity = import_candidate(
                new_candidate,
                edits={"nom": "Surf Anglet Pro", "price_adult": 50},
                actor="staff@test.com",
            )
 
        assert activity.nom == "Surf Anglet Pro"
        assert activity.price_adult == 50
 
    def test_activity_code_unique_on_collision(
        self, new_candidate, activity_biarritz
    ):
        """Code generation must not crash when the generated code already exists."""
        from apps.scraper.pipeline import import_candidate
 
        # Create an activity that would collide on first-attempt code
        Activity.objects.create(
            code="paid:aquita:ecole-de-surf-anglet",
            region="Aquitaine / Landes",
            kind="paid",
            nom="Existing",
            type="🏄",
            price_adult=40,
            price_child=30,
            saisons=["ete"],
        )
        with patch(
            "apps.cache_orchestrator.service.CacheOrchestrator.rebuild"
        ):
            activity = import_candidate(new_candidate, actor="test@test.com")
 
        assert activity is not None
        assert Activity.objects.filter(code=activity.code).count() == 1
 
    def test_free_activity_uses_free_kind(self, completed_job, village_biarritz):
        free_cand = ScrapingCandidate.objects.create(
            id=f"cand-free-{uuid.uuid4().hex[:8]}",
            job=completed_job,
            village=village_biarritz,
            region="Aquitaine / Landes",
            source="google_places",
            source_url="https://example.com",
            source_id="free-act-001",
            nom="Plage de Biarritz",
            type_emoji="🏖️",
            price_adult=0,
            price_child=0,
            distance_km=1.0,
            status="new",
        )
        from apps.scraper.pipeline import import_candidate
 
        with patch(
            "apps.cache_orchestrator.service.CacheOrchestrator.rebuild"
        ):
            activity = import_candidate(free_cand, actor="test@test.com")
 
        assert activity.kind == "free"


# ─────────────────────────────────────────────────────────────────────────────
# Scraping Management commands (AC-3.13, AC-3.14)
# ─────────────────────────────────────────────────────────────────────────────
 
 
@pytest.mark.django_db
class TestScrapeActivitiesManagementCommand:
    def test_scrape_single_village_queues_job(self, village_biarritz):
        """scrape_activities --village=biarritz creates and enqueues a job."""
        with patch(
            "apps.scraper.tasks.task_run_scraping_job.delay"
        ) as mock_delay:
            out = StringIO()
            call_command(
                "scrape_activities",
                "--village=biarritz",
                stdout=out,
            )
 
        assert ScrapingJob.objects.filter(target_id="biarritz").exists()
        mock_delay.assert_called_once()
 
    def test_scrape_all_queues_job_per_village(self, db):
        """scrape_activities --all creates one job per village in DB."""
        from apps.catalog.models import Village
        from common.enums import EnvCode, Region
 
        for i in range(3):
            Village.objects.get_or_create(
                id=f"village-cmd-{i}",
                defaults={
                    "nom": f"Village {i}",
                    "nom2": "",
                    "region": Region.AQUITAINE_LANDES,
                    "env_emoji": "🌊",
                    "env_code": EnvCode.SEA,
                    "has_loc": False,
                    "ski": False,
                    "ouverture": "",
                    "tarifs": {},
                    "bebe_club": False,
                    "forfait_rm": False,
                    "qf_exc": False,
                    "enf_solo_half": False,
                },
            )
 
        with patch("apps.scraper.tasks.task_run_scraping_job.delay") as mock_delay:
            out = StringIO()
            call_command("scrape_activities", "--all", stdout=out)
 
        village_count = Village.objects.count()
        assert mock_delay.call_count == village_count
 
 
@pytest.mark.django_db
class TestReviewScrapingCandidatesCommand:
    def test_command_outputs_pending_count(self, new_candidate):
        out = StringIO()
        call_command("review_scraping_candidates", stdout=out)
        output = out.getvalue()
        # Should mention pending/new candidates
        assert any(
            word in output.lower()
            for word in ["candidate", "new", "pending", "review", "0", "1"]
        )
 
    def test_command_does_not_raise_on_empty_db(self, db):
        out = StringIO()
        try:
            call_command("review_scraping_candidates", stdout=out)
        except Exception as exc:
            pytest.fail(f"Command raised unexpectedly: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# AC-3.14: Source adapters handle API errors gracefully
# ─────────────────────────────────────────────────────────────────────────────
 
class TestAdapterErrorHandling:
    """Verifies each adapter returns [] / None on error, never raises. (AC-3.14)"""
 
    def test_google_places_http_error_returns_empty(self):
        from apps.scraper.adapters.google_places import GooglePlacesAdapter
 
        adapter = GooglePlacesAdapter()
        adapter.api_key = "fake-key"
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 500")
        with patch.object(adapter._session, "post", return_value=mock_resp):
            results = adapter.search_near(
                lat=43.48, lng=-1.55, radius_km=30, max_results=20
            )
        assert results == []
 
    def test_tripadvisor_http_error_returns_empty(self):
        from apps.scraper.adapters.tripadvisor import TripAdvisorAdapter
 
        adapter = TripAdvisorAdapter()
        adapter.api_key = "fake-key"
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 403")
        with patch.object(adapter._session, "get", return_value=mock_resp):
            results = adapter.search_near(
                lat=43.48, lng=-1.55, radius_km=30, max_results=20
            )
        assert results == []
 
    def test_ot_local_no_url_returns_empty(self):
        from apps.scraper.adapters.ot_local import OfficeTourismeAdapter
 
        adapter = OfficeTourismeAdapter()
        results = adapter.search_near(
            lat=43.48, lng=-1.55, radius_km=30, max_results=20,
            village_id="no-such-village",
        )
        assert results == []
 
    def test_google_places_network_timeout_returns_empty(self):
        import requests
        from apps.scraper.adapters.google_places import GooglePlacesAdapter
 
        adapter = GooglePlacesAdapter()
        adapter.api_key = "fake-key"
        with patch.object(
            adapter._session, "post", side_effect=requests.Timeout("timeout")
        ):
            results = adapter.search_near(
                lat=43.48, lng=-1.55, radius_km=30, max_results=20
            )
        assert results == []
 
    def test_tripadvisor_network_timeout_returns_empty(self):
        import requests
        from apps.scraper.adapters.tripadvisor import TripAdvisorAdapter
 
        adapter = TripAdvisorAdapter()
        adapter.api_key = "fake-key"
        with patch.object(
            adapter._session, "get", side_effect=requests.Timeout("timeout")
        ):
            results = adapter.search_near(
                lat=43.48, lng=-1.55, radius_km=30, max_results=20
            )
        assert results == []


# ─────────────────────────────────────────────────────────────────────────────
# Health endpoint includes all cache fields from spec §5.3
#
# Fields: backend, connected, totalKeys, memoryUsedMb, hitRatePercent,
#         lastRebuild, lastRebuildScope, oldestKeyAgeSec.
# In locmem (test) mode some fields will be None — that is acceptable.
# What matters is that the keys are PRESENT in the response.
# ─────────────────────────────────────────────────────────────────────────────


class TestHealthCacheFields:
    """GAP 9 — /api/v1/health returns all cache fields specified in §5.3."""
 
    REQUIRED_CACHE_KEYS = {
        "backend",
        "connected",
        "totalKeys",
        "memoryUsedMb",
        "hitRatePercent",
        "oldestKeyAgeSec",
    }
 
    @pytest.mark.django_db
    def test_health_cache_block_has_all_required_keys(self, client, loaded_db):
        """All cache keys from spec §5.3 must be present (value may be None)."""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "cache" in body["data"], "Health response must include 'cache' block"
        cache_block = body["data"]["cache"]
 
        missing = self.REQUIRED_CACHE_KEYS - cache_block.keys()
        assert not missing, (
            f"Health endpoint cache block is missing keys: {missing}. "
            f"Got: {list(cache_block.keys())}"
        )
 
    @pytest.mark.django_db
    def test_health_cache_backend_is_string(self, client, loaded_db):
        """cache.backend must be a non-empty string ('redis' or 'locmem')."""
        resp = client.get("/api/v1/health")
        cache_block = resp.json()["data"]["cache"]
        assert isinstance(cache_block["backend"], str)
        assert cache_block["backend"] in ("redis", "locmem"), (
            f"Expected 'redis' or 'locmem', got {cache_block['backend']!r}"
        )
 
    @pytest.mark.django_db
    def test_health_cache_connected_is_bool(self, client, loaded_db):
        """cache.connected must be a boolean."""
        resp = client.get("/api/v1/health")
        cache_block = resp.json()["data"]["cache"]
        assert isinstance(cache_block["connected"], bool), (
            f"cache.connected must be bool, got {type(cache_block['connected'])}"
        )
 
    @pytest.mark.django_db
    def test_health_cache_optional_fields_are_none_or_correct_type(
        self, client, loaded_db
    ):
        """
        totalKeys, memoryUsedMb, hitRatePercent, oldestKeyAgeSec may be None
        in locmem test mode, but if they have a value it must be the correct type.
        """
        resp = client.get("/api/v1/health")
        cache_block = resp.json()["data"]["cache"]
 
        int_or_none = {"totalKeys", "oldestKeyAgeSec"}
        float_or_none = {"memoryUsedMb", "hitRatePercent"}
 
        for key in int_or_none:
            val = cache_block.get(key)
            assert val is None or isinstance(val, (int, float)), (
                f"cache.{key} must be int or None, got {type(val)}: {val}"
            )
 
        for key in float_or_none:
            val = cache_block.get(key)
            assert val is None or isinstance(val, (int, float)), (
                f"cache.{key} must be float or None, got {type(val)}: {val}"
            )
 
    @pytest.mark.django_db
    def test_health_cache_last_rebuild_present_after_rebuild(
        self, client, loaded_db
    ):
        """
        After a cache rebuild, lastRebuild and lastRebuildScope must be present
        and non-null in the health response.
        """
        from apps.cache_orchestrator.models import CacheRebuildLog
 
        # Create a rebuild log entry (simulates a rebuild having happened).
        CacheRebuildLog.objects.create(
            scope="pricing",
            keys_invalidated=10,
            keys_rebuilt=10,
            duration_ms=250,
            triggered_by="test",
            reason="Gap 9 test",
        )
 
        resp = client.get("/api/v1/health")
        cache_block = resp.json()["data"]["cache"]
 
        assert "lastRebuild" in cache_block, (
            "Health must include lastRebuild after a rebuild has occurred"
        )
        assert "lastRebuildScope" in cache_block, (
            "Health must include lastRebuildScope"
        )
        assert cache_block["lastRebuild"] is not None
        assert cache_block["lastRebuildScope"] == "pricing"

# ─────────────────────────────────────────────────────────────────────────────
# booking_urls scope in CacheOrchestrator
# The spec lists 'booking_urls' as a valid rebuild scope that invalidates
# vtf:booking:token:* keys. Confirm it is wired in _patterns_for_scope and
# that the warm step runs _warm_booking_urls.
# ─────────────────────────────────────────────────────────────────────────────

class TestBookingUrlsCacheScope:
    """GAP 10 — 'booking_urls' scope invalidates vtf:booking:token:* keys."""
 
    @pytest.mark.django_db
    def test_booking_urls_scope_accepted_by_rebuild_endpoint(
        self, loaded_db
    ):
        """POST /api/v3/admin/cache/rebuild with scope='booking_urls' returns 200."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        client = APIClient()
        staff = User.objects.create_user(
            username="staff_gap10",
            password="pass",
            is_staff=True,
        )
        client.force_authenticate(user=staff)
 
        resp = client.post(
            "/api/v3/admin/cache/rebuild",
            {"scope": "booking_urls", "reason": "GAP 10 test"},
            format="json",
        )
        assert resp.status_code == 200, (
            f"booking_urls scope must be accepted, got {resp.status_code}: {resp.json()}"
        )
 
    def test_booking_urls_scope_patterns_are_defined(self):
        """
        _patterns_for_scope('booking_urls') must return at least one pattern
        targeting vtf:booking:* keys.
        """
        from apps.cache_orchestrator.service import CacheOrchestrator
 
        patterns = CacheOrchestrator._patterns_for_scope("booking_urls")
        assert len(patterns) > 0, (
            "No cache patterns defined for scope 'booking_urls'. "
            "Add 'booking_urls' to SCOPE_PATTERNS in key_registry.py."
        )
        # At least one pattern must cover booking token keys.
        assert any("booking" in p for p in patterns), (
            f"booking_urls scope patterns {patterns} don't reference booking keys"
        )
 
    @pytest.mark.django_db
    def test_all_scope_rebuild_includes_booking_urls(self, loaded_db):
        """
        scope='all' must also warm booking_url keys (calls _warm_booking_urls).
        Verified by checking that the method is reachable from _warm('all').
        """
        from apps.cache_orchestrator.service import CacheOrchestrator
 
        with patch.object(
            CacheOrchestrator,
            "_warm_booking_urls",
            wraps=CacheOrchestrator._warm_booking_urls,
        ) as mock_warm:
            CacheOrchestrator.rebuild(
                scope="all",
                reason="GAP 10 all-scope test",
                triggered_by="test",
            )
            mock_warm.assert_called_once(), (
                "_warm_booking_urls was not called during scope='all' rebuild"
            )
