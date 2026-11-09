"""Tests for apps.translation_manager: the admin-managed catalog translation
table, its field registry, and its public /api/v6/translations endpoint.

Deliberately does NOT touch apps.catalog.services.translations or the v1
?language= query-param translator — that's a separate system left as-is.

Run with:
    pytest tests/test_translation_manager.py -v
"""
from __future__ import annotations

import pytest
from django.test import RequestFactory


@pytest.fixture(autouse=True)
def _no_celery_broker(monkeypatch):
    """Stub the Celery .delay() call the post_save signal fires so these
    tests don't spend ~20s retrying a Redis broker that isn't running in
    this environment. The signal's own try/except already handles a real
    broker outage gracefully in production — this just keeps tests fast."""
    monkeypatch.setattr(
        "apps.translation_manager.tasks.task_translate_source.delay",
        lambda *args, **kwargs: None,
    )


# ---------------------------------------------------------------------------
# Registry coverage — every catalog model with real text is represented
# ---------------------------------------------------------------------------


def test_registry_covers_every_catalog_model_with_text_fields():
    from apps.translation_manager.services.registry import REGISTRY

    registered_models = {spec.model_name for spec in REGISTRY}
    expected = {
        "Village",
        "LandingMapZone",
        "Formula",
        "Attraction",
        "Activity",
        "Animation",
        "VillageInfra",
        "Meal",
        "FuelOption",
        "Promo",
        "MarketingSeasons",
        "MarketingSeasonEnvironment",
    }
    assert expected.issubset(registered_models)


def test_registry_has_no_duplicate_field_specs():
    from apps.translation_manager.services.registry import REGISTRY

    seen = [(spec.app_label, spec.model_name, spec.field) for spec in REGISTRY]
    assert len(seen) == len(set(seen))


def test_registry_only_registers_char_or_text_fields():
    """Every FieldSpec in REGISTRY must point at an actual CharField/TextField
    on its model — catches an accidental numeric/date/JSON/FK registration
    before it ever reaches sync_field()."""
    from django.apps import apps as django_apps
    from django.db import models as dj_models

    from apps.translation_manager.services.registry import REGISTRY

    for spec in REGISTRY:
        model = django_apps.get_model(spec.app_label, spec.model_name)
        field = model._meta.get_field(spec.field)
        assert isinstance(field, (dj_models.CharField, dj_models.TextField)), (
            f"{spec.app_label}.{spec.model_name}.{spec.field} is a "
            f"{type(field).__name__}, not translatable text"
        )


# ---------------------------------------------------------------------------
# sync_field — non-text fields skipped gracefully, text fields synced
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_sync_field_skips_non_text_field_gracefully():
    """A FieldSpec pointing at a numeric field (Attraction.km) must never be
    stringified and sent to the LLM — sync_field skips it cleanly."""
    from apps.translation_manager.services.registry import FieldSpec, sync_field

    spec = FieldSpec("catalog", "Attraction", "km")
    result = sync_field(spec)
    assert result["created"] == 0
    assert result["updated"] == 0
    assert result.get("field_skipped") is True


@pytest.mark.django_db
def test_sync_field_skips_boolean_field_gracefully():
    from apps.translation_manager.services.registry import FieldSpec, sync_field

    spec = FieldSpec("catalog", "Village", "has_loc")
    result = sync_field(spec)
    assert result.get("field_skipped") is True


@pytest.mark.django_db
def test_sync_field_skips_json_field_gracefully():
    from apps.translation_manager.services.registry import FieldSpec, sync_field

    spec = FieldSpec("catalog", "Village", "tarifs")
    result = sync_field(spec)
    assert result.get("field_skipped") is True


@pytest.mark.django_db
def test_sync_field_skips_date_field_gracefully():
    from apps.translation_manager.services.registry import FieldSpec, sync_field

    spec = FieldSpec("catalog", "MarketingSeasons", "start_date")
    result = sync_field(spec)
    assert result.get("field_skipped") is True


@pytest.mark.django_db
def test_sync_field_translates_actual_text_field():
    from apps.catalog.models import Formula
    from apps.translation_manager.models import TranslationSource
    from apps.translation_manager.services.registry import FieldSpec, sync_field

    Formula.objects.create(
        code="PC",
        icon="🍽",
        icon_key="pc",
        label="Pension complète",
        short_description="Tout compris",
        sort_order=0,
    )
    spec = FieldSpec("catalog", "Formula", "label")
    result = sync_field(spec)
    assert result["created"] == 1

    source = TranslationSource.objects.get(source_model_ref="catalog.Formula.label")
    assert source.source_text == "Pension complète"
    assert source.source_language == "FR"


@pytest.mark.django_db
def test_sync_field_is_idempotent_on_unchanged_value():
    from apps.catalog.models import Meal
    from apps.translation_manager.services.registry import FieldSpec, sync_field

    Meal.objects.create(code="DEJ", label="Déjeuner", price_adult=15, price_child=8, order=0)
    spec = FieldSpec("catalog", "Meal", "label")

    first = sync_field(spec)
    second = sync_field(spec)
    assert first["created"] == 1
    assert second["created"] == 0
    assert second["unchanged"] == 1


@pytest.mark.django_db
def test_sync_all_covers_all_registered_models_without_error():
    from apps.translation_manager.services.registry import sync_all

    summary = sync_all()
    assert summary["fields"] >= 12
    assert isinstance(summary["by_group"], dict)


# ---------------------------------------------------------------------------
# /api/v6/translations — public read endpoint for the translation table
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_translation_list_view_returns_translated_entries():
    from apps.translation_manager.models import TranslationEntry, TranslationSource
    from apps.translation_manager.views import TranslationListView

    source = TranslationSource.objects.create(
        key="catalog-formula-label-pc",
        source_language="FR",
        source_text="Pension complète",
        source_model_ref="catalog.Formula.label",
    )
    TranslationEntry.objects.create(
        source=source,
        language="GB",
        translated_text="Full board",
        status=TranslationEntry.STATUS_TRANSLATED,
        source_content_hash=source.content_hash,
    )
    # A pending (not-yet-translated) entry must NOT show up in the list.
    TranslationSource.objects.create(
        key="catalog-formula-label-dp",
        source_language="FR",
        source_text="Demi-pension",
        source_model_ref="catalog.Formula.label",
    )

    request = RequestFactory().get("/api/v6/translations?lang=GB")
    response = TranslationListView.as_view()(request)

    keys = [row["key"] for row in response.data["data"]]
    assert "catalog-formula-label-pc" in keys
    assert len(response.data["data"]) == 1
    assert response.data["data"][0]["translated_text"] == "Full board"


@pytest.mark.django_db
def test_translation_list_view_filters_by_key():
    from apps.translation_manager.models import TranslationEntry, TranslationSource
    from apps.translation_manager.views import TranslationListView

    source = TranslationSource.objects.create(
        key="catalog-village-nom-lacanau",
        source_language="FR",
        source_text="Lacanau",
        source_model_ref="catalog.Village.nom",
    )
    TranslationEntry.objects.create(
        source=source,
        language="GB",
        translated_text="Lacanau",
        status=TranslationEntry.STATUS_TRANSLATED,
        source_content_hash=source.content_hash,
    )

    request = RequestFactory().get(
        "/api/v6/translations?key=catalog-village-nom-lacanau"
    )
    response = TranslationListView.as_view()(request)
    assert len(response.data["data"]) == 1
    assert response.data["data"][0]["key"] == "catalog-village-nom-lacanau"


# ---------------------------------------------------------------------------
# task_translate_source — FR target is copied, GB target calls the LLM
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_task_translate_source_copies_same_language_without_llm(monkeypatch):
    from apps.translation_manager.models import TranslationSource
    from apps.translation_manager.tasks import task_translate_source

    def fail_llm(*_args, **_kwargs):
        raise AssertionError("same-language target must not call the LLM")

    monkeypatch.setattr(
        "apps.translation_manager.services.llm_client.translate_text", fail_llm
    )

    source = TranslationSource.objects.create(
        key="catalog-village-nom-agde",
        source_language="FR",
        source_text="Agde",
        source_model_ref="catalog.Village.nom",
    )

    result = task_translate_source(source.pk, ["FR"])
    assert result["ok"] is True
    entry = source.translations.get(language="FR")
    assert entry.translated_text == "Agde"
    assert entry.model_used == "source"


@pytest.mark.django_db
def test_task_translate_source_calls_llm_for_gb(monkeypatch, settings):
    from apps.translation_manager.models import TranslationSource
    from apps.translation_manager.tasks import task_translate_source

    settings.TRANSLATION_LLM_ENABLED = "true"

    monkeypatch.setattr(
        "apps.translation_manager.services.llm_client.translate_text",
        lambda text, lang: "Full board",
    )

    source = TranslationSource.objects.create(
        key="catalog-formula-label-pc-2",
        source_language="FR",
        source_text="Pension complète",
        source_model_ref="catalog.Formula.label",
    )

    result = task_translate_source(source.pk, ["GB"])
    assert result["ok"] is True
    entry = source.translations.get(language="GB")
    assert entry.translated_text == "Full board"
    assert entry.status == entry.STATUS_TRANSLATED
