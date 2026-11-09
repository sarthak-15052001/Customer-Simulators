from __future__ import annotations

from datetime import timedelta

import uuid
from datetime import timedelta, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from apps.catalog.models import Village
from apps.recommender import tasks
from apps.recommender.models import (
    RecommendationSystemState,
    VillageInteraction,
    VillagePopularityCache,
)
from apps.cache_orchestrator.models import CacheRebuildLog
from apps.cache_orchestrator.tasks import task_rebuild_cache
from apps.recommender.tasks import (
    task_check_cf_readiness,
    task_check_cf_readiness_after_estimate,
    task_refresh_popularity,
    task_train_cf_model,
)
from common.enums import EnvCode, Region
from config.celery_app import app
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from apps.scraper.models import ScrapingCandidate, ScrapingJob
from apps.scraper.tasks import (
    task_monthly_scrape_all,
    task_notify_scraping,
    task_run_scraping_job,
)

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-celery-cache",
    }
}


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
 


@pytest.fixture
def village(db) -> Village:
    return Village.objects.create(
        id="celery-village",
        nom="Celery Village",
        nom2="",
        region=Region.AQUITAINE_LANDES,
        env_emoji="sea",
        env_code=EnvCode.SEA,
        has_loc=False,
        ski=False,
        ouverture="",
        tarifs={},
        bebe_club=False,
        forfait_rm=False,
        qf_exc=False,
        enf_solo_half=False,
    )


def test_celery_app_uses_expected_beat_schedule():
    """All 6 CELERY_BEAT_SCHEDULE entries are present with correct task names."""
    schedule = app.conf.beat_schedule

    expected_tasks = {
        "refresh-popularity":     "apps.recommender.tasks.task_refresh_popularity",
        "check-cf-readiness":     "apps.recommender.tasks.task_check_cf_readiness",
        "train-cf-model":         "apps.recommender.tasks.task_train_cf_model",
        "rebuild-cache-daily-7am":"apps.cache_orchestrator.tasks.task_rebuild_cache",
        "monthly-scrape-all":     "apps.scraper.tasks.task_monthly_scrape_all",
        "scrape-header-banner":   "apps.header_scraper.tasks.task_scrape_header_banner",
    }
    for key, task_name in expected_tasks.items():
        assert key in schedule, f"'{key}' missing from beat_schedule"
        assert schedule[key]["task"] == task_name, (
            f"'{key}' task name mismatch: {schedule[key]['task']!r} != {task_name!r}"
        )


def test_beat_schedule_refresh_popularity_is_every_6_hours():
    """refresh-popularity fires every 6 hours at minute 0 (AC2.7)."""
    sched = app.conf.beat_schedule["refresh-popularity"]["schedule"]
    assert sched._orig_minute == 0 or sched._orig_minute == {0}
    hour = sched._orig_hour
    assert hour == "*/6" or getattr(hour, "step", None) == 6 or set(hour) == set(range(0, 24, 6))


def test_beat_schedule_check_cf_readiness_is_daily_0250():
    """check-cf-readiness fires daily at 02:50 AM (before train at 03:00, AC2.14)."""
    sched = app.conf.beat_schedule["check-cf-readiness"]["schedule"]
    assert sched._orig_minute == 50 or sched._orig_minute == {50}
    assert sched._orig_hour == 2 or sched._orig_hour == {2}


def test_beat_schedule_train_cf_model_is_daily_0300():
    """train-cf-model fires daily at 03:00 AM (AC2.14)."""
    sched = app.conf.beat_schedule["train-cf-model"]["schedule"]
    assert sched._orig_minute == 0 or sched._orig_minute == {0}
    assert sched._orig_hour == 3 or sched._orig_hour == {3}


def test_beat_schedule_rebuild_cache_is_daily_0700_with_kwargs():
    """rebuild-cache-daily-7am fires at 07:00 AM with correct scope kwargs (Phase 3)."""
    entry = app.conf.beat_schedule["rebuild-cache-daily-7am"]
    sched = entry["schedule"]
    assert sched._orig_minute == 0 or sched._orig_minute == {0}
    assert sched._orig_hour == 7 or sched._orig_hour == {7}
    assert entry["kwargs"]["scope"] == "all"
    assert entry["kwargs"]["reason"] == "Scheduled daily 07:00 cache rebuild"
    assert entry["kwargs"]["triggered_by"] == "system:cron"


def test_beat_schedule_monthly_scrape_is_1st_of_month_0400():
    """monthly-scrape-all fires on the 1st of each month at 04:00 AM."""
    sched = app.conf.beat_schedule["monthly-scrape-all"]["schedule"]
    assert sched._orig_minute == 0 or sched._orig_minute == {0}
    assert sched._orig_hour == 4 or sched._orig_hour == {4}
    assert sched._orig_day_of_month == 1 or sched._orig_day_of_month == {1}


def test_beat_schedule_scrape_header_banner_is_every_4_hours():
    """scrape-header-banner fires every 4 hours exactly on the hour."""
    sched = app.conf.beat_schedule["scrape-header-banner"]["schedule"]
    assert sched._orig_minute == 0 or sched._orig_minute == {0}
    hour = sched._orig_hour
    assert hour == "*/4" or getattr(hour, "step", None) == 4 or set(hour) == set(range(0, 24, 4))


def test_cache_orchestrator_task_has_expected_celery_name_and_retry_limits():

    assert task_rebuild_cache.name == "apps.cache_orchestrator.tasks.task_rebuild_cache"
    assert task_rebuild_cache.max_retries == 3


def test_recommender_tasks_have_expected_celery_names_and_retry_limits():

    assert task_refresh_popularity.name == "apps.recommender.tasks.task_refresh_popularity"
    assert task_refresh_popularity.max_retries == 3
    assert task_check_cf_readiness.name == "apps.recommender.tasks.task_check_cf_readiness"
    assert task_check_cf_readiness.max_retries == 2
    assert task_train_cf_model.name == "apps.recommender.tasks.task_train_cf_model"
    assert task_train_cf_model.max_retries == 1
    assert task_check_cf_readiness_after_estimate.name == (
        "apps.recommender.tasks.task_check_cf_readiness_after_estimate"
    )


def test_header_scraper_tasks_have_expected_celery_names_and_retry_limits():
    """header_scraper Celery tasks must be registered with the correct names and retry config."""
    from apps.header_scraper.tasks import (
        task_scrape_header_banner,
        task_scrape_header_banner_language,
    )

    assert task_scrape_header_banner.name == (
        "apps.header_scraper.tasks.task_scrape_header_banner"
    )
    assert task_scrape_header_banner.max_retries == 2

    assert task_scrape_header_banner_language.name == (
        "apps.header_scraper.tasks.task_scrape_header_banner_language"
    )
    assert task_scrape_header_banner_language.max_retries == 2

@pytest.fixture
def scraper_village(db):
    from apps.catalog.models import Village
    from common.enums import EnvCode, Region
 
    return Village.objects.create(
        id="scraper-celery-village",
        nom="Scraper Celery Village",
        nom2="",
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
    )


@pytest.fixture
def queued_job(db, scraper_village):
    ts = timezone.now().strftime("%Y%m%d-%H%M%S")
    return ScrapingJob.objects.create(
        id=f"scrape-celery-test-{ts}",
        target_type="village",
        target_id=scraper_village.id,
        sources=["google_places"],
        radius_km=30,
        status="queued",
        triggered_by="pytest:celery",
    )


@pytest.mark.django_db
def test_task_refresh_popularity_updates_cache_rows(village, monkeypatch):

    monkeypatch.setattr(
        "apps.cache_orchestrator.tasks.task_rebuild_cache.delay",
        lambda **kwargs: None,
    )
    now = timezone.now()
    interactions = [
        VillageInteraction.objects.create(
            session_id="celery-popularity",
            village=village,
            kind="view",
            value=1.0,
            metadata={},
        ),
        VillageInteraction.objects.create(
            session_id="celery-popularity",
            village=village,
            kind="simulate",
            value=1.0,
            metadata={},
        ),
        VillageInteraction.objects.create(
            session_id="celery-popularity",
            village=village,
            kind="bookmark",
            value=1.0,
            metadata={},
        ),
    ]
    VillageInteraction.objects.filter(
        pk__in=[interaction.pk for interaction in interactions]
    ).update(created_at=now - timedelta(days=1))

    result = task_refresh_popularity.apply(kwargs={"days": 30})

    assert result.successful()
    row = VillagePopularityCache.objects.get(village=village)
    assert row.views_30d == 1
    assert row.simulations_30d == 1
    assert row.bookmarks_30d == 1
    assert row.score == 9.0


@pytest.mark.django_db
def test_task_refresh_popularity_creates_zero_row_for_village_without_interactions(village, monkeypatch):

    monkeypatch.setattr(
        "apps.cache_orchestrator.tasks.task_rebuild_cache.delay",
        lambda **kwargs: None,
    )
    result = task_refresh_popularity.apply(kwargs={"days": 30})

    assert result.successful()
    row = VillagePopularityCache.objects.get(village=village)
    assert row.views_30d == 0
    assert row.simulations_30d == 0
    assert row.bookmarks_30d == 0
    assert row.score == 0.0


@override_settings(CACHES=LOCMEM_CACHE)
@pytest.mark.django_db
def test_task_check_cf_readiness_sets_false_when_thresholds_not_met():

    cache.clear()

    result = task_check_cf_readiness.apply()

    assert result.successful()
    assert cache.get("cf_model_ready") is False
    row = RecommendationSystemState.objects.get(key="cf_model_ready")
    assert row.value_bool is False
    assert row.metadata["ready"] is False


@override_settings(CACHES=LOCMEM_CACHE)
@pytest.mark.django_db
def test_task_train_cf_model_skips_when_not_ready():

    cache.clear()
    cache.set("cf_model_ready", False)

    result = task_train_cf_model.apply(kwargs={"force": False})

    assert result.successful()
    assert cache.get("vtf:reco:cf_model") is None
    row = RecommendationSystemState.objects.get(key="cf_model_training")
    assert row.value_bool is False
    assert row.metadata["status"] == "skipped_not_ready"


@override_settings(CACHES=LOCMEM_CACHE)
@pytest.mark.django_db
def test_task_train_cf_model_force_empty_matrix_updates_db(monkeypatch):


    cache.clear()
    monkeypatch.setattr(tasks, "Dataset", object)
    monkeypatch.setattr(tasks, "Reader", object)
    monkeypatch.setattr(tasks, "SVD", object)
    monkeypatch.setattr(tasks, "_collect_interaction_rows", lambda: [])

    result = task_train_cf_model.apply(kwargs={"force": True})

    assert result.successful()
    row = RecommendationSystemState.objects.get(key="cf_model_training")
    assert row.value_bool is False
    assert row.metadata["status"] == "skipped_empty_matrix"
    assert row.metadata["force"] is True


@override_settings(CACHES=LOCMEM_CACHE)
def test_task_check_cf_readiness_after_estimate_enqueues_when_not_ready(monkeypatch):

    enqueued = []
    cache.clear()
    monkeypatch.setattr(tasks.task_check_cf_readiness, "delay", lambda: enqueued.append("queued"))

    result = tasks.task_check_cf_readiness_after_estimate.apply()

    assert result.successful()
    assert enqueued == ["queued"]


@override_settings(CACHES=LOCMEM_CACHE)
@pytest.mark.django_db
def test_task_rebuild_cache_creates_log_entry(village):

    cache.clear()
    result = task_rebuild_cache.apply(
        kwargs={
            "scope": "pricing",
            "reason": "celery test",
            "triggered_by": "test:celery",
        }
    )

    assert result.successful()
    payload = result.result
    assert payload["scope"] == "pricing"
    assert payload["status"] == "completed"
    log = CacheRebuildLog.objects.filter(scope="pricing").first()
    assert log is not None
    assert log.triggered_by == "test:celery"


@override_settings(CACHES=LOCMEM_CACHE)
@pytest.mark.django_db
def test_task_refresh_popularity_enqueues_recommendations_cache_rebuild(village, monkeypatch):

    enqueued = []
    monkeypatch.setattr(
        "apps.cache_orchestrator.tasks.task_rebuild_cache.delay",
        lambda **kwargs: enqueued.append(kwargs),
    )

    result = task_refresh_popularity.apply(kwargs={"days": 30})

    assert result.successful()
    assert len(enqueued) == 1
    assert enqueued[0]["scope"] == "recommendations"


@override_settings(CACHES=LOCMEM_CACHE)
def test_task_check_cf_readiness_after_estimate_noops_when_already_ready(monkeypatch):

    enqueued = []
    cache.clear()
    cache.set("cf_model_ready", True)
    monkeypatch.setattr(tasks.task_check_cf_readiness, "delay", lambda: enqueued.append("queued"))

    result = tasks.task_check_cf_readiness_after_estimate.apply()

    assert result.successful()
    assert enqueued == []


# ─────────────────────────────────────────────────────────────────────────────
# task_run_scraping_job — Celery metadata
# ─────────────────────────────────────────────────────────────────────────────


def test_scraper_task_has_expected_celery_name_and_retry_limits():
    """task_run_scraping_job must be registered with the correct Celery name."""
    assert (
        task_run_scraping_job.name
        == "apps.scraper.tasks.task_run_scraping_job"
    )
    assert task_run_scraping_job.max_retries == 2
 
 
def test_monthly_scrape_task_celery_name():
    assert (
        task_monthly_scrape_all.name
        == "apps.scraper.tasks.task_monthly_scrape_all"
    )
 
 
def test_notify_scraping_task_celery_name():
    assert (
        task_notify_scraping.name
        == "apps.scraper.tasks.task_notify_scraping"
    )
 
 
# ─────────────────────────────────────────────────────────────────────────────
# Beat schedule — monthly scrape cron
# ─────────────────────────────────────────────────────────────────────────────
 
 
def test_beat_schedule_includes_monthly_scrape():
    """Verify the monthly cron is registered in Celery beat schedule."""
    schedule = app.conf.beat_schedule
    assert "monthly-scrape-all" in schedule, (
        "Expected 'monthly-scrape-all' in beat_schedule. "
        f"Available keys: {list(schedule.keys())}"
    )
    entry = schedule["monthly-scrape-all"]
    assert entry["task"] == "apps.scraper.tasks.task_monthly_scrape_all"
    # Should run on the 1st of each month at 04:00
    sched = entry["schedule"]
    assert sched._orig_hour == 4
    assert sched._orig_day_of_month == 1
 
 
# ─────────────────────────────────────────────────────────────────────────────
# task_run_scraping_job — happy path
# ─────────────────────────────────────────────────────────────────────────────
 
 
@pytest.mark.django_db
def test_task_run_scraping_job_happy_path(queued_job):
    """Job transitions queued → running → completed."""
    mock_result = {
        "totalNew": 3,
        "totalDuplicates": 1,
        "totalPriceAlerts": 0,
        "readyForReview": 3,
        "sources": {},
        "candidates": [],
    }
    with patch(
        "apps.scraper.pipeline.run_scraping_job", return_value=mock_result
    ):
        result = task_run_scraping_job.apply(args=[queued_job.id])
 
    assert result.successful()
    queued_job.refresh_from_db()
    assert queued_job.status == "completed"
    assert queued_job.result_summary["totalNew"] == 3
    assert queued_job.completed_at is not None
 
 
@pytest.mark.django_db
def test_task_run_scraping_job_sets_started_at(queued_job):
    with patch("apps.scraper.pipeline.run_scraping_job", return_value={}):
        task_run_scraping_job.apply(args=[queued_job.id])
 
    queued_job.refresh_from_db()
    assert queued_job.started_at is not None
 
 
@pytest.mark.django_db
def test_task_run_scraping_job_job_not_found_returns_error():
    """Missing job_id must return error dict, not raise."""
    result = task_run_scraping_job.apply(args=["scrape-does-not-exist-xyz"])
    assert result.successful()
    assert "error" in result.result
 
 
@pytest.mark.django_db
def test_task_run_scraping_job_exception_sets_failed_status(queued_job):
    """On pipeline exception: status → failed, result_summary has error key."""
    with patch(
        "apps.scraper.pipeline.run_scraping_job",
        side_effect=Exception("pipeline exploded"),
    ):
        result = task_run_scraping_job.apply(
            args=[queued_job.id],
            kwargs={},
            retries=task_run_scraping_job.max_retries,  # exhaust retries
        )

    assert result.failed()
    queued_job.refresh_from_db()
    assert queued_job.status == "failed"
    assert "error" in queued_job.result_summary
 
 
@pytest.mark.django_db
def test_task_run_scraping_job_result_includes_total_new(queued_job):
    mock_result = {"totalNew": 5, "totalDuplicates": 2}
    with patch("apps.scraper.pipeline.run_scraping_job", return_value=mock_result):
        result = task_run_scraping_job.apply(args=[queued_job.id])
 
    assert result.result["totalNew"] == 5
 
 
# ─────────────────────────────────────────────────────────────────────────────
# task_monthly_scrape_all (AC-3.13)
# ─────────────────────────────────────────────────────────────────────────────
 
 
@pytest.mark.django_db
def test_task_monthly_scrape_all_creates_one_job_per_village(db):
    """AC-3.13: Monthly cron queues exactly one ScrapingJob per Village."""
    from apps.catalog.models import Village
    from common.enums import EnvCode, Region
 
    village_ids = [f"monthly-v-{i}" for i in range(3)]
    for vid in village_ids:
        Village.objects.get_or_create(
            id=vid,
            defaults={
                "nom": f"Village {vid}",
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
 
    with patch(
        "apps.scraper.tasks.task_run_scraping_job.delay"
    ) as mock_delay, patch(
        "apps.scraper.tasks.task_notify_scraping.delay"
    ):
        result = task_monthly_scrape_all.apply()
 
    assert result.successful()
    payload = result.result
    assert payload["jobsQueued"] == Village.objects.count()
    assert mock_delay.call_count == Village.objects.count()
 
 
@pytest.mark.django_db
def test_task_monthly_scrape_all_jobs_have_correct_sources(db):
    from apps.catalog.models import Village
    from common.enums import EnvCode, Region
 
    Village.objects.get_or_create(
        id="monthly-src-v",
        defaults={
            "nom": "Monthly Src",
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
    with patch("apps.scraper.tasks.task_run_scraping_job.delay"), patch(
        "apps.scraper.tasks.task_notify_scraping.delay"
    ):
        task_monthly_scrape_all.apply()
 
    job = ScrapingJob.objects.filter(
        triggered_by="system:cron:monthly"
    ).first()
    assert job is not None
    assert "google_places" in job.sources
    assert "tripadvisor" in job.sources
    assert "ot_local" in job.sources
 
 
@pytest.mark.django_db
def test_task_monthly_scrape_all_enqueues_notification(db):
    from apps.catalog.models import Village
    from common.enums import EnvCode, Region
 
    Village.objects.get_or_create(
        id="monthly-notify-v",
        defaults={
            "nom": "Monthly Notify",
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
 
    notified = []
    with patch("apps.scraper.tasks.task_run_scraping_job.delay"), patch(
        "apps.scraper.tasks.task_notify_scraping.delay",
        side_effect=lambda **kwargs: notified.append(kwargs),
    ):
        task_monthly_scrape_all.apply()
 
    assert len(notified) == 1
    assert notified[0]["trigger"] == "monthly_cron"
 
 
# ─────────────────────────────────────────────────────────────────────────────
# task_notify_scraping
# ─────────────────────────────────────────────────────────────────────────────
 
 
@pytest.mark.django_db
def test_task_notify_scraping_no_webhook_silent(queued_job, monkeypatch):
    """No Discord webhook configured → task completes silently, no HTTP call."""
    monkeypatch.delenv("DISCORD_WEBHOOK", raising=False)
    with patch("requests.post") as mock_post:
        result = task_notify_scraping.apply(
            kwargs={"job_ids": [queued_job.id], "trigger": "manual"}
        )
    assert result.successful()
    mock_post.assert_not_called()
 
 
@pytest.mark.django_db
def test_task_notify_scraping_with_webhook_posts_to_discord(
    queued_job, scraper_village, monkeypatch
):
    """When new candidates exist and webhook configured → Discord POST fired."""
    monkeypatch.setenv(
        "DISCORD_WEBHOOK", "https://discord.com/api/webhooks/test"
    )
    # Create a 'new' candidate so there's something to notify about
    ScrapingCandidate.objects.create(
        id=f"cand-notify-{uuid.uuid4().hex[:8]}",
        job=queued_job,
        village=scraper_village,
        region="Aquitaine / Landes",
        source="google_places",
        source_url="https://example.com",
        source_id="notify-src-001",
        nom="Surf School",
        type_emoji="🏄",
        distance_km=5.0,
        status="new",
    )
 
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = task_notify_scraping.apply(
            kwargs={"job_ids": [queued_job.id], "trigger": "monthly_cron"}
        )
 
    assert result.successful()
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args.args[0] == "https://discord.com/api/webhooks/test"
    payload = call_args.kwargs.get("json")
    assert "embeds" in payload
    embed = payload["embeds"][0]
    field_values = {f["name"]: f["value"] for f in embed["fields"]}
    assert "Environment" in field_values
    assert field_values["New Candidates"] == "1"
 
 
@pytest.mark.django_db
def test_task_notify_scraping_no_new_candidates_skips_discord(
    queued_job, monkeypatch
):
    """If there are no 'new' candidates, Discord POST should be skipped."""
    monkeypatch.setenv(
        "DISCORD_WEBHOOK", "https://discord.com/api/webhooks/test"
    )
    with patch("requests.post") as mock_post:
        task_notify_scraping.apply(
            kwargs={"job_ids": [queued_job.id], "trigger": "manual"}
        )
    mock_post.assert_not_called()
 
 
@pytest.mark.django_db
def test_task_notify_scraping_discord_failure_does_not_raise(
    queued_job, scraper_village, monkeypatch
):
    """Discord HTTP error must not propagate; task completes successfully."""
    monkeypatch.setenv(
        "DISCORD_WEBHOOK", "https://discord.com/api/webhooks/test"
    )
    ScrapingCandidate.objects.create(
        id=f"cand-discord-err-{uuid.uuid4().hex[:8]}",
        job=queued_job,
        village=scraper_village,
        region="Aquitaine / Landes",
        source="google_places",
        source_url="https://example.com",
        source_id="discord-err-001",
        nom="Surf",
        type_emoji="🏄",
        distance_km=5.0,
        status="new",
    )
    with patch("requests.post", side_effect=Exception("Discord down")):
        result = task_notify_scraping.apply(
            kwargs={"job_ids": [queued_job.id], "trigger": "manual"}
        )
    assert result.successful()
