"""Resto cost helpers. Port of vtf/front/src/utils/restoTab.ts."""
from __future__ import annotations


def family_meal_unit_price(*, meal: dict, adults: int, children: int) -> int:
    return max(0, meal["price_adult"]) * max(0, adults) + max(0, meal["price_child"]) * max(
        0, children
    )


def resto_total_amount(
    *, meals: list[dict], qty_by_meal_id: dict, adults: int, children: int
) -> int:
    """`meals[i]` must have keys `code`, `price_adult`, `price_child`."""
    total = 0
    for meal in meals:
        qty = qty_by_meal_id.get(meal["code"], 0)
        if qty <= 0:
            continue
        total += qty * family_meal_unit_price(meal=meal, adults=adults, children=children)
    return total
