from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.catalog.serializers import SimulationPdfInputSerializer
from apps.catalog.services.simulation_pdf import build_simulation_pdf_html


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def pdf_payload():
    return {
        "villageName": "Blainville",
        "dateDebut": "2026-04-15",
        "dateFin": "2026-04-17",
        "nuits": "2",
        "saison": "vs",
        "adultes": "2",
        "nbEnfants": "3",
        "enfantsAges": "8 · 5 · 6",
        "totalEuro": "752",
        "perPersonEuro": "150",
        "perPersonPerDay": "75",
        "perDayFamily": "376",
        "formuleLabel": "Pension complète",
        "perAdultBase": "138",
        "totalAdults": "275",
        "children": [
            {"age": "8", "discountLabel": "0.2", "amount": "110"},
            {"age": "5", "discountLabel": "0.4", "amount": "83"},
            {"age": "6", "discountLabel": "0.2", "amount": "110"},
        ],
        "totalChildren": "303",
        "staySubtotal": "578",
        "adhesionEuro": "44",
        "stayPackageTotal": "622",
        "activitiesTotal": "75",
        "restoTotal": "55",
        "transportModeLabel": "Transport (total)",
        "transportDetailNote": "Transport (total)",
        "transportTotal": "0",
        "formuleIncludesText": "Inclus en pension complète : Repas buffet + vin à table · Clubs enfants · Animations · Piscine & espace bien-être · Randonnées guidées · Ménage · WIFI",
        "hotelSavingsEuro": "274",
        "savingsPct": "27",
        "bookingUrl": "https://www.vtf-vacances.com/fr_FR/summer/village-vacances/manche/blainville-sur-mer/le-senequet?search_engine%5BstartedAt%5D=2026-04-15&search_engine%5BendedAt%5D=2026-04-17&search_engine%5BnbPersons%5D=5&search_engine%5BnbAdults%5D=2&search_engine%5BnbBabies%5D=0&search_engine%5BnbChildren3%5D=1&search_engine%5BnbChildren1%5D=2&search_engine%5BnbChildren2%5D=0",
        "planning": [
            {
                "kind": "day",
                "label": "Wed, 15 Apr",
                "morning": "Clubs enfants & ados",
                "afternoon": "Balade sur les sentiers côtiers GR34",
                "evening": "Fête de la mer (saison estivale)",
            },
            {
                "kind": "day",
                "label": "Thu, 16 Apr",
                "morning": "Clubs enfants & ados · Animations de journée · Animations de soirée",
                "afternoon": "Aquarium de Saint-Malo",
                "evening": "Snack",
            },
            {
                "kind": "day",
                "label": "Fri, 17 Apr",
                "morning": "Clubs enfants & ados",
                "afternoon": "Temps libre",
                "evening": "Animations de journée",
            },
            {
                "kind": "departure",
                "label": "Fri, 17 Apr",
                "morning": "Clubs enfants & ados",
                "afternoon": "Temps libre",
                "evening": "Animations de journée",
            },
        ],
    }


@pytest.mark.django_db
def test_simulations_pdf_returns_pdf(client, pdf_payload):
    response = client.post("/api/v1/simulations/pdf/", pdf_payload, format="json")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == 'attachment; filename="simulation-blainville.pdf"'
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000


@pytest.mark.django_db
def test_simulations_pdf_accepts_pdf_header(client, pdf_payload):
    response = client.post(
        "/api/v1/simulations/pdf/",
        pdf_payload,
        format="json",
        HTTP_ACCEPT="application/pdf",
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


@pytest.mark.django_db
def test_simulations_pdf_requires_payload_fields(client, pdf_payload):
    pdf_payload.pop("villageName")

    response = client.post("/api/v1/simulations/pdf/", pdf_payload, format="json")

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Invalid simulation PDF payload."
    assert "villageName" in body["errors"]


@pytest.mark.django_db
def test_simulations_pdf_validates_booking_url(client, pdf_payload):
    pdf_payload["bookingUrl"] = "not-a-url"

    response = client.post("/api/v1/simulations/pdf/", pdf_payload, format="json")

    assert response.status_code == 400
    assert "bookingUrl" in response.json()["errors"]


def test_simulation_pdf_serializer_rejects_blank_strings(pdf_payload):
    pdf_payload["totalEuro"] = "   "

    serializer = SimulationPdfInputSerializer(data=pdf_payload)

    assert not serializer.is_valid()
    assert "totalEuro" in serializer.errors


def test_simulation_pdf_html_escapes_dynamic_values(pdf_payload):
    pdf_payload["villageName"] = "<script>alert(1)</script>"

    html = build_simulation_pdf_html(pdf_payload)

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_simulation_pdf_html_renders_children_and_planning_arrays(pdf_payload):
    html = build_simulation_pdf_html(pdf_payload)

    assert "Âges:" not in html
    assert "Enfant 3" in html
    assert "0.4" in html
    assert "Aquarium de Saint-Malo" in html
    assert "Départ" in html
    assert "27%" in html
