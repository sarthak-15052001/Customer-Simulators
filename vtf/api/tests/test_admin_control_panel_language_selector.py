"""Verifies the Django admin 'Lancer une traduction' panel's language
selector (Toutes les langues / French (FR) / English (GB)) queues the
right sources for both 'mode' options, matching what's shown in the
translation_control.html template + admin_views.py.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.fixture(autouse=True)
def _locmem_cache(settings):
    """The control panel view reads/writes cache for active-job tracking.
    Use in-memory cache here so these tests don't need a live Redis —
    same fix pattern as elsewhere, scoped to this test file only."""
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }


@pytest.fixture(autouse=True)
def _no_celery_broker(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "apps.translation_manager.tasks.task_translate_source.delay",
        lambda *a, **k: calls.append(a),
    )
    return calls


@pytest.fixture
def admin_client(db):
    User = get_user_model()
    User.objects.create_superuser(username="admin", email="a@a.com", password="pw")
    c = Client()
    c.login(username="admin", password="pw")
    return c


@pytest.mark.django_db
def test_all_mode_with_fr_target_excludes_all_catalog_sources(monkeypatch, admin_client):
    """Every synced catalog TranslationSource has source_language=FR, so
    'Retraduire toutes les sources actives' + target=French (FR) excludes
    every one of them via `.exclude(source_language=language)` -> 0 queued.
    The view now surfaces an explanatory info message for this case instead
    of a bare '0 queued' success message."""
    from apps.translation_manager.models import TranslationSource

    TranslationSource.objects.create(
        key="k1", source_language="FR", source_text="Bonjour", source_model_ref="x"
    )

    calls = []
    monkeypatch.setattr(
        "apps.translation_manager.tasks.task_translate_source.delay",
        lambda *a, **k: calls.append(a),
    )
    resp = admin_client.post(
        "/admin/translation_manager/translationsource/control/start/",
        {"mode": "all", "language": "FR"},
        follow=True,
    )
    assert resp.status_code == 200
    assert calls == [], "expected zero queued tasks when target=FR excludes all FR sources"

    messages = [str(m) for m in resp.context["messages"]]
    assert any("Rien à retraduire vers FR" in m for m in messages), messages


@pytest.mark.django_db
def test_all_mode_with_gb_target_queues_all_active_sources(monkeypatch, admin_client):
    from apps.translation_manager.models import TranslationSource

    s1 = TranslationSource.objects.create(
        key="k1", source_language="FR", source_text="Bonjour", source_model_ref="x"
    )
    s2 = TranslationSource.objects.create(
        key="k2", source_language="FR", source_text="Salut", source_model_ref="x"
    )

    calls = []
    monkeypatch.setattr(
        "apps.translation_manager.tasks.task_translate_source.delay",
        lambda *a, **k: calls.append(a),
    )
    admin_client.post(
        "/admin/translation_manager/translationsource/control/start/",
        {"mode": "all", "language": "GB"},
    )
    queued_ids = {c[0] for c in calls}
    assert queued_ids == {s1.pk, s2.pk}
    assert all(c[1] == ["GB"] for c in calls)


@pytest.mark.django_db
def test_all_mode_with_toutes_les_langues_queues_all_with_no_language_filter(monkeypatch, admin_client):
    from apps.translation_manager.models import TranslationSource

    s1 = TranslationSource.objects.create(
        key="k1", source_language="FR", source_text="Bonjour", source_model_ref="x"
    )

    calls = []
    monkeypatch.setattr(
        "apps.translation_manager.tasks.task_translate_source.delay",
        lambda *a, **k: calls.append(a),
    )
    admin_client.post(
        "/admin/translation_manager/translationsource/control/start/",
        {"mode": "all", "language": ""},
    )
    assert len(calls) == 1
    assert calls[0][0] == s1.pk
    assert calls[0][1] is None  # None -> task_translate_source defaults to both FR+GB


@pytest.mark.django_db
def test_all_mode_with_gb_target_and_no_active_sources_shows_normal_success(monkeypatch, admin_client):
    """0 queued for a reason OTHER than the FR same-language exclusion (here:
    there simply are no active sources) must still show the normal success
    message, not the FR-specific explanation."""
    calls = []
    monkeypatch.setattr(
        "apps.translation_manager.tasks.task_translate_source.delay",
        lambda *a, **k: calls.append(a),
    )
    resp = admin_client.post(
        "/admin/translation_manager/translationsource/control/start/",
        {"mode": "all", "language": "GB"},
        follow=True,
    )
    assert calls == []
    messages = [str(m) for m in resp.context["messages"]]
    assert any("Translation run queued" in m for m in messages)
    assert not any("Rien à retraduire" in m for m in messages)
