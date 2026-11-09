"""3-star hotel comparison helper. Port of vtf/front/src/utils/viewDetails.ts."""
from __future__ import annotations

import math
from typing import Literal

from ._round import jsround

SaisonKey = Literal["hs", "vs", "ete", "fetes"]


def get_hotel_night_rate(saison_key: str | None) -> int:
    if saison_key == "ete":
        return 120
    if saison_key == "fetes":
        return 110
    return 90


def estimate_hotel_total(*, family: dict, estimate: dict) -> int:
    """family: {adultes, enfants:[{age}, ...]}; estimate: {saisonKey, nuits, transportTotal}."""
    nuit_rate = get_hotel_night_rate(estimate["saisonKey"])
    nuits = max(1, estimate["nuits"])
    nb_adults = family["adultes"]
    nb_children = len(family["enfants"])

    nb_ch = math.ceil(nb_adults / 2 + (1 if nb_children > 0 else 0))
    hotel_heberg = nuit_rate * nb_ch * nuits
    hotel_resto = (28 * nb_adults + 15 * nb_children) * 3 * nuits
    hotel_act = (15 * nb_adults + 10 * nb_children) * math.ceil(nuits / 2)
    transport = max(0, estimate["transportTotal"])

    return jsround(hotel_heberg + hotel_resto + hotel_act + transport)


def calculate_hotel_savings(*, family: dict, estimate: dict) -> int:
    hotel = estimate_hotel_total(family=family, estimate=estimate)
    vtf = max(0, estimate["total"])
    return max(0, hotel - vtf)
