from __future__ import annotations

from unittest.mock import patch

import pytest
import requests
from apps.mailer.brevo_client import (
    BREVO_SMTP_URL,
    BrevoError,
    send_transactional_email,
)
from apps.mailer.email_builder import _fmt, build_html, build_subject
from apps.mailer.serializers import SendSimulationSerializer
from django.test import override_settings
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def mailer_payload():
    return {
        "recipientEmail": "guest@example.com",
        "locale": "FR",
        "bookingUrl": "https://example.com/book",
        "villageName": "Village Test",
        "nuits": 7,
        "saison": "ete",
        "dateDebut": "2026-07-01",
        "dateFin": "2026-07-08",
        "adultes": 2,
        "enfantsAges": [8],
        "formule": "PC",
        "envKey": "mer",
        "perPersonPerDay": 50,
        "perDayFamily": 150,
        "total": 1050,
        "perPerson": 350,
        "perAdultBase": 400,
        "totalAdults": 800,
        "childAmounts": [250],
        "totalChildren": 250,
        "adhesion": 30,
        "staySubtotal": 1080,
        "activitiesTotal": 0,
        "restoTotal": 0,
        "transportMode": "car",
        "transportKm": 100,
        "transportTotal": 80,
        "hotelEstimate": 1400,
        "hotelSavings": 320,
        "savingsPct": 23,
    }


@pytest.mark.django_db
def test_mailer_brevo_error_uses_common_response_envelope(client, mailer_payload):
    with (
        patch("apps.mailer.views.build_subject", return_value="Simulation"),
        patch("apps.mailer.views.build_html", return_value="<p>Simulation</p>"),
        patch(
            "apps.mailer.views.send_transactional_email",
            side_effect=BrevoError(0, "BREVO_API_KEY is not configured."),
        ),
    ):
        resp = client.post("/api/v1/mailer/send-simulation", mailer_payload, format="json")

    assert resp.status_code == 502
    assert resp.json() == {
        "success": False,
        "message": "Email delivery failed.",
        "data": {
            "detail": "BREVO_API_KEY is not configured.",
            "brevoStatusCode": 0,
        },
    }


@pytest.mark.django_db
def test_mailer_success_uses_common_response_envelope(client, mailer_payload):
    with (
        patch("apps.mailer.views.build_subject", return_value="Simulation"),
        patch("apps.mailer.views.build_html", return_value="<p>Simulation</p>"),
        patch("apps.mailer.views.send_transactional_email", return_value={"messageId": "abc-123"}),
    ):
        resp = client.post("/api/v1/mailer/send-simulation", mailer_payload, format="json")

    body = resp.json()
    assert resp.status_code == 200
    assert body["success"] is True
    assert body["message"] == "Simulation email sent successfully."
    assert body["data"]["messageId"] == "abc-123"
    assert body["data"]["recipient"] == "guest@example.com"
    assert "sentAt" in body["data"]


@pytest.mark.django_db
@override_settings(
    BREVO_API_KEY="xkeysib-valid-test-key",
    BREVO_SENDER_EMAIL="sender@example.com",
    BREVO_SENDER_NAME="Sender Name",
)
def test_mailer_full_success_flow_sends_rendered_email(client, mailer_payload):
    fake_response = FakeBrevoResponse(payload={"messageId": "full-flow-123"})

    with patch("apps.mailer.brevo_client.requests.post", return_value=fake_response) as post_mock:
        resp = client.post("/api/v1/mailer/send-simulation", mailer_payload, format="json")

    body = resp.json()
    assert resp.status_code == 200
    assert body["success"] is True
    assert body["message"] == "Simulation email sent successfully."
    assert body["data"]["messageId"] == "full-flow-123"
    assert body["data"]["recipient"] == "guest@example.com"

    post_mock.assert_called_once()
    _, kwargs = post_mock.call_args
    assert kwargs["json"]["sender"] == {"email": "sender@example.com", "name": "Sender Name"}
    assert kwargs["json"]["to"] == [{"email": "guest@example.com"}]
    assert "Village Test" in kwargs["json"]["subject"]
    assert "Village Test" in kwargs["json"]["htmlContent"]
    assert 'href="https://example.com/book"' in kwargs["json"]["htmlContent"]
    assert kwargs["json"]["tags"] == ["simulation", "vtf-budget"]


@pytest.mark.django_db
def test_mailer_accepts_blank_env_key(client, mailer_payload):
    mailer_payload["envKey"] = ""

    with (
        patch("apps.mailer.views.build_subject", return_value="Simulation"),
        patch("apps.mailer.views.build_html", return_value="<p>Simulation</p>"),
        patch("apps.mailer.views.send_transactional_email", return_value={"messageId": "abc-123"}),
    ):
        resp = client.post("/api/v1/mailer/send-simulation", mailer_payload, format="json")

    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.django_db
def test_mailer_validation_error_uses_common_envelope(client, mailer_payload):
    mailer_payload["recipientEmail"] = "not-an-email"

    with patch("apps.mailer.views.send_transactional_email") as send_mock:
        resp = client.post("/api/v1/mailer/send-simulation", mailer_payload, format="json")

    body = resp.json()
    assert resp.status_code == 400
    assert body["success"] is False
    assert body["message"] == "Validation failed. Please check your input."
    assert body["data"] is None
    assert "recipientEmail" in body["errors"]
    send_mock.assert_not_called()


@pytest.mark.django_db
def test_mailer_email_build_error_uses_common_envelope(client, mailer_payload):
    with (
        patch("apps.mailer.views.build_subject", side_effect=ValueError("template data broken")),
        patch("apps.mailer.views.send_transactional_email") as send_mock,
    ):
        resp = client.post("/api/v1/mailer/send-simulation", mailer_payload, format="json")

    assert resp.status_code == 500
    assert resp.json() == {
        "success": False,
        "message": "Failed to build email content.",
        "data": {"detail": "template data broken"},
    }
    send_mock.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("brevo_status", "expected_http_status"),
    [
        (401, 401),
        (403, 403),
        (429, 429),
        (500, 502),
        (503, 502),
        (504, 502),
        (400, 502),
        (0, 502),
    ],
)
def test_mailer_maps_brevo_errors_to_expected_http_status(
    client,
    mailer_payload,
    brevo_status,
    expected_http_status,
):
    with (
        patch("apps.mailer.views.build_subject", return_value="Simulation"),
        patch("apps.mailer.views.build_html", return_value="<p>Simulation</p>"),
        patch(
            "apps.mailer.views.send_transactional_email",
            side_effect=BrevoError(brevo_status, "Brevo rejected the request."),
        ),
    ):
        resp = client.post("/api/v1/mailer/send-simulation", mailer_payload, format="json")

    assert resp.status_code == expected_http_status
    assert resp.json() == {
        "success": False,
        "message": "Email delivery failed.",
        "data": {
            "detail": "Brevo rejected the request.",
            "brevoStatusCode": brevo_status,
        },
    }


@pytest.mark.django_db
@override_settings(
    BREVO_API_KEY="xkeysib-valid-test-key",
    BREVO_SENDER_EMAIL="sender@example.com",
    BREVO_SENDER_NAME="Sender Name",
)
def test_send_email_brevo_api_error_returns_502(client, mailer_payload):
    """When Brevo returns non-2xx at the HTTP level, the API must return a 502
    with the standard error envelope including brevoStatusCode."""
    fake_response = FakeBrevoResponse(
        status_code=400,
        payload={"message": "Invalid payload"},
        text="Invalid payload",
        ok=False,
    )

    with patch("apps.mailer.brevo_client.requests.post", return_value=fake_response):
        resp = client.post("/api/v1/mailer/send-simulation", mailer_payload, format="json")

    body = resp.json()
    assert resp.status_code == 502, f"Expected 502, got {resp.status_code}: {body}"
    assert body["success"] is False
    assert body["message"] == "Email delivery failed."
    assert body["data"]["brevoStatusCode"] == 400
    assert "400" in body["data"]["detail"]


@pytest.mark.django_db
def test_mailer_unexpected_send_error_uses_common_envelope(client, mailer_payload):
    with (
        patch("apps.mailer.views.build_subject", return_value="Simulation"),
        patch("apps.mailer.views.build_html", return_value="<p>Simulation</p>"),
        patch("apps.mailer.views.send_transactional_email", side_effect=RuntimeError("boom")),
    ):
        resp = client.post("/api/v1/mailer/send-simulation", mailer_payload, format="json")

    assert resp.status_code == 500
    assert resp.json() == {
        "success": False,
        "message": "Unexpected error during email delivery.",
        "data": {"detail": "boom"},
    }


def test_serializer_applies_optional_defaults(mailer_payload):
    mailer_payload.pop("bookingUrl")
    mailer_payload.pop("envKey")
    mailer_payload.pop("transportMode")
    mailer_payload.pop("transportKm")
    mailer_payload.pop("transportTotal")

    ser = SendSimulationSerializer(data=mailer_payload)

    assert ser.is_valid(), ser.errors
    assert ser.validated_data["bookingUrl"] == ""
    assert ser.validated_data["redirectUrl"] == ""
    assert ser.validated_data["envKey"] == ""
    assert ser.validated_data["transportMode"] == "car"
    assert ser.validated_data["transportKm"] == 0
    assert ser.validated_data["transportTotal"] == 0
    assert ser.validated_data["childAges"] == ""
    assert ser.validated_data["formulaIncludes"] == ""
    assert ser.validated_data["transportLabel"] == ""
    assert ser.validated_data["simulationData"] == {}


def test_serializer_accepts_frontend_template_payload_shape():
    payload = _new_frontend_payload()

    ser = SendSimulationSerializer(data=payload)

    assert ser.is_valid(), ser.errors
    assert ser.validated_data["formule"] == "Pension complète"
    assert ser.validated_data["childAges"] == "2 ans"
    assert ser.validated_data["transportLabel"] == "Voiture — 425 km (aller)"
    assert ser.validated_data["bookingUrl"].endswith("b22842c%22")
    assert ser.validated_data["simulationData"]["villageId"] == "lacanau"


@pytest.mark.django_db
def test_mailer_endpoint_accepts_frontend_template_payload_shape(client):
    with (
        patch("apps.mailer.views.build_subject", return_value="Simulation"),
        patch("apps.mailer.views.build_html", return_value="<p>Simulation</p>"),
        patch("apps.mailer.views.send_transactional_email", return_value={"messageId": "abc-123"}),
    ):
        resp = client.post(
            "/api/v1/mailer/send-simulation",
            _new_frontend_payload(),
            format="json",
        )

    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_fmt_uses_plain_integers_without_thin_space_thousands_separator():

    assert _fmt(2268) == "2268"
    assert _fmt(1050) == "1050"
    assert "\u202f" not in _fmt(1_553_418)


def test_email_subject_contains_village_nights_and_total(mailer_payload):
    subject = build_subject(mailer_payload)

    assert "Village Test" in subject
    assert "7" in subject
    assert "1050" in subject


@pytest.mark.django_db
def test_email_html_contains_core_simulation_values(mailer_payload):
    html = build_html(mailer_payload)

    assert "Village Test" in html
    assert "01/07/2026" in html
    assert "08/07/2026" in html
    assert "1050" in html
    assert 'href="https://example.com/book"' in html
    assert "Je réserve mes vacances VTF" in html
    assert "tel:+33442123200" in html


@pytest.mark.django_db
def test_email_html_renders_redirect_cta_when_booking_url_is_missing(mailer_payload):
    mailer_payload.pop("bookingUrl")
    mailer_payload["redirectUrl"] = "https://api.example.com/api/v1/go/token-123%22"

    html = build_html(mailer_payload)

    assert 'href="https://api.example.com/api/v1/go/token-123"' in html
    assert "%22" not in html


@pytest.mark.django_db
def test_email_html_renders_frontend_booking_url_alias_cta(mailer_payload):
    mailer_payload.pop("bookingUrl")
    mailer_payload["booking_url"] = "https://api.example.com/api/v1/go/snake-token"

    html = build_html(mailer_payload)

    assert 'href="https://api.example.com/api/v1/go/snake-token"' in html


@pytest.mark.django_db
def test_email_html_renders_new_frontend_template_fields():
    html = build_html(_new_frontend_payload())
    text_html = html.replace("&nbsp;", " ")

    assert "Lacanau" in html
    assert "Pension complète" in html
    assert "2 adultes · 1 enfants" in html
    assert "2 ans" in html
    assert "Voiture — 425 km (aller)" in html
    assert "Inclus en pension complète" in html
    assert "256 €" in text_html
    assert 'href="http://192.168.1.89:8000/api/v1/go/TGoIvr0UguQyt4ZlTbEsog.1779613554.28890f67006642f10fe19b870b22842c"' in html
    assert "%22" not in html


def _new_frontend_payload():
    return {
        "recipientEmail": "shahil.patel@iflair.com",
        "villageName": "Lacanau",
        "nuits": 2,
        "saison": "vs",
        "dateDebut": "2026-04-15",
        "dateFin": "2026-04-17",
        "adultes": 2,
        "formule": "Pension complète",
        "perPersonPerDay": 119,
        "perDayFamily": 357,
        "total": 714,
        "perPerson": 238,
        "perAdultBase": 128,
        "totalAdults": 256,
        "totalChildren": 13,
        "adhesion": 44,
        "staySubtotal": 269,
        "activitiesTotal": 202,
        "restoTotal": 62,
        "transportTotal": 137,
        "hotelEstimate": 963,
        "hotelSavings": 249,
        "savingsPct": 26,
        "formulaIncludes": "🥗 Inclus en pension complète : Repas buffet + vin à table · Clubs enfants · Animations · Piscine & espace bien-être · Randonnées guidées · Ménage · WIFI",
        "childAges": "2 ans",
        "transportLabel": "Voiture — 425 km (aller)",
        "bookingUrl": "http://192.168.1.89:8000/api/v1/go/TGoIvr0UguQyt4ZlTbEsog.1779613554.28890f67006642f10fe19b870b22842c%22",
        "simulationData": {
            "villageId": "lacanau",
            "family": {
                "adultes": 2,
                "enfants": [{"age": 2}],
                "qfVal": 10,
                "maxiFamily": False,
                "isSoloParent": False,
            },
            "sejour": {
                "dateDebut": "2026-04-15",
                "dateFin": "2026-04-17",
                "formule": "PC",
                "fNuits": 2,
                "transport": {
                    "mode": "car",
                    "distanceOneWayKm": 425,
                    "fuel": "diesel",
                },
            },
        },
    }


class FakeBrevoResponse:
    def __init__(self, status_code=201, payload=None, text="", ok=True):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.ok = ok
        self.elapsed = self

    def json(self):
        return self._payload

    def total_seconds(self):
        return 0.1


@override_settings(
    BREVO_API_KEY="xkeysib-valid-test-key",
    BREVO_SENDER_EMAIL="sender@example.com",
    BREVO_SENDER_NAME="Sender Name",
)
def test_brevo_client_posts_expected_payload():
    fake_response = FakeBrevoResponse(payload={"messageId": "message-123"})

    with patch("apps.mailer.brevo_client.requests.post", return_value=fake_response) as post_mock:
        result = send_transactional_email(
            to_email="guest@example.com",
            subject="Simulation",
            html_content="<p>Hello</p>",
            tags=["simulation"],
        )

    assert result == {"messageId": "message-123"}
    post_mock.assert_called_once()
    _, kwargs = post_mock.call_args
    assert post_mock.call_args.args[0] == BREVO_SMTP_URL
    assert kwargs["timeout"] == 15
    assert kwargs["headers"]["api-key"] == "xkeysib-valid-test-key"
    assert kwargs["json"] == {
        "sender": {"email": "sender@example.com", "name": "Sender Name"},
        "to": [{"email": "guest@example.com"}],
        "subject": "Simulation",
        "htmlContent": "<p>Hello</p>",
        "tags": ["simulation"],
    }


@override_settings(BREVO_API_KEY="")
def test_brevo_client_rejects_missing_api_key_before_network_call():
    with patch("apps.mailer.brevo_client.requests.post") as post_mock:
        with pytest.raises(BrevoError) as exc_info:
            send_transactional_email(
                to_email="guest@example.com",
                subject="Simulation",
                html_content="<p>Hello</p>",
            )

    assert exc_info.value.status_code == 0
    assert "BREVO_API_KEY" in exc_info.value.detail
    post_mock.assert_not_called()


@override_settings(BREVO_API_KEY="not-a-brevo-key")
def test_brevo_client_rejects_invalid_api_key_format_before_network_call():
    with patch("apps.mailer.brevo_client.requests.post") as post_mock:
        with pytest.raises(BrevoError) as exc_info:
            send_transactional_email(
                to_email="guest@example.com",
                subject="Simulation",
                html_content="<p>Hello</p>",
            )

    assert exc_info.value.status_code == 0
    assert "Invalid BREVO_API_KEY format" in exc_info.value.detail
    post_mock.assert_not_called()


@override_settings(BREVO_API_KEY="xkeysib-valid-test-key")
@pytest.mark.parametrize(
    ("response_status", "response_payload", "expected_detail"),
    [
        (401, {"message": "Key not valid"}, "Unauthorized"),
        (
            401,
            {
                "message": (
                    "We have detected you are using an unrecognised IP address "
                    "110.226.127.25. If you performed this action make sure to add "
                    "the new IP address in this link: "
                    "https://app.brevo.com/security/authorised_ips"
                )
            },
            "IP allowlist rejected this server",
        ),
        (403, {"message": "No permission"}, "Forbidden"),
        (429, {"message": "Too many requests"}, "Rate limited"),
        (500, {"message": "Server failed"}, "server error"),
        (503, {"message": "Unavailable"}, "temporarily unavailable"),
        (400, {"message": "Bad request"}, "Brevo API returned 400: Bad request"),
    ],
)
def test_brevo_client_raises_brevo_error_for_non_2xx_responses(
    response_status,
    response_payload,
    expected_detail,
):
    fake_response = FakeBrevoResponse(
        status_code=response_status,
        payload=response_payload,
        text="fallback text",
        ok=False,
    )

    with patch("apps.mailer.brevo_client.requests.post", return_value=fake_response):
        with pytest.raises(BrevoError) as exc_info:
            send_transactional_email(
                to_email="guest@example.com",
                subject="Simulation",
                html_content="<p>Hello</p>",
            )

    assert exc_info.value.status_code == response_status
    assert expected_detail in exc_info.value.detail


@override_settings(BREVO_API_KEY="xkeysib-valid-test-key")
@pytest.mark.parametrize(
    ("request_error", "expected_status"),
    [
        (requests.exceptions.Timeout(), 504),
        (requests.exceptions.ConnectionError("offline"), 503),
        (requests.exceptions.RequestException("request failed"), 500),
    ],
)
def test_brevo_client_maps_request_exceptions_to_brevo_error(request_error, expected_status):
    with patch("apps.mailer.brevo_client.requests.post", side_effect=request_error):
        with pytest.raises(BrevoError) as exc_info:
            send_transactional_email(
                to_email="guest@example.com",
                subject="Simulation",
                html_content="<p>Hello</p>",
            )

    assert exc_info.value.status_code == expected_status
