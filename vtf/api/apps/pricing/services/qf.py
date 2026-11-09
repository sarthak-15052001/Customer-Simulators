"""Quotient familial calculator. Port of vtf/front/src/utils/qfCalc.ts."""
from __future__ import annotations

from ._round import jsround

QF_MIN = 0
QF_MAX = 5000


def calc_qf_from_income_parts(*, net_monthly_income: float, parts: float) -> int:
    income = max(0.0, net_monthly_income)
    p = max(1.0, parts)
    raw = income / p
    # `jsround`, not Python's banker `round`, to match `Math.round(raw / 10)`
    # in qfCalc.ts. Half-cases (e.g. raw=875) otherwise diverge between JS/Py.
    rounded = jsround(raw / 10) * 10
    return max(QF_MIN, min(QF_MAX, int(rounded)))
