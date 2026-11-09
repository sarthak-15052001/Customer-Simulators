from __future__ import annotations

import json
from datetime import date, datetime
from io import BytesIO
from typing import Any

from openpyxl import Workbook

from apps.pricing.models import SimulationLog


def build_simulation_logs_export() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Simulation Logs"

    fields = list(SimulationLog._meta.fields)
    headers = [field.attname for field in fields]
    worksheet.append(headers)

    queryset = SimulationLog.objects.all().order_by("-created_at", "-id")
    for row in queryset.iterator(chunk_size=1000):
        worksheet.append([_excel_value(getattr(row, field.attname)) for field in fields])

    for cell in worksheet[1]:
        cell.style = "Headline 4"

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _excel_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value
