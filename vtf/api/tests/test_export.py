from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.pricing.models import SimulationLog


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_simulation_logs_export_contains_all_model_fields(client):
    SimulationLog.objects.create(
        session_id="session-export",
        village=None,
        region="Atlantique",
        formule="PC",
        saison_key="ete",
        date_debut="2026-07-01",
        date_fin="2026-07-08",
        nuits=7,
        nb_adults=2,
        nb_children=1,
        children_ages=[8],
        qf_val=700,
        qf_badge="QF2",
        is_solo_parent=False,
        is_maxi_family=False,
        estimated_total=1200,
        per_person_per_day=57,
        discount_rate=0.1,
        promos_applied=["early_booking"],
        transport_mode="car",
        transport_cost=80,
        activities_cost=40,
        resto_cost=100,
        hotel_estimate=1500,
        hotel_savings=300,
        savings_pct=20,
        clicked_booking=True,
        time_on_result_ms=1234,
        ip_hash="ip-hash",
        user_agent="pytest",
        referrer="https://example.com",
        utm_source="newsletter",
        device_type="desktop",
        step_timings={"estimate": 100},
    )

    response = client.get("/api/v1/exports/simulation-logs")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response["Content-Disposition"] == 'attachment; filename="simulation_logs.xlsx"'

    workbook = load_workbook(BytesIO(response.content))
    worksheet = workbook["Simulation Logs"]
    headers = [cell.value for cell in worksheet[1]]
    expected_headers = [field.attname for field in SimulationLog._meta.fields]

    assert headers == expected_headers
    assert worksheet.max_row == 2

    row = dict(zip(headers, [cell.value for cell in worksheet[2]]))
    assert row["session_id"] == "session-export"
    assert row["village_id"] is None
    assert row["children_ages"] == "[8]"
    assert row["promos_applied"] == '["early_booking"]'
    assert row["step_timings"] == '{"estimate": 100}'
