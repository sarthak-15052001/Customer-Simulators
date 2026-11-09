# 04 — Pricing services (port from TS)

> All services are **pure functions**: they take dicts/dataclasses in, return numbers/dataclasses out.
> No DB access inside services — pass `pricing_rules` (dict) and `village` (dict) as arguments.
> This makes them trivially unit-testable and lets us reuse them in batch jobs / async tasks.

## Module map

```
apps/pricing/services/
├── __init__.py
├── calendar.py             # diff_nuits, date_to_saison_idx, is_village_ouvert, get_stay_days
├── family.py               # child_discount_fraction, qf_badge_kind
├── qf.py                   # calc_qf_from_income_parts
├── promos.py               # available_sejour_promos, promo_key_from_rate
├── transport.py            # fuel_cost_per_km, car_cost_breakdown, train_total
├── resto.py                # resto_total_amount, family_meal_unit_price
├── hotel.py                # get_hotel_night_rate, estimate_hotel_total
├── stay_estimate.py        # ⭐ estimate_sejour_total — cœur métier
├── booking_url.py          # build_vtf_booking_url + token mint/verify
└── highlights.py           # get_highlights (i18n-aware)
```

## Conventions

- All public functions accept **kwargs** (no positional after the first arg).
- Money values are passed/returned as **int euros** (round at the boundary).
- Dates: `datetime.date` in/out, ISO `YYYY-MM-DD` at the API boundary.
- Pass `pricing_rules: dict` explicitly — never read `PricingRules.active()` inside a service.
- Pass `now: date` for time-dependent functions (testability).

## `calendar.py`

> Source: `vtf/front/src/utils/stayTab.ts:33-83` and `planningTab.ts`

```python
from __future__ import annotations
from datetime import date, timedelta
from typing import Literal
import re

SaisonKey = Literal["hs", "vs", "ete", "fetes"]
SAISON_KEYS: list[SaisonKey] = ["hs", "vs", "ete", "fetes"]


def diff_nuits(date_debut: date | None, date_fin: date | None) -> int | None:
    """Number of nights between two dates."""
    if not date_debut or not date_fin:
        return None
    return (date_fin - date_debut).days


def date_to_saison_idx(d: date | None) -> int:
    """
    Returns 0 (hs) | 1 (vs) | 2 (ete) | 3 (fetes).
    Port of stayTab.ts:dateToSaisonIdx. Cutoffs are *day-of-year * 100 + day*.
    """
    if d is None:
        return 2  # default ete
    m, j = d.month, d.day
    jj = m * 100 + j
    if 628 <= jj <= 901:
        return 2
    if jj >= 1220 or jj <= 106:
        return 3
    if (m == 2 and j >= 15) or (m == 3 and j <= 3):
        return 1
    if (m == 4 and j >= 12) or (m == 5 and j <= 4):
        return 1
    if (m == 10 and j >= 19) or (m == 11 and j <= 2):
        return 1
    return 0


def saison_key(d: date | None) -> SaisonKey:
    return SAISON_KEYS[date_to_saison_idx(d)]


# ─── Ouverture parser (port of parseOuverture) ─────────────────
_PLAGE_RE = re.compile(
    r"([0-9]{1,2})/([0-9]{1,2})(?:/([0-9]{2}))?[–-]([0-9]{1,2})/([0-9]{1,2})(?:/([0-9]{2}))?"
)


def parse_ouverture(s: str | None) -> list[tuple[int, int]] | None:
    """Returns list of (abs_start, abs_end) where abs = year*10000 + month*100 + day."""
    if not s or "confirmer" in s:
        return None
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"[A-Za-zÀ-ÿ]+\s+(?:LOC|PC|DP)[/A-Za-z]*", "", s)
    plages: list[tuple[int, int]] = []
    for m in _PLAGE_RE.finditer(s):
        d1j, d1m, d1y_raw = int(m[1]), int(m[2]), int(m[3]) if m[3] else None
        d2j, d2m, d2y_raw = int(m[4]), int(m[5]), int(m[6]) if m[6] else None
        y2 = 2000 + d2y_raw if d2y_raw else 2026
        if d1y_raw:
            y1 = 2000 + d1y_raw
        elif d1m > d2m or (d1m == d2m and d1j > d2j):
            y1 = y2 - 1
        else:
            y1 = y2
        plages.append((y1 * 10000 + d1m * 100 + d1j, y2 * 10000 + d2m * 100 + d2j))
    return plages or None


def is_village_ouvert(ouverture: str | None, d: date | None) -> bool:
    """True if village is open at date d. Defaults to True when ouverture is unknown."""
    if not ouverture or not d:
        return True
    plages = parse_ouverture(ouverture)
    if not plages:
        return True
    djj = d.year * 10000 + d.month * 100 + d.day
    return any(start <= djj < end for start, end in plages)


def get_stay_days(date_debut: date | None, date_fin: date | None) -> list[dict]:
    """List of {key, label, date} for each day of the stay (inclusive)."""
    if not date_debut or not date_fin or date_fin < date_debut:
        return []
    out, cur, idx = [], date_debut, 0
    while cur <= date_fin and idx <= 31:
        out.append({"key": cur.isoformat(), "label": f"Jour {idx + 1}", "date": cur})
        cur += timedelta(days=1)
        idx += 1
    return out
```

## `family.py`

> Source: `vtf/front/src/utils/familyTab.ts`

```python
QF_SEUIL_BAS = 880
QF_SEUIL_HAUT = 1350


def child_discount_fraction(age: int) -> float:
    """
    Display-only dégressivité (no village context).
    For pricing, use stay_estimate._child_discount_fraction_with_bebe_club().
    """
    if age < 1: return 1.0
    if age < 3: return 0.9
    if age < 6: return 0.4
    if age < 11: return 0.2
    if age < 16: return 0.1
    return 0.0


def qf_badge_kind(qf_val: int | None) -> str:
    if qf_val is None: return "empty"
    if qf_val < QF_SEUIL_BAS: return "r1"
    if qf_val < QF_SEUIL_HAUT: return "r2"
    return "plein"
```

## `qf.py`

> Source: `vtf/front/src/utils/qfCalc.ts`

```python
QF_MIN, QF_MAX = 0, 5000


def calc_qf_from_income_parts(*, net_monthly_income: float, parts: float) -> int:
    income = max(0.0, net_monthly_income)
    p = max(1.0, parts)
    raw = income / p
    rounded = round(raw / 10) * 10
    return max(QF_MIN, min(QF_MAX, int(rounded)))
```

## `promos.py`

> Source: `vtf/front/src/utils/promosTab.ts`

```python
from datetime import date


def available_sejour_promos(*, date_debut: date, date_fin: date, now: date) -> list[dict]:
    """
    Port of availableSejourPromos. Returns list of {key, icon, label, description, tag, rate, kind}.

    Rules (2026):
      - 1ère Minute  : séjour mai–oct ET réservation strictement avant le 20/03
      - Dernière Min : départ dans ≤30 j ET hors été
      - Promo Jeudi  : hors été + 7 nuits min
      - Pack Surprise: hors été + 7 nuits min
      - Quinzaine futée: gérée séparément
    """
    m, j = date_debut.month, date_debut.day
    jj = m * 100 + j
    nuits = (date_fin - date_debut).days
    today_jj = now.month * 100 + now.day
    days_before = (date_debut - now).days
    ete = 628 <= jj <= 901

    out: list[dict] = []

    # 1ère Minute
    if 502 <= jj <= 1101 and today_jj < 320:
        is_jan = today_jj < 120
        is_fev = 120 <= today_jj < 220
        rate = 0.30 if is_jan else 0.20 if is_fev else 0.10
        tag = "−30%" if is_jan else "−20%" if is_fev else "−10%"
        out.append({
            "key": "premiere", "icon": "⏰", "label": "1ère Minute",
            "description": "Séjours mai–oct · Réservation avant le 20/03",
            "tag": tag, "rate": rate, "kind": "auto",
        })

    if 0 <= days_before <= 30 and not ete:
        out.append({
            "key": "derniere", "icon": "⚡", "label": "Dernière Minute",
            "description": "Départ dans moins de 30 jours · Hors été",
            "tag": "−40%", "rate": 0.40, "kind": "auto",
        })

    if not ete and nuits >= 7:
        out.append({
            "key": "jeudi", "icon": "🔥", "label": "Promo du Jeudi",
            "description": "Code JEUDI · Flash hebdo · Hors été · 7 nuits min",
            "tag": "−25%", "rate": 0.25, "kind": "auto",
        })
        out.append({
            "key": "pack", "icon": "🎁", "label": "Pack Surprise",
            "description": "Village mystère · Dès 319€/sem · 7 nuits min",
            "tag": "−35%", "rate": 0.35, "kind": "auto",
        })

    return out
```

## `transport.py`

> Source: `vtf/front/src/utils/transportTab.ts`

```python
from typing import Literal

FuelKey = Literal["essence", "diesel", "electrique"]

# Static defaults (port of vtfTransport.ts:VTF_FUELS / VTF_TRANSPORT_DEFAULTS)
FUEL_COST_PER_KM = {"essence": 0.12, "diesel": 0.09, "electrique": 0.04}
TOLL_PER_KM = 0.07
TRAIN_ADULT_ONE_WAY = 65
TRAIN_CHILD_ONE_WAY = 35


def fuel_cost_per_km(fuel: FuelKey) -> float:
    return FUEL_COST_PER_KM.get(fuel, FUEL_COST_PER_KM["essence"])


def car_cost_breakdown(*, distance_one_way_km: float, fuel: FuelKey) -> dict:
    d = max(0.0, distance_one_way_km)
    km_ar = d * 2
    fuel_cost = round(km_ar * fuel_cost_per_km(fuel))
    toll_cost = round(km_ar * TOLL_PER_KM)
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
    return round(one_way * 2)
```

## `resto.py`

> Source: `vtf/front/src/utils/restoTab.ts`

```python
def family_meal_unit_price(*, meal: dict, adults: int, children: int) -> int:
    return max(0, meal["price_adult"]) * max(0, adults) + max(0, meal["price_child"]) * max(0, children)


def resto_total_amount(*, meals: list[dict], qty_by_meal_id: dict, adults: int, children: int) -> int:
    total = 0
    for meal in meals:
        qty = qty_by_meal_id.get(meal["code"], 0)
        if qty <= 0:
            continue
        total += qty * family_meal_unit_price(meal=meal, adults=adults, children=children)
    return total
```

## `hotel.py`

> Source: `vtf/front/src/utils/viewDetails.ts` (consolidated — replaces the duplicate in `stayEstimate.ts`)

```python
from typing import Literal

SaisonKey = Literal["hs", "vs", "ete", "fetes"]


def get_hotel_night_rate(saison_key: SaisonKey | None) -> int:
    if saison_key == "ete": return 120
    if saison_key == "fetes": return 110
    return 90


def estimate_hotel_total(*, family: dict, estimate: dict) -> int:
    """
    Classic 3* hotel estimate for the same family + dates.
    family: {adultes, enfants:[{age}]}
    estimate: {saisonKey, nuits, transportTotal}
    """
    nuit_rate = get_hotel_night_rate(estimate["saisonKey"])
    nuits = max(1, estimate["nuits"])
    nb_adults = family["adultes"]
    nb_children = len(family["enfants"])

    nb_ch = (nb_adults + 1) // 2 + (1 if nb_children > 0 else 0)
    hotel_heberg = nuit_rate * nb_ch * nuits
    hotel_resto = (28 * nb_adults + 15 * nb_children) * 3 * nuits
    hotel_act = (15 * nb_adults + 10 * nb_children) * ((nuits + 1) // 2)
    transport = max(0, estimate["transportTotal"])

    return round(hotel_heberg + hotel_resto + hotel_act + transport)


def calculate_hotel_savings(*, family: dict, estimate: dict) -> int:
    hotel = estimate_hotel_total(family=family, estimate=estimate)
    vtf = max(0, estimate["total"])
    return max(0, hotel - vtf)
```

## `stay_estimate.py` — cœur métier

> Source: `vtf/front/src/utils/stayEstimate.ts:137-251`. Read the TS first.

This is the **most important** service. It must match the JS to the euro.

```python
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date
from typing import Optional

from .calendar import saison_key, diff_nuits
from .transport import car_cost_breakdown, train_total
from .resto import resto_total_amount
from .hotel import estimate_hotel_total

QF_SEUIL_BAS, QF_SEUIL_HAUT = 880, 1350


@dataclass
class ChildLine:
    age: int
    discount_fraction: float
    amount: int


@dataclass
class SejourEstimate:
    total: int
    per_person: int
    total_adults: int
    total_children: int
    per_adult_base: int
    child_lines: list[ChildLine]
    saison_key: str
    nuits: int
    discount_rate: float
    stay_subtotal: int
    adhesion: int
    solo_supplement: int
    extras_loc: int
    activities_total: int
    resto_total: int
    transport_total: int
    hotel_estimate: int
    hotel_savings: int
    savings_pct: float


def _child_discount_with_bebe_club(age: int, bebe_club: bool, rules: dict) -> float:
    cd = rules["childDiscounts"]
    if age < 1: return cd["lt1"]
    if age < 3: return cd["1to2_withBebeClub"] if bebe_club else cd["1to2_withoutBebeClub"]
    if age < 6: return cd["3to5"]
    if age < 11: return cd["6to10"]
    if age < 16: return cd["11to15"]
    return cd["ge16"]


def _qf_rate(qf_val: Optional[int], qf_exc: bool) -> float:
    if qf_val is None: return 0.0
    if qf_val < QF_SEUIL_BAS: return 0.10 if qf_exc else 0.17
    if qf_val < QF_SEUIL_HAUT: return 0.05 if qf_exc else 0.10
    return 0.0


def _duration_coef(nuits: int, rules: dict) -> float:
    exact = rules["durationCoefficients"].get(str(nuits))
    if isinstance(exact, (int, float)) and exact > 0:
        return float(exact)
    return nuits / 7


def _formula_coef(formule: str, rules: dict) -> float:
    if formule == "LOC": return 1.0
    c = rules["formulaCoefficients"].get(formule)
    return float(c) if isinstance(c, (int, float)) and c > 0 else 1.0


def _membership_fee(family: dict, rules: dict) -> int:
    m = rules.get("membership") or {"individual": 22, "familyOrCouple": 44}
    if family["adultes"] >= 2 or len(family["enfants"]) > 0:
        return m["familyOrCouple"]
    return m["individual"]


def _quinzaine_rate(sejour: dict, rules: dict) -> float:
    if not sejour.get("promos", {}).get("quinzaineFutee"): return 0.0
    if sejour["formule"] != "PC": return 0.0
    if sejour["fNuits"] < 14: return 0.0
    return float(rules.get("quinzaineFuteeRate", 0.10))


def _solo_supplement(family: dict, sejour: dict, nuits: int, rules: dict) -> int:
    if family["adultes"] != 1 or len(family["enfants"]) < 1: return 0
    mode = sejour.get("promos", {}).get("soloSupplementMode", "default")
    per_night = (rules.get("soloSupplementPerNight") or {}).get(mode, 22)
    return max(0, per_night) * nuits


def _maxi_family_factor(family: dict, rules: dict) -> float:
    if not family.get("maxiFamily"): return 1.0
    if len(family["enfants"]) < 3: return 1.0
    rate = float(rules.get("maxiFamilyChildrenRate", 0.20))
    return 1 - max(0.0, min(1.0, rate))


def estimate_sejour_total(
    *,
    family: dict,
    sejour: dict,
    village: dict,
    pricing_rules: dict,
    activities_by_region: dict[str, list[dict]] | None = None,
    meals_catalog: list[dict] | None = None,
) -> SejourEstimate | None:
    """
    Port of stayEstimate.ts:estimateSejourTotal. Returns None if dates invalid or
    village has no tarif for the saison/formule.
    """
    if not sejour.get("dateDebut") or not sejour.get("dateFin"):
        return None
    d_start = date.fromisoformat(sejour["dateDebut"])
    d_end = date.fromisoformat(sejour["dateFin"])
    nuits = (d_end - d_start).days
    if nuits < 1:
        return None

    sk = saison_key(d_start)
    coef = _duration_coef(nuits, pricing_rules)

    base_pc = (village["tarifs"].get("PC") or {}).get(sk, 0)
    base_loc = (village["tarifs"].get("LOC") or {}).get(sk, 0)
    base = base_loc if sejour["formule"] == "LOC" else base_pc
    if not base or base <= 0:
        return None

    pb = base * coef * _formula_coef(sejour["formule"], pricing_rules)

    qf = _qf_rate(family.get("qfVal"), bool(village.get("qfExc")))
    promo = max(0.0, min(1.0, sejour.get("promos", {}).get("promoSejourRate", 0.0)))
    quinzaine = _quinzaine_rate(sejour, pricing_rules)
    discount_rate = 1 - (1 - qf) * (1 - promo) * (1 - quinzaine)
    pb_after = pb * (1 - discount_rate)

    bebe_club = bool(village.get("bebeClub"))
    total_adults = pb_after * family["adultes"]

    child_factor = _maxi_family_factor(family, pricing_rules)
    child_lines: list[ChildLine] = []
    total_children = 0.0
    for child in family["enfants"]:
        frac = _child_discount_with_bebe_club(child["age"], bebe_club, pricing_rules)
        amount = pb_after * (1 - frac) * child_factor
        total_children += amount
        child_lines.append(ChildLine(age=child["age"], discount_fraction=frac, amount=round(amount)))

    solo_supp = _solo_supplement(family, sejour, nuits, pricing_rules)
    stay_subtotal = total_adults + total_children + solo_supp
    adhesion = _membership_fee(family, pricing_rules)

    kit_price = (pricing_rules.get("defaults") or {}).get("locKitPrice", 10)
    extras_loc = 0
    if sejour["formule"] == "LOC":
        extras_loc = (
            max(0, sejour.get("extras", {}).get("locCleaningFee", 0))
            + max(0, sejour.get("extras", {}).get("locKits", 0)) * kit_price
        )

    # Activities
    paid_acts = sejour.get("extraActivities", {}).get("paidQtyById") or {}
    activities_total = 0
    if paid_acts and activities_by_region:
        region_acts = activities_by_region.get(village["region"], [])
        nb_a, nb_c = family["adultes"], len(family["enfants"])
        for a in region_acts:
            qty = paid_acts.get(a["id"], 0)
            if qty <= 0:
                continue
            unit = max(0, a["ad"]) * nb_a + max(0, a["enf"]) * nb_c
            activities_total += qty * unit
        activities_total = round(activities_total)
    else:
        outings = max(0, sejour.get("activities", {}).get("outings", 0))
        unit = (
            max(0, sejour.get("activities", {}).get("priceAdult", 0)) * family["adultes"]
            + max(0, sejour.get("activities", {}).get("priceChild", 0)) * len(family["enfants"])
        )
        activities_total = outings * unit

    # Resto
    qty_by_meal = sejour.get("resto", {}).get("qtyByMealId") or {}
    resto_total = 0
    if qty_by_meal and meals_catalog:
        resto_total = resto_total_amount(
            meals=meals_catalog, qty_by_meal_id=qty_by_meal,
            adults=family["adultes"], children=len(family["enfants"]),
        )

    # Transport
    transport_total = 0
    transport = sejour.get("transport") or {}
    if transport.get("mode") == "car":
        transport_total = car_cost_breakdown(
            distance_one_way_km=transport.get("distanceOneWayKm", 400),
            fuel=transport.get("fuel", "essence"),
        )["total"]
    elif transport.get("mode") == "train":
        transport_total = train_total(
            adults=family["adultes"], children=len(family["enfants"]),
        )

    total = stay_subtotal + adhesion + extras_loc + activities_total + resto_total + transport_total
    persons = max(1, family["adultes"] + len(family["enfants"]))

    # Hotel comparison
    pre = SejourEstimate(
        total=round(total),
        per_person=round(total / persons),
        total_adults=round(total_adults),
        total_children=round(total_children),
        per_adult_base=round(pb_after),
        child_lines=child_lines,
        saison_key=sk,
        nuits=nuits,
        discount_rate=discount_rate,
        stay_subtotal=round(stay_subtotal),
        adhesion=round(adhesion),
        solo_supplement=round(solo_supp),
        extras_loc=round(extras_loc),
        activities_total=round(activities_total),
        resto_total=round(resto_total),
        transport_total=round(transport_total),
        hotel_estimate=0,
        hotel_savings=0,
        savings_pct=0.0,
    )

    hotel = estimate_hotel_total(family=family, estimate={
        "saisonKey": pre.saison_key, "nuits": pre.nuits, "transportTotal": pre.transport_total,
    })
    pre.hotel_estimate = hotel
    pre.hotel_savings = max(0, hotel - pre.total)
    pre.savings_pct = (pre.hotel_savings / hotel * 100) if hotel > 0 else 0.0
    return pre
```

## `booking_url.py`

> Spec §3.4 + §US-2.8. URL builder lives here; the views layer in `apps/pricing/views.py`
> wraps it with the token signing flow.

```python
# apps/pricing/services/booking_url.py
from __future__ import annotations
import hmac, hashlib, json, secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.conf import settings


SAISON_TO_URL_SEGMENT = {"ete": "summer", "fetes": "winter", "vs": "winter", "hs": "summer"}


def saison_to_url_segment(saison_key: str, date_debut: str) -> str:
    month = int(date_debut[5:7])
    if saison_key in ("vs", "hs"):
        return "winter" if month in (1, 2, 3, 10, 11, 12) else "summer"
    return SAISON_TO_URL_SEGMENT.get(saison_key, "summer")


def bucket_children(enfants: list[dict]) -> dict[str, int]:
    buckets = {"nbBabies": 0, "nbChildren3": 0, "nbChildren1": 0, "nbChildren2": 0}
    for child in enfants:
        age = child["age"]
        if   age <= 1:  buckets["nbBabies"]    += 1
        elif age <= 5:  buckets["nbChildren3"] += 1
        elif age <= 11: buckets["nbChildren1"] += 1
        else:           buckets["nbChildren2"] += 1
    return buckets


def build_vtf_booking_url(*, village, family: dict, dates: dict, saison_key: str) -> str:
    """Build the pre-filled VTF booking URL. Spec §3.4."""
    base = village.vtf_base_url or (
        f"https://www.vtf-vacances.com/fr_FR/"
        f"{saison_to_url_segment(saison_key, dates['debut'])}/village-vacances/"
        f"{village.vtf_department}/{village.vtf_city}/{village.vtf_slug}"
    )
    buckets = bucket_children(family["enfants"])
    nb_persons = family["adultes"] + len(family["enfants"])
    qs = urlencode({
        "search_engine[startedAt]": dates["debut"],
        "search_engine[endedAt]":   dates["fin"],
        "search_engine[nbPersons]": nb_persons,
        "search_engine[nbAdults]":  family["adultes"],
        **{f"search_engine[{k}]": v for k, v in buckets.items()},
    })
    return f"{base}?{qs}"


def mint_token(*, village_id: str, session_id: str, payload_hash: str, ttl_hours: int = 72) -> tuple[str, datetime]:
    """
    HMAC-SHA256 signed token. NOT a JWT — small, opaque, server-verified.
    Returns (token, expires_at).
    """
    nonce = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
    body = f"{village_id}|{session_id}|{payload_hash}|{int(expires_at.timestamp())}|{nonce}"
    sig = hmac.new(
        settings.BOOKING_REDIRECT_SECRET.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    token = f"{nonce}.{int(expires_at.timestamp())}.{sig[:32]}"
    return token, expires_at


def verify_token(token: str, *, village_id: str, session_id: str, payload_hash: str) -> bool:
    """Recompute the signature and constant-time compare. False on tamper or malformed."""
    try:
        nonce, exp_str, sig_short = token.split(".", 2)
        expires_at = datetime.utcfromtimestamp(int(exp_str))
    except (ValueError, OverflowError):
        return False
    if expires_at < datetime.utcnow():
        return False
    body = f"{village_id}|{session_id}|{payload_hash}|{int(expires_at.timestamp())}|{nonce}"
    expected = hmac.new(
        settings.BOOKING_REDIRECT_SECRET.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()[:32]
    return hmac.compare_digest(expected, sig_short)


def hash_payload(payload: dict) -> str:
    """Stable hash for token integrity. Sort keys for determinism."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
```

### Service entry point used by views

```python
# apps/pricing/services/booking_redirect.py
from datetime import timedelta
from django.utils import timezone

from apps.catalog.models import Village
from apps.pricing.models import BookingRedirectToken

from .booking_url import build_vtf_booking_url, mint_token, hash_payload


class BookingRedirectService:
    @staticmethod
    def create_token(*, village: Village, session_id: str, family: dict, dates: dict, context: dict) -> str:
        """Spec §US-2.8."""
        target = build_vtf_booking_url(
            village=village, family=family, dates=dates,
            saison_key=context.get("saisonKey", "ete"),
        )
        payload = {"family": family, "dates": dates, "context": context}
        digest = hash_payload(payload)
        token, expires_at = mint_token(
            village_id=village.id, session_id=session_id, payload_hash=digest,
        )
        BookingRedirectToken.objects.create(
            token=token, village=village, session_id=session_id,
            payload=payload, target_url=target, expires_at=expires_at,
        )
        return token
```

> ⚠️ Implementations must:
> - Generate the token in **< 10 ms** (no DB writes inside `mint_token`; the token row is
>   created in a single `INSERT` afterward, called inside `transaction.on_commit` to keep
>   the calc endpoint's response time low).
> - Redirect in **< 50 ms** (the `BookingClick` write is async via `on_commit`).
> - Never raise on expired/tampered tokens — fall back to the village's generic VTF page.

## Golden-master testing

> The single most important quality gate. Without this, JS↔Python divergence will bite us in production.

### Step 1 — Capture JS outputs

Create `vtf/api/tests/golden/snapshot.cjs` (a tiny Node script):

```js
// Run from vtf/front/: node ../api/tests/golden/snapshot.cjs > ../api/tests/golden/cases.json
const { estimateSejourTotal } = require('./src/utils/stayEstimate.ts')
const { VTF_VILLAGES } = require('./src/data/vtfStay.ts')

const cases = [
  { /* family, sejour, villageId */ },
  // ... 20 cases covering: PC summer, DP shoulder, LOC family, solo+kid, qfExc, ski, etc.
]

const out = cases.map(c => ({
  input: c,
  output: estimateSejourTotal({ family: c.family, sejour: c.sejour, village: VTF_VILLAGES.find(v => v.id === c.villageId) }),
}))
console.log(JSON.stringify(out, null, 2))
```

### Step 2 — Assert in pytest

```python
# apps/pricing/tests/test_stay_estimate_golden.py
import json
import pathlib

import pytest

from apps.pricing.services.stay_estimate import estimate_sejour_total

GOLDEN = pathlib.Path(__file__).parent / "golden" / "cases.json"


@pytest.fixture(scope="module")
def cases():
    return json.loads(GOLDEN.read_text())


@pytest.fixture(scope="module")
def pricing_rules():
    return json.loads(
        (pathlib.Path(__file__).parents[3] / "front" / "src" / "mocks" / "vtfPricingRules.mock.json").read_text()
    )


@pytest.fixture(scope="module")
def villages():
    payload = json.loads(
        (pathlib.Path(__file__).parents[3] / "front" / "src" / "mocks" / "vtfStay.mock.json").read_text()
    )
    return {v["id"]: v for v in payload["villages"]}


def test_golden(cases, pricing_rules, villages):
    for case in cases:
        v = villages[case["input"]["villageId"]]
        actual = estimate_sejour_total(
            family=case["input"]["family"],
            sejour=case["input"]["sejour"],
            village=v,
            pricing_rules=pricing_rules,
        )
        expected = case["output"]
        assert actual is not None
        assert actual.total == expected["total"], f"{case['input']}"
        assert actual.saison_key == expected["saisonKey"]
        assert actual.nuits == expected["nuits"]
        # ... more fields
```
