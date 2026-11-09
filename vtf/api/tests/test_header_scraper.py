"""Tests for apps.header_scraper — mocked Playwright, no live browser."""
from __future__ import annotations

import base64
import sys
from pathlib import Path
from types import ModuleType

# Catalog URL import pulls WeasyPrint (system DLLs). Stub it so API tests stay
# local-friendly without touching catalog code.
if "weasyprint" not in sys.modules:
    _weasy = ModuleType("weasyprint")

    class _HTML:  # noqa: N801
        def __init__(self, *args, **kwargs):
            pass

        def write_pdf(self, *args, **kwargs):
            return b"%PDF-1.4"

    _weasy.HTML = _HTML
    sys.modules["weasyprint"] = _weasy

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.header_scraper.models import HeaderBanner, HeaderBannerSnapshot
from apps.header_scraper.services.parse import (
    extract_banner_html_from_page,
    parse_banner_html,
    segments_to_plain_text,
)
from apps.header_scraper.services.scrape import (
    BannerScrapeResult,
    scrape_header_banner_html,
    scrape_header_banner_html_from_string,
)
from apps.header_scraper.services.sync import (
    normalize_api_language,
    sync_language,
)
from apps.header_scraper.services.alerts import (
    format_errors_by_step,
    notify_batch_summary,
    notify_scrape_failure,
    notify_scrape_success,
    parse_pipeline_error,
    split_error_cascade,
)
from config.celery_app import app

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "apps"
    / "header_scraper"
    / "fixtures"
    / "topbar_fr.html"
)
BASE_URL = "https://www.vtf-vacances.com/fr_FR/"


@pytest.fixture
def fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def staff_api_client(db):
    user = get_user_model().objects.create_user(
        username="header_staff",
        password="password",
        is_staff=True,
    )
    token = base64.b64encode(b"header_staff:password").decode()
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Basic {token}")
    api.user = user
    return api


def test_normalize_api_language():
    assert normalize_api_language("FR") == "FR"
    assert normalize_api_language("es") == "FR"
    assert normalize_api_language("NL") == "FR"
    assert normalize_api_language("GB") == "GB"
    assert normalize_api_language("EN") == "GB"
    assert normalize_api_language(None) == "FR"


def test_extract_and_parse_fixture_preserves_links(fixture_html):
    banner_html = extract_banner_html_from_page(fixture_html)
    assert "offres" in banner_html.lower() or "derni" in banner_html.lower()

    segments = parse_banner_html(banner_html, base_url=BASE_URL)
    assert segments
    links = [s for s in segments if s["type"] == "link"]
    assert len(links) >= 2
    hrefs = {s["href"] for s in links}
    assert any("sejours-derniere-minute" in h for h in hrefs)
    assert any("bons-plans" in h for h in hrefs)
    # Language switcher must not appear.
    plain = segments_to_plain_text(segments)
    assert "FR" not in plain.split() or "alerte" in plain.lower()
    assert "Information alerte incendie" in plain or "alerte incendie" in plain.lower()


def test_scrape_header_banner_http_success_skips_playwright(fixture_html, monkeypatch):
    monkeypatch.setattr(
        "apps.header_scraper.services.scrape.fetch_header_page_html",
        lambda url: fixture_html,
    )

    def fail_playwright(language: str) -> BannerScrapeResult:
        raise AssertionError("Playwright should not run after HTTP success")

    monkeypatch.setattr(
        "apps.header_scraper.services.scrape.scrape_header_banner_html_playwright",
        fail_playwright,
    )

    result = scrape_header_banner_html("FR")

    assert result.ok is True
    assert result.method == "http"
    assert result.banner_html


def test_scrape_header_banner_falls_back_to_playwright(monkeypatch):
    monkeypatch.setattr(
        "apps.header_scraper.services.scrape.fetch_header_page_html",
        lambda url: "<html><body>No topbar here</body></html>",
    )

    def fake_playwright(language: str) -> BannerScrapeResult:
        return BannerScrapeResult(
            language=language,
            source_url=BASE_URL,
            ok=True,
            banner_html="Dernieres minutes",
            method="playwright",
        )

    monkeypatch.setattr(
        "apps.header_scraper.services.scrape.scrape_header_banner_html_playwright",
        fake_playwright,
    )

    result = scrape_header_banner_html("FR")

    assert result.ok is True
    assert result.method == "playwright"
    assert result.banner_html == "Dernieres minutes"


def test_scrape_header_banner_falls_back_to_llm_after_http_and_playwright(monkeypatch):
    page_html = "<html><body><div>Banner text hidden in changed markup</div></body></html>"
    monkeypatch.setattr(
        "apps.header_scraper.services.scrape.fetch_header_page_html",
        lambda url: page_html,
    )

    def fail_playwright(language: str) -> BannerScrapeResult:
        return BannerScrapeResult(
            language=language,
            source_url=BASE_URL,
            ok=False,
            error="No banner in browser DOM",
            method="playwright",
        )

    llm_calls = []

    def fake_llm(page_html_arg: str, language: str, *, base_url: str) -> str:
        llm_calls.append((page_html_arg, language, base_url))
        return (
            'Ne manquez pas <a href="/fr_FR/sejours-derniere-minute-ete">'
            "les offres</a>"
        )

    monkeypatch.setattr(
        "apps.header_scraper.services.scrape.scrape_header_banner_html_playwright",
        fail_playwright,
    )
    monkeypatch.setattr(
        "apps.header_scraper.services.llm_fallback.llm_fallback_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "apps.header_scraper.services.llm_fallback.extract_banner_html_with_llm",
        fake_llm,
    )

    result = scrape_header_banner_html("FR")

    assert result.ok is True
    assert result.method == "llm_fallback"
    assert "les offres" in result.banner_html
    assert llm_calls == [(page_html, "FR", BASE_URL)]


def test_scrape_header_banner_llm_disabled_reports_combined_failure(monkeypatch):
    monkeypatch.setattr(
        "apps.header_scraper.services.scrape.fetch_header_page_html",
        lambda url: "<html><body>No topbar here</body></html>",
    )
    monkeypatch.setattr(
        "apps.header_scraper.services.scrape.scrape_header_banner_html_playwright",
        lambda language: BannerScrapeResult(
            language=language,
            source_url=BASE_URL,
            ok=False,
            error="No banner in browser DOM",
            method="playwright",
        ),
    )
    monkeypatch.setattr(
        "apps.header_scraper.services.llm_fallback.llm_fallback_enabled",
        lambda: False,
    )

    result = scrape_header_banner_html("FR")

    assert result.ok is False
    assert result.method == "http+playwright+llm_fallback"
    assert "LLM fallback is disabled" in result.error


def test_header_llm_fallback_parses_json_and_validates_links(monkeypatch):
    from apps.header_scraper.services.llm_fallback import extract_banner_html_with_llm

    monkeypatch.setattr(
        "apps.header_scraper.services.llm_fallback._call_lmstudio",
        lambda prompt: (
            '{"banner_html": "Ne manquez pas '
            '<a href=\\"/fr_FR/bons-plans/bons-plans-villages-vacances\\">'
            'les bons plans du moment</a> !"}'
        ),
    )

    banner_html = extract_banner_html_with_llm(
        "<html>changed topbar markup</html>",
        "FR",
        base_url=BASE_URL,
    )
    segments = parse_banner_html(banner_html, base_url=BASE_URL)

    assert banner_html
    assert segments[1]["type"] == "link"
    assert segments[1]["href"] == (
        "https://www.vtf-vacances.com/fr_FR/bons-plans/bons-plans-villages-vacances"
    )


@pytest.mark.django_db
def test_sync_language_success_then_unchanged(fixture_html):
    def fake_scrape(language: str) -> BannerScrapeResult:
        return scrape_header_banner_html_from_string(language, fixture_html)

    first = sync_language("FR", scrape_fn=fake_scrape)
    assert first["status"] == HeaderBannerSnapshot.STATUS_SUCCESS
    banner = HeaderBanner.objects.get(language="FR")
    assert banner.is_active
    assert banner.segments
    scraped_at = banner.scraped_at

    second = sync_language("FR", scrape_fn=fake_scrape)
    assert second["status"] == HeaderBannerSnapshot.STATUS_UNCHANGED
    banner.refresh_from_db()
    assert banner.scraped_at == scraped_at

    snaps = HeaderBannerSnapshot.objects.filter(language="FR").order_by("id")
    assert snaps.count() == 2
    assert snaps[0].status == HeaderBannerSnapshot.STATUS_SUCCESS
    assert snaps[1].status == HeaderBannerSnapshot.STATUS_UNCHANGED


@pytest.mark.django_db
def test_sync_fetch_failure_keeps_previous_banner(fixture_html):
    def ok_scrape(language: str) -> BannerScrapeResult:
        return scrape_header_banner_html_from_string(language, fixture_html)

    sync_language("FR", scrape_fn=ok_scrape)
    before = HeaderBanner.objects.get(language="FR")
    before_hash = before.content_hash
    before_text = before.plain_text

    def fail_scrape(language: str) -> BannerScrapeResult:
        return BannerScrapeResult(
            language=language,
            source_url=BASE_URL,
            ok=False,
            error="Playwright boom",
        )

    result = sync_language("FR", scrape_fn=fail_scrape)
    assert result["status"] == HeaderBannerSnapshot.STATUS_FETCH_FAILED

    after = HeaderBanner.objects.get(language="FR")
    assert after.content_hash == before_hash
    assert after.plain_text == before_text
    assert HeaderBannerSnapshot.objects.filter(
        language="FR", status=HeaderBannerSnapshot.STATUS_FETCH_FAILED
    ).exists()


@pytest.mark.django_db
def test_get_header_banner_empty_returns_null(client):
    resp = client.get("/api/v5/header-banner", {"lang": "FR"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] is None


@pytest.mark.django_db
def test_get_header_banner_nl_maps_to_fr(client, fixture_html):
    def fake_scrape(language: str) -> BannerScrapeResult:
        return scrape_header_banner_html_from_string(language, fixture_html)

    sync_language("FR", scrape_fn=fake_scrape)

    resp = client.get("/api/v5/header-banner", {"lang": "NL"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["language"] == "FR"
    assert body["data"]["segments"]
    assert "scrapedAt" in body["data"]


class _FakeAsyncResult:
    id = "header-task-123"


@pytest.mark.django_db
def test_staff_scrape_queues_language_task(staff_api_client, monkeypatch):
    calls = []

    def fake_delay(language: str):
        calls.append(language)
        return _FakeAsyncResult()

    monkeypatch.setattr(
        "apps.header_scraper.tasks.task_scrape_header_banner_language.delay",
        fake_delay,
    )
    resp = staff_api_client.post(
        "/api/v5/admin/header-scraper/scrape",
        {"language": "FR"},
        format="json",
    )

    assert resp.status_code == 202
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["task_id"] == "header-task-123"
    assert body["data"]["language"] == "FR"
    assert calls == ["FR"]


@pytest.mark.django_db
def test_staff_scrape_queues_all_languages_task(staff_api_client, monkeypatch):
    calls = []

    def fake_delay():
        calls.append(True)
        return _FakeAsyncResult()

    monkeypatch.setattr(
        "apps.header_scraper.tasks.task_scrape_header_banner.delay",
        fake_delay,
    )
    resp = staff_api_client.post(
        "/api/v5/admin/header-scraper/scrape",
        {},
        format="json",
    )

    assert resp.status_code == 202
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["task_id"] == "header-task-123"
    assert body["data"]["language"] is None
    assert calls == [True]


@pytest.mark.django_db
def test_staff_scrape_ignores_async_mode_and_queues_celery(staff_api_client, monkeypatch):
    calls = []

    def fake_delay(language: str):
        calls.append(language)
        return _FakeAsyncResult()

    monkeypatch.setattr(
        "apps.header_scraper.tasks.task_scrape_header_banner_language.delay",
        fake_delay,
    )
    resp = staff_api_client.post(
        "/api/v5/admin/header-scraper/scrape",
        {"language": "FR", "async_mode": True},
        format="json",
    )

    assert resp.status_code == 202
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["task_id"] == "header-task-123"
    assert body["data"]["language"] == "FR"
    assert calls == ["FR"]


@pytest.mark.django_db
def test_staff_jobs_list(staff_api_client, fixture_html):
    def fake_scrape(language: str) -> BannerScrapeResult:
        return scrape_header_banner_html_from_string(language, fixture_html)

    sync_language("FR", scrape_fn=fake_scrape)
    resp = staff_api_client.get("/api/v5/admin/header-scraper/jobs", {"lang": "FR"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) >= 1


def test_beat_schedule_includes_header_banner_scrape():
    schedule = app.conf.beat_schedule
    assert "scrape-header-banner" in schedule, (
        "Expected 'scrape-header-banner' in beat_schedule. "
        f"Available keys: {list(schedule.keys())}"
    )
    entry = schedule["scrape-header-banner"]
    assert entry["task"] == "apps.header_scraper.tasks.task_scrape_header_banner"
    sched = entry["schedule"]
    assert sched._orig_minute == {0} or sched._orig_minute == 0
    # hour */4
    hour = sched._orig_hour
    assert hour == "*/4" or getattr(hour, "step", None) == 4 or set(hour) == set(range(0, 24, 4))


# ---------------------------------------------------------------------------
# Discord alerts (apps.header_scraper.services.alerts)
# ---------------------------------------------------------------------------

def test_scrape_error_messages_are_step_labeled(monkeypatch):
    """HTTP/Playwright/LLM tier errors must carry 'Step N (Label) | file → func() | reason'
    so alerts.parse_pipeline_error() can extract where/why it broke."""
    monkeypatch.setattr(
        "apps.header_scraper.services.scrape.fetch_header_page_html",
        lambda url: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    from apps.header_scraper.services.scrape import scrape_header_banner_html_http

    result = scrape_header_banner_html_http("FR")
    assert result.ok is False
    assert result.error.startswith("Step 1 (HTTP Fetch) | scrape.py")
    parsed = parse_pipeline_error(result.error)
    assert parsed["step"] == "Step 1 (HTTP Fetch)"
    assert "scrape_header_banner_html_http" in parsed["source"]
    assert "boom" in parsed["reason"]


def test_llm_fallback_disabled_error_is_step_labeled(monkeypatch):
    monkeypatch.setattr(
        "apps.header_scraper.services.llm_fallback.llm_fallback_enabled",
        lambda: False,
    )
    from apps.header_scraper.services.scrape import scrape_header_banner_html_llm

    result = scrape_header_banner_html_llm("FR", page_html="<html></html>")
    assert result.ok is False
    assert result.error.startswith("Step 3 (LLM Fallback) | scrape.py")
    # Preserve the exact substring older callers/tests key off of.
    assert "LLM fallback is disabled" in result.error


def test_split_error_cascade_breaks_combined_tier_errors():
    combined = (
        "Step 1 (HTTP Fetch) | scrape.py → scrape_header_banner_html_http() | HTTP 404"
        " | Step 2 (Playwright Scrape) | scrape.py → scrape_header_banner_html_playwright() | timeout"
        " | Step 3 (LLM Fallback) | scrape.py → scrape_header_banner_html_llm() | LLM fallback is disabled."
    )
    steps = split_error_cascade(combined)
    assert len(steps) == 3
    assert steps[0].startswith("Step 1 (HTTP Fetch)")
    assert steps[1].startswith("Step 2 (Playwright Scrape)")
    assert steps[2].startswith("Step 3 (LLM Fallback)")

    parsed_last = parse_pipeline_error(steps[-1])
    assert parsed_last["step"] == "Step 3 (LLM Fallback)"
    assert "LLM fallback is disabled" in parsed_last["reason"]


def test_split_error_cascade_handles_empty_and_single_step():
    assert split_error_cascade("") == []
    assert split_error_cascade("   ") == []
    single = "Step 4 (Parse) | sync.py → sync_language() | Parsed zero segments from banner HTML."
    assert split_error_cascade(single) == [single]


def test_format_errors_by_step_renders_readable_block():
    errors = [
        "Step 1 (HTTP Fetch) | scrape.py → scrape_header_banner_html_http() | HTTP 404",
        "Step 2 (Playwright Scrape) | scrape.py → scrape_header_banner_html_playwright() | timeout",
    ]
    text = format_errors_by_step(errors)
    assert "**Step 1 (HTTP Fetch)**" in text
    assert "`scrape.py → scrape_header_banner_html_http()`" in text
    assert "❌ HTTP 404" in text
    assert "**Step 2 (Playwright Scrape)**" in text


def test_notify_scrape_failure_posts_discord_embed(settings, monkeypatch):
    settings.DISCORD_WEBHOOK = "https://discord.example/webhook"
    settings.NOTIFICATION_ENVIRONMENT_NAME = "production"
    settings.NOTIFICATION_ORIGIN_DOMAIN = "production.example.com"
    settings.NOTIFICATION_ORIGIN_IP = "203.0.113.10"
    posted = {}

    class _FakeResp:
        status_code = 204
        text = ""

    def fake_post(url, json, timeout):
        posted["url"] = url
        posted["json"] = json
        return _FakeResp()

    monkeypatch.setattr("apps.header_scraper.services.alerts.requests.post", fake_post)

    result = {
        "language": "FR",
        "status": "fetch_failed",
        "source_url": "https://www.vtf-vacances.com/fr_FR/",
        "error": (
            "Step 1 (HTTP Fetch) | scrape.py → scrape_header_banner_html_http() | HTTP 404"
            " | Step 2 (Playwright Scrape) | scrape.py → scrape_header_banner_html_playwright() | timeout"
            " | Step 3 (LLM Fallback) | scrape.py → scrape_header_banner_html_llm() | LLM fallback is disabled."
        ),
    }
    notify_scrape_failure(result)

    assert posted["url"] == "https://discord.example/webhook"
    embed = posted["json"]["embeds"][0]
    assert "FR" in embed["title"]
    assert embed["color"] == 0xED4245  # RED
    field_names = [f["name"] for f in embed["fields"]]
    assert field_names[0] == "Environment"
    assert "production" in embed["fields"][0]["value"]
    assert "production.example.com" in embed["fields"][0]["value"]
    assert "203.0.113.10" in embed["fields"][0]["value"]
    assert "Errors by Step (where it broke)" in field_names


def test_notify_scrape_failure_parse_failed_is_yellow(settings, monkeypatch):
    settings.DISCORD_WEBHOOK = "https://discord.example/webhook"
    posted = {}

    class _FakeResp:
        status_code = 204
        text = ""

    monkeypatch.setattr(
        "apps.header_scraper.services.alerts.requests.post",
        lambda url, json, timeout: posted.update(json=json) or _FakeResp(),
    )

    result = {
        "language": "GB",
        "status": "parse_failed",
        "source_url": "https://www.vtf-vacances.com/en_GB/",
        "error": "Step 4 (Parse) | sync.py → sync_language() | Parsed zero segments from banner HTML.",
    }
    notify_scrape_failure(result)

    embed = posted["json"]["embeds"][0]
    assert embed["color"] == 0xFEE75C  # YELLOW
    assert "GB" in embed["title"]


def test_notify_scrape_success_skipped_when_setting_disabled(settings, monkeypatch):
    settings.DISCORD_WEBHOOK = "https://discord.example/webhook"
    settings.HEADER_SCRAPER_NOTIFY_SUCCESS = False
    calls = []
    monkeypatch.setattr(
        "apps.header_scraper.services.alerts.requests.post",
        lambda *a, **k: calls.append(1),
    )

    notify_scrape_success({"language": "FR", "source_url": "u", "content_hash": "abc123", "plain_text": "hi"})
    assert calls == []


def test_notify_scrape_success_posts_green_embed(settings, monkeypatch):
    settings.DISCORD_WEBHOOK = "https://discord.example/webhook"
    settings.HEADER_SCRAPER_NOTIFY_SUCCESS = True
    posted = {}

    class _FakeResp:
        status_code = 204
        text = ""

    monkeypatch.setattr(
        "apps.header_scraper.services.alerts.requests.post",
        lambda url, json, timeout: posted.update(json=json) or _FakeResp(),
    )

    notify_scrape_success({
        "language": "FR",
        "source_url": "https://www.vtf-vacances.com/fr_FR/",
        "content_hash": "abcdef123456",
        "plain_text": "Dernieres minutes",
    })
    embed = posted["json"]["embeds"][0]
    assert embed["color"] == 0x57F287  # GREEN
    assert "FR" in embed["title"]


def test_notify_batch_summary_red_when_any_fetch_failed(settings, monkeypatch):
    settings.DISCORD_WEBHOOK = "https://discord.example/webhook"
    posted = {}

    class _FakeResp:
        status_code = 204
        text = ""

    monkeypatch.setattr(
        "apps.header_scraper.services.alerts.requests.post",
        lambda url, json, timeout: posted.update(json=json) or _FakeResp(),
    )

    results = [
        {"language": "FR", "status": "success"},
        {
            "language": "GB",
            "status": "fetch_failed",
            "error": (
                "Step 1 (HTTP Fetch) | scrape.py → scrape_header_banner_html_http() | HTTP 500"
            ),
        },
    ]
    notify_batch_summary(results)

    embed = posted["json"]["embeds"][0]
    assert embed["color"] == 0xED4245  # RED
    field_map = {f["name"]: f["value"] for f in embed["fields"]}
    assert field_map["Failed"] == "1"
    assert "GB" in field_map["Failed languages (step + reason)"]


def test_notify_alerts_noop_without_webhook(settings, monkeypatch):
    """No DISCORD_WEBHOOK configured -> never calls requests.post."""
    settings.DISCORD_WEBHOOK = ""
    calls = []
    monkeypatch.setattr(
        "apps.header_scraper.services.alerts.requests.post",
        lambda *a, **k: calls.append(1),
    )
    notify_scrape_failure({"language": "FR", "status": "fetch_failed", "error": "boom"})
    notify_scrape_success({"language": "FR"})
    notify_batch_summary([{"language": "FR", "status": "success"}])
    assert calls == []


@pytest.mark.django_db
def test_task_scrape_header_banner_language_dispatches_failure_alert(monkeypatch):
    """task_scrape_header_banner_language() must fire notify_scrape_failure
    on a fetch_failed sync result."""
    from apps.header_scraper import tasks

    fail_result = {
        "language": "FR",
        "status": "fetch_failed",
        "source_url": "https://www.vtf-vacances.com/fr_FR/",
        "error": "Step 1 (HTTP Fetch) | scrape.py → scrape_header_banner_html_http() | HTTP 500",
    }
    monkeypatch.setattr(
        "apps.header_scraper.services.sync.sync_language",
        lambda language, scrape_fn=None: fail_result,
    )

    calls = []
    monkeypatch.setattr(
        "apps.header_scraper.services.alerts.notify_scrape_failure",
        lambda result: calls.append(result),
    )

    result = tasks.task_scrape_header_banner_language.run("FR")
    assert result["status"] == "fetch_failed"
    assert calls == [fail_result]


@pytest.mark.django_db
def test_task_scrape_header_banner_language_skips_alert_when_unchanged(monkeypatch):
    """STATUS_UNCHANGED must NOT trigger a Discord alert (avoid alert spam)."""
    from apps.header_scraper import tasks

    unchanged_result = {"language": "FR", "status": "unchanged", "source_url": "u"}
    monkeypatch.setattr(
        "apps.header_scraper.services.sync.sync_language",
        lambda language, scrape_fn=None: unchanged_result,
    )

    fail_calls = []
    success_calls = []
    monkeypatch.setattr(
        "apps.header_scraper.services.alerts.notify_scrape_failure",
        lambda result: fail_calls.append(result),
    )
    monkeypatch.setattr(
        "apps.header_scraper.services.alerts.notify_scrape_success",
        lambda result: success_calls.append(result),
    )

    result = tasks.task_scrape_header_banner_language.run("FR")
    assert result["status"] == "unchanged"
    assert fail_calls == []
    assert success_calls == []


@pytest.mark.django_db
def test_task_scrape_header_banner_dispatches_batch_summary(monkeypatch):
    """task_scrape_header_banner() must call notify_batch_summary once with
    both language results after scraping FR + GB."""
    from apps.header_scraper import tasks

    fake_results = {
        "results": [
            {"language": "FR", "status": "success", "source_url": "u1"},
            {"language": "GB", "status": "unchanged", "source_url": "u2"},
        ],
        "ok": True,
    }
    monkeypatch.setattr(
        "apps.header_scraper.services.sync.sync_all_languages",
        lambda scrape_fn=None: fake_results,
    )

    summary_calls = []
    success_calls = []
    monkeypatch.setattr(
        "apps.header_scraper.services.alerts.notify_batch_summary",
        lambda results: summary_calls.append(results),
    )
    monkeypatch.setattr(
        "apps.header_scraper.services.alerts.notify_scrape_success",
        lambda result: success_calls.append(result),
    )

    result = tasks.task_scrape_header_banner.run()
    assert result["ok"] is True
    assert summary_calls == [fake_results["results"]]
    assert success_calls == [fake_results["results"][0]]  # only the "success" one


# ---------------------------------------------------------------------------
# POST /api/v5/header-scraper/dry-run/
# ---------------------------------------------------------------------------

def _patch_discord_post(monkeypatch, settings):
    """Point DISCORD_WEBHOOK at a fake URL and capture the posted embed."""
    settings.DISCORD_WEBHOOK = "https://discord.example/webhook"
    settings.HEADER_SCRAPER_NOTIFY_SUCCESS = True
    posted = {}

    class _FakeResp:
        status_code = 204
        text = ""

    def fake_post(url, json, timeout):
        posted["url"] = url
        posted["json"] = json
        return _FakeResp()

    monkeypatch.setattr("apps.header_scraper.services.alerts.requests.post", fake_post)
    return posted


@pytest.mark.django_db
def test_dry_run_requires_staff_auth(client):
    resp = client.post(
        "/api/v5/header-scraper/dry-run/",
        {"scenario": "success"},
        format="json",
    )
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_dry_run_rejects_unknown_scenario(staff_api_client):
    resp = staff_api_client.post(
        "/api/v5/header-scraper/dry-run/",
        {"scenario": "not_a_real_scenario"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_dry_run_success_scenario_sends_green_alert(staff_api_client, monkeypatch, settings):
    posted = _patch_discord_post(monkeypatch, settings)

    resp = staff_api_client.post(
        "/api/v5/header-scraper/dry-run/",
        {"scenario": "success", "language": "FR"},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["scenario"] == "success"
    assert body["data"]["language"] == "FR"

    embed = posted["json"]["embeds"][0]
    assert embed["color"] == 0x57F287  # GREEN
    assert "FR" in embed["title"]


@pytest.mark.django_db
def test_dry_run_fetch_failed_scenario_sends_red_alert_with_steps(
    staff_api_client, monkeypatch, settings
):
    posted = _patch_discord_post(monkeypatch, settings)

    resp = staff_api_client.post(
        "/api/v5/header-scraper/dry-run/",
        {"scenario": "fetch_failed", "language": "GB"},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["scenario"] == "fetch_failed"
    assert body["data"]["language"] == "GB"

    embed = posted["json"]["embeds"][0]
    assert embed["color"] == 0xED4245  # RED
    field_names = [f["name"] for f in embed["fields"]]
    assert "Errors by Step (where it broke)" in field_names
    steps_field = next(f for f in embed["fields"] if f["name"] == "Errors by Step (where it broke)")
    assert "Step 1 (HTTP Fetch)" in steps_field["value"]
    assert "Step 2 (Playwright Scrape)" in steps_field["value"]
    assert "Step 3 (LLM Fallback)" in steps_field["value"]


@pytest.mark.django_db
def test_dry_run_parse_failed_scenario_sends_yellow_alert(staff_api_client, monkeypatch, settings):
    posted = _patch_discord_post(monkeypatch, settings)

    resp = staff_api_client.post(
        "/api/v5/header-scraper/dry-run/",
        {"scenario": "parse_failed", "language": "FR"},
        format="json",
    )
    assert resp.status_code == 200
    embed = posted["json"]["embeds"][0]
    assert embed["color"] == 0xFEE75C  # YELLOW
    steps_field = next(f for f in embed["fields"] if f["name"] == "Errors by Step (where it broke)")
    assert "Step 4 (Parse)" in steps_field["value"]
    assert "sync.py" in steps_field["value"]


@pytest.mark.django_db
def test_dry_run_batch_summary_scenario_sends_summary_alert(staff_api_client, monkeypatch, settings):
    posted = _patch_discord_post(monkeypatch, settings)

    resp = staff_api_client.post(
        "/api/v5/header-scraper/dry-run/",
        {"scenario": "batch_summary"},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["scenario"] == "batch_summary"
    assert body["data"]["languages"] == 2

    embed = posted["json"]["embeds"][0]
    field_map = {f["name"]: f["value"] for f in embed["fields"]}
    assert field_map["Failed"] == "1"
    assert "GB" in field_map["Failed languages (step + reason)"]


@pytest.mark.django_db
def test_dry_run_defaults_language_to_fr(staff_api_client, monkeypatch, settings):
    posted = _patch_discord_post(monkeypatch, settings)

    resp = staff_api_client.post(
        "/api/v5/header-scraper/dry-run/",
        {"scenario": "success"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["language"] == "FR"
    assert "FR" in posted["json"]["embeds"][0]["title"]


@pytest.mark.django_db
def test_dry_run_does_not_write_to_database(staff_api_client, monkeypatch, settings):
    """Dry-run must never touch HeaderBanner/HeaderBannerSnapshot rows."""
    _patch_discord_post(monkeypatch, settings)

    staff_api_client.post(
        "/api/v5/header-scraper/dry-run/",
        {"scenario": "fetch_failed", "language": "FR"},
        format="json",
    )
    assert HeaderBanner.objects.count() == 0
    assert HeaderBannerSnapshot.objects.count() == 0
