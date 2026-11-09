"""Transport (car / train) cost helpers.

Port of vtf/front/src/utils/transportTab.ts. Default fuel/toll/train constants
mirror VTF_TRANSPORT_DEFAULTS from vtfTransport.ts.
"""
from __future__ import annotations

from typing import Literal

from ._round import jsround

FuelKey = Literal["essence", "diesel", "electrique"]

FUEL_COST_PER_KM: dict[str, float] = {
    "essence": 0.12,
    "diesel": 0.09,
    "electrique": 0.04,
}
TOLL_PER_KM = 0.07
TRAIN_ADULT_ONE_WAY = 65
TRAIN_CHILD_ONE_WAY = 35


def fuel_cost_per_km(fuel: str) -> float:
    """Return cost-per-km for `fuel`, looking up the DB first.

    Falls back to the hardcoded FUEL_COST_PER_KM dict so this works during
    tests and migrations when the catalog app isn't yet available.
    """
    try:
        from apps.catalog.models import FuelOption  # local import: avoids circular
        option = FuelOption.objects.filter(key=fuel).values_list("cost_per_km", flat=True).first()
        if option is not None:
            return float(option)
    except Exception:  # noqa: BLE001
        pass
    return FUEL_COST_PER_KM.get(fuel, FUEL_COST_PER_KM["essence"])


def car_cost_breakdown(*, distance_one_way_km: float, fuel: str) -> dict:
    d = max(0.0, distance_one_way_km)
    km_ar = d * 2
    fuel_cost = jsround(km_ar * fuel_cost_per_km(fuel))
    toll_cost = jsround(km_ar * TOLL_PER_KM)
    return {
        "kmAR": int(km_ar),
        "fuelCost": fuel_cost,
        "tollCost": toll_cost,
        "total": fuel_cost + toll_cost,
    }


def train_total(*, adults: int, children: int) -> int:
    a = max(0, adults)
    c = max(0, children)
    one_way = TRAIN_ADULT_ONE_WAY * a + TRAIN_CHILD_ONE_WAY * c
    return jsround(one_way * 2)
