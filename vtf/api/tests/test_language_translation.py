"""Language translation middleware and schema tests.

Covers:
  - ApiResponseTranslationMiddleware — payload translation, FR default,
    static value substitution, LLM bypass for known values
  - Middleware exclusion — non-v1 APIs are never translated
  - Default language — browser Accept-Language header is ignored;
    only explicit ?language= / ?lang= query params trigger translation
  - add_global_language_parameter — language selector appears in Swagger
    only for translatable v1 endpoints

Run with:
    pytest tests/test_language_translation.py -v
"""
from __future__ import annotations

import pytest
from django.test import RequestFactory
from rest_framework import status

from common.middleware import ApiResponseTranslationMiddleware
from common.response import CustomResponse
from common.schema import add_global_language_parameter


# ---------------------------------------------------------------------------
# Middleware — envelope translation
# ---------------------------------------------------------------------------


def test_global_translation_middleware_translates_api_envelope(monkeypatch):
    """Middleware passes the response payload through translate_response_payload
    and re-renders the result when language=GB is requested."""
    request = RequestFactory().get("/api/v1/formules?language=GB")

    def view(_request):
        return CustomResponse.success(
            "Formules récupérées avec succès.",
            data={"label": "Pension complète", "code": "PC"},
        )

    def fake_translate(payload, language):
        assert language == "GB"
        translated = dict(payload)
        translated["message"] = "Formulas fetched successfully."
        translated["data"] = dict(payload["data"], label="Full board")
        return translated

    monkeypatch.setattr(
        "apps.catalog.services.translations.translate_response_payload",
        fake_translate,
    )

    response = ApiResponseTranslationMiddleware(view)(request)

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Language"] == "gb"
    assert response.data["message"] == "Formulas fetched successfully."
    assert response.data["data"]["label"] == "Full board"
    assert response.data["data"]["code"] == "PC"


# ---------------------------------------------------------------------------
# Middleware — scope: only /api/v1/ endpoints are translated
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/v2/recommendations?language=GB",
        "/api/v3/admin/cache/status?language=GB",
        "/api/v4/tariff-scraper/status?language=GB",
        "/api/v5/header-banner?language=GB",
    ],
)
def test_translation_middleware_skips_non_v1_apis(monkeypatch, path):
    """Responses from non-v1 API paths must never go through the translator."""
    request = RequestFactory().get(path)

    def view(_request):
        return CustomResponse.success(
            "Recommendations generated.",
            data={"label": "Village familial"},
        )

    def fail_translate(_payload, _language):
        raise AssertionError("non-v1 API responses should not be translated")

    monkeypatch.setattr(
        "apps.catalog.services.translations.translate_response_payload",
        fail_translate,
    )

    response = ApiResponseTranslationMiddleware(view)(request)

    assert response.data["message"] == "Recommendations generated."
    assert response.data["data"]["label"] == "Village familial"
    assert "Content-Language" not in response


# ---------------------------------------------------------------------------
# Middleware — FR default: messages localised, data unchanged
# ---------------------------------------------------------------------------


def test_global_translation_middleware_translates_french_envelope_message():
    """When language=FR the envelope message is localised via the static map
    and the data payload is returned unchanged (no LLM call)."""
    request = RequestFactory().get("/api/v1/animations?language=FR")

    def view(_request):
        return CustomResponse.success(
            "Animations fetched.",
            data=[
                {
                    "nom": "Clubs enfants & ados",
                    "note": "Encadrés par animateurs diplômés · sans supplément",
                    "order": 0,
                }
            ],
        )

    response = ApiResponseTranslationMiddleware(view)(request)

    assert response["Content-Language"] == "fr"
    assert response.data["message"] == "Animations récupérées."
    assert response.data["data"][0]["nom"] == "Clubs enfants & ados"


# ---------------------------------------------------------------------------
# Middleware — static value substitution (GB)
# ---------------------------------------------------------------------------


def test_global_translation_middleware_translates_static_animation_payload_to_english():
    """Known static animation strings are replaced from STATIC_RESPONSE_TEXT_VALUES
    without calling the LLM when language=GB."""
    request = RequestFactory().get("/api/v1/animations?language=GB")

    def view(_request):
        return CustomResponse.success(
            "Animations fetched.",
            data=[
                {
                    "nom": "Clubs enfants & ados",
                    "note": "Encadrés par animateurs diplômés · sans supplément",
                    "order": 0,
                }
            ],
        )

    response = ApiResponseTranslationMiddleware(view)(request)

    assert response["Content-Language"] == "gb"
    assert response.data["message"] == "Animations fetched."
    assert response.data["data"][0]["nom"] == "Kids and teen clubs"
    assert (
        response.data["data"][0]["note"]
        == "Supervised by qualified activity leaders · no extra charge"
    )


def test_static_animation_translation_does_not_require_llm(monkeypatch, settings):
    """Static value substitution must resolve without reaching the LLM."""
    settings.TRANSLATION_LLM_ENABLED = "false"
    request = RequestFactory().get("/api/v1/animations?language=GB")

    def view(_request):
        return CustomResponse.success(
            "Animations fetched.",
            data=[{"nom": "Animations de soirée", "note": "Programme variable"}],
        )

    def fail_llm(*_args, **_kwargs):
        raise AssertionError("known static values should not call the LLM")

    monkeypatch.setattr("apps.catalog.services.translations._call_llm_chunk", fail_llm)

    response = ApiResponseTranslationMiddleware(view)(request)

    assert response["Content-Language"] == "gb"
    assert response.data["data"][0]["nom"] == "Evening entertainment"
    assert response.data["data"][0]["note"] == "Programme variable"


# ---------------------------------------------------------------------------
# Middleware — default language: Accept-Language header is ignored
# ---------------------------------------------------------------------------


def test_translation_middleware_ignores_accept_language_header(monkeypatch):
    """The browser's Accept-Language header must NOT trigger translation.
    Only an explicit ?language= query param should activate it."""
    request = RequestFactory().get(
        "/api/v1/marketing-seasons",
        HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9",
    )

    def view(_request):
        return CustomResponse.success(
            "Seasons fetched.",
            data=[{"nom": "Saison Été"}],
        )

    def fail_translate(_payload, _language):
        raise AssertionError("Accept-Language header alone should not trigger translation")

    monkeypatch.setattr(
        "apps.catalog.services.translations.translate_response_payload",
        fail_translate,
    )

    response = ApiResponseTranslationMiddleware(view)(request)

    assert response.data["data"][0]["nom"] == "Saison Été"
    assert "Content-Language" not in response


# ---------------------------------------------------------------------------
# OpenAPI schema — language parameter injection
# ---------------------------------------------------------------------------


def test_language_schema_parameter_is_v1_only():
    """add_global_language_parameter injects the language selector only on
    translatable /api/v1/ paths; all other versions are left untouched."""
    schema = {
        "paths": {
            "/api/v1/formules": {"get": {}},
            "/api/v2/recommendations": {"get": {}},
            "/api/v3/admin/cache/status": {"get": {}},
            "/api/v4/tariff-scraper/status": {"get": {}},
            "/api/v5/header-banner": {"get": {}},
        }
    }

    add_global_language_parameter(schema, generator=None, request=None, public=True)

    assert schema["paths"]["/api/v1/formules"]["get"]["parameters"][0]["name"] == "language"
    assert "parameters" not in schema["paths"]["/api/v2/recommendations"]["get"]
    assert "parameters" not in schema["paths"]["/api/v3/admin/cache/status"]["get"]
    assert "parameters" not in schema["paths"]["/api/v4/tariff-scraper/status"]["get"]
    assert "parameters" not in schema["paths"]["/api/v5/header-banner"]["get"]


# ---------------------------------------------------------------------------
# Registry — full catalog coverage, and non-text fields skipped gracefully
# ---------------------------------------------------------------------------


def test_registry_covers_every_catalog_model_with_text_fields():
    """Every catalog model that actually has a CharField/TextField must be
    represented in REGISTRY — this is the fix for the "only 4 of 12+ models
    covered" gap."""
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


@pytest.mark.django_db
def test_sync_field_skips_non_text_field_gracefully():
    """A FieldSpec pointing at a numeric/date/JSON field must never be sent
    to the LLM — sync_field should skip it cleanly instead of stringifying
    and mistranslating it."""
    from apps.translation_manager.services.registry import FieldSpec, sync_field

    for field_name in ("km", "id"):  # Attraction.km is numeric, .village_id is a FK/int
        spec = FieldSpec("catalog", "Attraction", field_name)
        result = sync_field(spec)
        assert result["created"] == 0
        assert result["updated"] == 0
        assert result.get("field_skipped") is True


@pytest.mark.django_db
def test_sync_field_translates_actual_text_field():
    from apps.catalog.models import Formula
    from apps.translation_manager.models import TranslationSource
    from apps.translation_manager.services.registry import FieldSpec, sync_field

    Formula.objects.create(
        code="PC", icon="🍽", icon_key="pc", label="Pension complète",
        short_description="Tout compris", sort_order=0,
    )
    spec = FieldSpec("catalog", "Formula", "label")
    result = sync_field(spec)
    assert result["created"] == 1
    source = TranslationSource.objects.get(source_model_ref="catalog.Formula.label")
    assert source.source_text == "Pension complète"
