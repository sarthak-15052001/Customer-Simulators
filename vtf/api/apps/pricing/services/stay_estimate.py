"""Cœur métier — estimateSejourTotal port. See vtf/api/docs/04-services.md.

Source: vtf/front/src/utils/stayEstimate.ts. Output must match JS to the euro
on the golden master cases (AC-1.3).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from apps.tariff_scraper.models import (
    PRICING_TYPE_PER_PERSON,
    PRICING_TYPE_PER_PERSON_PER_NIGHT,
)

from ._round import jsround
from .calendar import saison_key
from apps.catalog.models import MarketingSeasons
from apps.catalog.services.marketing_seasons import rolled_season_window
from .hotel import estimate_hotel_total
from .promos import available_sejour_promos
from .resto import resto_total_amount
from .transport import car_cost_breakdown, train_total

QF_SEUIL_BAS = 880
QF_SEUIL_HAUT = 1350


@dataclass
class ChildLine:
    age: int
    discount_fraction: float
    amount: int


@dataclass
class DisplayMetrics:
    per_day_family: int
    per_person_per_day: int
    total_vtf_stay_only: int
    savings_pct: float
    discount_pct: int


@dataclass
class BudgetBreakdown:
    stay: int
    restoration: int
    transport: int
    activities: int


@dataclass
class SejourEstimate:
    total: int
    per_person: int
    total_adults: int
    total_children: int
    per_adult_base: int
    child_lines: list[ChildLine] = field(default_factory=list)
    saison_key: str = ""
    nuits: int = 0
    discount_rate: float = 0.0
    stay_subtotal: int = 0
    adhesion: int = 0
    solo_supplement: int = 0
    extras_loc: int = 0
    activities_total: int = 0
    resto_total: int = 0
    transport_total: int = 0
    hotel_estimate: int = 0
    hotel_savings: int = 0
    savings_pct: float = 0.0
    display_metrics: DisplayMetrics | None = None
    budget_breakdown: BudgetBreakdown | None = None


def _child_discount_with_bebe_club(age: int, bebe_club: bool, rules: dict) -> float:
    cd = rules["childDiscounts"]
    if age < 1:
        return cd["lt1"]
    if age < 3:
        if bebe_club:
            return cd.get("1to2_withBebeClub", cd.get("1to3_withBebeClub", 0.7))
        return cd.get("1to2_withoutBebeClub", cd.get("1to3_withoutBebeClub", 0.9))
    if age < 6:
        return cd.get("3to5", cd.get("4to5", 0.4))
    if age < 11:
        return cd["6to10"]
    if age < 16:
        return cd["11to15"]
    return cd["ge16"]


def _qf_rate(qf_val: int | None, qf_exc: bool) -> float:
    if qf_val is None:
        return 0.0
    if qf_val < QF_SEUIL_BAS:
        return 0.10 if qf_exc else 0.17
    if qf_val < QF_SEUIL_HAUT:
        return 0.05 if qf_exc else 0.10
    return 0.0


def _duration_coef(nuits: int, rules: dict, formule: str = "PC") -> float:
    """Duration coefficient for stay length.

    LOC is charged per accommodation week, so scale linearly (nuits/7).
    Board formules (PC/DP) keep the discounted durationCoefficients table.
    """
    if formule == "LOC":
        return nuits / 7
    coefs = rules.get("durationCoefficients") or {}
    exact = coefs.get(str(nuits))
    if isinstance(exact, (int, float)) and exact > 0:
        return float(exact)
    return nuits / 7


def _formula_coef(formule: str, rules: dict) -> float:
    if formule == "LOC":
        return 1.0
    coefs = rules.get("formulaCoefficients") or {}
    c = coefs.get(formule)
    return float(c) if isinstance(c, (int, float)) and c > 0 else 1.0


def _membership_fee(family: dict, rules: dict) -> int:
    m = rules.get("membership") or {"individual": 22, "familyOrCouple": 44}
    if family["adultes"] >= 2 or len(family["enfants"]) > 0:
        return m["familyOrCouple"]
    return m["individual"]


def _quinzaine_rate(sejour: dict, nuits: int, rules: dict) -> float:
    """Quinzaine futée: PC formule + ≥14 nights computed from the dates.

    Important: derive nuits from `dateDebut/dateFin`, *never* from the
    user-supplied `fNuits` field — frontends commonly omit it (defaults to
    0 in the serializer) and the discount would silently never apply.
    """
    promos = sejour.get("promos") or {}
    if not promos.get("quinzaineFutee"):
        return 0.0
    if sejour.get("formule") != "PC":
        return 0.0
    if nuits < 14:
        return 0.0
    return float(rules.get("quinzaineFuteeRate", 0.10))


def _solo_supplement(family: dict, sejour: dict, nuits: int, rules: dict) -> int:
    if family["adultes"] != 1 or len(family["enfants"]) < 1:
        return 0
    promos = sejour.get("promos") or {}
    mode = promos.get("soloSupplementMode", "default") or "default"
    per_night_map = rules.get("soloSupplementPerNight") or {}
    per_night = per_night_map.get(mode, 22)
    return max(0, per_night) * nuits


def _maxi_family_factor(family: dict, rules: dict) -> float:
    if not family.get("maxiFamily"):
        return 1.0
    if len(family["enfants"]) < 3:
        return 1.0
    rate = float(rules.get("maxiFamilyChildrenRate", 0.20))
    return 1 - max(0.0, min(1.0, rate))


def _resolve_base_tarif(
    *,
    village: dict,
    formule: str,
    stay_date: date,
    saison: str,
    pricing_rules: dict,
    unit_type: str = "",
) -> tuple[float, float, bool] | None:
    """Resolve base price + formula coefficient + whether it's a nightly rate.

    Prefer an active scraped ``VillageTarif`` covering ``stay_date``.
    Fall back to fixture ``Village.tarifs`` season buckets.

    Returns ``(base, formula_coef, is_per_night)`` or None when no usable
    price exists.

    Scraped PC/DP/LOC prices are already formula-specific, so formula_coef is
    1.0. Fixture DP still derives from PC × formulaCoefficients['DP'].
    When DP has no scrape but PC was scraped, apply the DP coefficient on
    that scraped PC price.

    ``is_per_night`` is True only for villages whose scraped pricing_type is
    per_person_per_night — à la carte villages with no weekly grid (e.g.
    Talloires, which publishes "Tarif par nuit" instead of "Séjour semaine
    ... pension complète"). The caller must multiply that base by the
    segment's night count instead of treating it as an already-weekly price.
    """
    village_id = village.get("id") or ""
    scraped = None
    scraped_pricing_type = PRICING_TYPE_PER_PERSON
    scrape_formule = formule

    if village_id:
        try:
            from apps.tariff_scraper.services.tarif_query import get_active_tarif_with_type

            resolved = get_active_tarif_with_type(village_id, formule, stay_date, unit_type=unit_type)
            if resolved is None and formule == "DP":
                resolved = get_active_tarif_with_type(village_id, "PC", stay_date, unit_type="")
                if resolved is not None:
                    scrape_formule = "PC"
            if resolved is not None:
                scraped, scraped_pricing_type = resolved
        except Exception:
            scraped = None

    if scraped is not None and scraped > 0:
        base = float(scraped)
        is_per_night = scraped_pricing_type == PRICING_TYPE_PER_PERSON_PER_NIGHT
        if formule == "DP" and scrape_formule == "PC":
            return base, _formula_coef("DP", pricing_rules), is_per_night
        return base, 1.0, is_per_night

    tarifs = village.get("tarifs") or {}
    if formule == "LOC":
        base = (tarifs.get("LOC") or {}).get(saison, 0) or 0
    else:
        base = (tarifs.get("PC") or {}).get(saison, 0) or 0
    if not base or base <= 0:
        return None
    fixture_is_per_night = (village.get("tarifUnit") or village.get("tarif_unit") or "week") == "night"
    return float(base), _formula_coef(formule, pricing_rules), fixture_is_per_night


def _resolve_scraped_child_tarif(
    *,
    village_id: str,
    formule: str,
    stay_date: date,
    age: int,
    pricing_rules: dict,
) -> tuple[float, float, bool] | None:
    """Resolve a scraped child age-band price for one date segment.

    Returns None when no approved child row covers this exact child age, keeping
    the legacy fixture discount path available as a fallback.
    """
    try:
        from apps.tariff_scraper.services.tarif_query import get_active_child_tarif_with_type

        scrape_formule = formule
        resolved = get_active_child_tarif_with_type(village_id, formule, stay_date, age)
        if resolved is None and formule == "DP":
            resolved = get_active_child_tarif_with_type(village_id, "PC", stay_date, age)
            if resolved is not None:
                scrape_formule = "PC"
        if resolved is None:
            return None

        scraped, scraped_pricing_type = resolved
        if scraped is None or scraped < 0:
            return None

        base = float(scraped)
        is_per_night = scraped_pricing_type == PRICING_TYPE_PER_PERSON_PER_NIGHT
        if formule == "DP" and scrape_formule == "PC":
            return base, _formula_coef("DP", pricing_rules), is_per_night
        return base, 1.0, is_per_night
    except Exception:
        return None


def _sum_scraped_person_tarif_for_stay(
    *,
    village_id: str,
    formule: str,
    d_start: date,
    nuits: int,
    pricing_rules: dict,
    age: int,
) -> float | None:
    """Sum one person's scraped child prices across the stay's date bands."""
    total = 0.0
    cursor = d_start
    remaining = nuits
    while remaining > 0:
        segment_nights = min(7, remaining)
        resolved = _resolve_scraped_child_tarif(
            village_id=village_id,
            formule=formule,
            stay_date=cursor,
            age=age,
            pricing_rules=pricing_rules,
        )
        if resolved is None:
            return None

        seg_base, seg_formula_c, seg_is_per_night = resolved
        if seg_is_per_night:
            total += seg_base * segment_nights * seg_formula_c
        elif segment_nights == 7:
            total += seg_base * seg_formula_c
        else:
            nightly = round(seg_base / 7)
            total += nightly * segment_nights * seg_formula_c

        cursor += timedelta(days=segment_nights)
        remaining -= segment_nights
    return total



def estimate_sejour_total(  
    *,
    family: dict,
    sejour: dict,
    village: dict,
    pricing_rules: dict,
    activities_by_region: dict[str, list[dict]] | None = None,
    meals_catalog: list[dict] | None = None,
) -> SejourEstimate | None: 
    """Port of stayEstimate.ts:estimateSejourTotal + estimateSejourWithComparison.

    Returns None if dates are missing/invalid or village has no tarif for the
    requested saison/formule.
    """
    if not sejour.get("dateDebut") or not sejour.get("dateFin"):
        return None
    d_start = date.fromisoformat(sejour["dateDebut"])
    d_end = date.fromisoformat(sejour["dateFin"])
    nuits = (d_end - d_start).days
    if nuits < 1:
        return None

    sk = saison_key(d_start)

    extras = sejour.get("extras") or {}
    unit_type = (extras.get("locUnitType") or sejour.get("unitType") or "") or ""

    # VTF quotes prices per calendar week ("Prix pour 8 jours et 7 nuits").
    # A single base-price + duration-coefficient model only works when the
    # whole stay sits inside one price band; it silently under/over-charges
    # any stay that crosses into a differently-priced week (e.g. a 14-night
    # stay spanning a season change). Walk the stay in 7-night blocks and
    # resolve + sum each block's own real weekly price instead.
    pb = 0.0
    formula_c = 1.0
    cursor = d_start
    remaining = nuits
    resolved_any = False
    while remaining > 0:
        segment_nights = min(7, remaining)
        segment_resolved = _resolve_base_tarif(
            village=village,
            formule=sejour["formule"],
            stay_date=cursor,
            saison=saison_key(cursor),
            pricing_rules=pricing_rules,
            unit_type=unit_type,
        )
        if segment_resolved is None:
            return None
        seg_base, seg_formula_c, seg_is_per_night = segment_resolved
        formula_c = seg_formula_c
        if seg_is_per_night:
            # à la carte villages (e.g. Talloires): seg_base is already a
            # nightly rate, not a weekly one — multiply by nights directly
            # instead of running it through the /7 weekly-derivation path.
            pb += seg_base * segment_nights * seg_formula_c
        elif segment_nights == 7:
            pb += seg_base * seg_formula_c
        else:
            nightly = round(seg_base / 7)
            pb += nightly * segment_nights * seg_formula_c
        resolved_any = True
        cursor += timedelta(days=segment_nights)
        remaining -= segment_nights

    if not resolved_any:
        return None

    # QF discounts apply only in summer, and selectively in winter (per rate docs).
    allow_qf = False
    if sk == "ete":
        allow_qf = True
    else:
        # For winter, allow QF only when the requested start date falls inside the
        # marketing 'hiver' window for the upcoming season and sales are open (10 June).
        try:
            hiver = MarketingSeasons.objects.filter(key="hiver").first()
            if hiver:
                cand_start, cand_end = rolled_season_window(hiver, d_start)
                # orig_start = date.fromisoformat(hiver.start_date)
                # orig_end = date.fromisoformat(hiver.end_date)
                # # shift years so the end is near d_start
                # year_offset = d_start.year - orig_end.year
                # cand_start = orig_start.replace(year=orig_start.year + year_offset)
                # cand_end = orig_end.replace(year=orig_end.year + year_offset)
                # if cand_end < d_start:
                #     cand_start = cand_start.replace(year=cand_start.year + 1)
                #     cand_end = cand_end.replace(year=cand_end.year + 1)

                # sales open date (June 10 of current year)
                sales_open = date(date.today().year, 6, 10)
                if cand_start <= d_start <= cand_end and date.today() >= sales_open:
                    allow_qf = True
        except Exception:
            allow_qf = False

    qf = _qf_rate(family.get("qfVal"), bool(village.get("qfExc"))) if allow_qf else 0.0
    promos = sejour.get("promos") or {}
    client_promo_rate = max(0.0, min(1.0, promos.get("promoSejourRate") or 0.0))

    # Use the promo rate explicitly chosen by the frontend.
    # The backend should not auto-apply the highest eligible promotion.
    promo_rate = client_promo_rate
    quinzaine = _quinzaine_rate(sejour, nuits, pricing_rules)

    # "Séjour Quinzaine" (fortnightStay) is exposed to the frontend as a
    # selectable card in "Promos séjour" (see promos.py) whenever the
    # automatic Quinzaine futée discount (`quinzaine`, above) is already
    # active for the same stay. If the user selects that card, the client
    # sends its rate back as `promoSejourRate`, which historically got
    # stacked multiplicatively on top of `quinzaine` — double-charging the
    # same 10% discount (e.g. 1-(0.9*0.9)=19% instead of 10%).
    #
    # These two are the same offer, never two different ones, so when the
    # selected promo rate matches the auto-applied quinzaine rate, treat it
    # as already accounted for instead of compounding it again.
    if quinzaine > 0 and abs(promo_rate - quinzaine) < 1e-6:
        promo_rate = 0.0

    discount_rate = 1 - (1 - qf) * (1 - promo_rate) * (1 - quinzaine)
    pb_after = pb * (1 - discount_rate)

    bebe_club = bool(village.get("bebeClub"))
    nb_adults = family["adultes"]
    enfants = family["enfants"]
    nb_children = len(enfants)

    # LOC (location/rental) tariff is per accommodation, not per person.
    # PC/DP tariffs are per person: multiply by nb_adults and apply child discounts.

    is_loc = sejour["formule"] == "LOC"
    if is_loc:
        # Per-accommodation: the tarif covers the whole unit regardless of occupants.
        total_adults = pb_after  # 1 accommodation unit
        child_lines: list[ChildLine] = []
        total_children = 0.0
    else:
        total_adults = pb_after * nb_adults
        child_factor = _maxi_family_factor(family, pricing_rules)
        child_lines: list[ChildLine] = []
        total_children = 0.0
        village_id = village.get("id") or ""
        for child in enfants:
            frac = _child_discount_with_bebe_club(child["age"], bebe_club, pricing_rules)
            child_base = None
            if village_id:
                child_base = _sum_scraped_person_tarif_for_stay(
                    village_id=village_id,
                    formule=sejour["formule"],
                    d_start=d_start,
                    nuits=nuits,
                    pricing_rules=pricing_rules,
                    age=child["age"],
                )
            if child_base is None:
                child_base = pb * (1 - frac)
            amount = child_base * (1 - discount_rate) * child_factor
            total_children += amount
            child_lines.append(
                ChildLine(age=child["age"], discount_fraction=frac, amount=jsround(amount))
            )

    solo_supp = _solo_supplement(family, sejour, nuits, pricing_rules)
    stay_subtotal = total_adults + total_children + solo_supp
    adhesion = _membership_fee(family, pricing_rules)
    adhesion = adhesion * (1 - discount_rate)

    kit_price = (pricing_rules.get("defaults") or {}).get("locKitPrice", 10)
    extras_loc = 0
    if sejour["formule"] == "LOC":
        extras = sejour.get("extras") or {}
        extras_loc = max(0, extras.get("locCleaningFee", 0) or 0) + max(
            0, extras.get("locKits", 0) or 0
        ) * kit_price

    # Activities
    extra_acts = sejour.get("extraActivities") or {}
    paid_acts = extra_acts.get("paidQtyById") or {}
    activities_total = 0
    if paid_acts and activities_by_region:
        region_acts = activities_by_region.get(village["region"], [])
        running = 0
        for a in region_acts:
            qty = paid_acts.get(a["id"], 0) or 0
            if qty <= 0:
                continue
            unit = max(0, a.get("ad", 0)) * nb_adults + max(0, a.get("enf", 0)) * nb_children
            running += qty * unit
        activities_total = jsround(running)
    else:
        acts = sejour.get("activities") or {}
        outings = max(0, acts.get("outings", 0) or 0)
        unit = max(0, acts.get("priceAdult", 0) or 0) * nb_adults + max(
            0, acts.get("priceChild", 0) or 0
        ) * nb_children
        activities_total = outings * unit

    # Resto
    resto_block = sejour.get("resto") or {}
    qty_by_meal = resto_block.get("qtyByMealId") or {}
    resto_total = 0
    if qty_by_meal and meals_catalog:
        resto_total = jsround(
            resto_total_amount(
                meals=meals_catalog,
                qty_by_meal_id=qty_by_meal,
                adults=nb_adults,
                children=nb_children,
            )
        )

    # Transport
    transport_total = 0
    transport = sejour.get("transport") or {}
    mode = transport.get("mode")
    if mode == "car":
        # Mirror JS `??`-style nullish coalescing: an explicit 0 km must stay 0.
        # Falsy-coalescing (`a or b`) here would silently rewrite 0 → 400.
        raw_distance = transport.get("distanceOneWayKm")
        distance = 400 if raw_distance is None else raw_distance
        raw_fuel = transport.get("fuel")
        fuel = "essence" if raw_fuel is None else raw_fuel
        transport_total = car_cost_breakdown(
            distance_one_way_km=distance, fuel=fuel
        )["total"]
    elif mode == "train":
        transport_total = train_total(adults=nb_adults, children=nb_children)

    total = (
        stay_subtotal + adhesion + extras_loc + activities_total + resto_total + transport_total
    )
    persons = max(1, nb_adults + nb_children)

    est = SejourEstimate(
        total=jsround(total),
        per_person=jsround(total / persons),
        total_adults=jsround(total_adults),
        total_children=jsround(total_children),
        per_adult_base=jsround(pb_after),
        child_lines=child_lines,
        saison_key=sk,
        nuits=nuits,
        discount_rate=discount_rate,
        stay_subtotal=jsround(stay_subtotal),
        adhesion=jsround(adhesion),
        solo_supplement=jsround(solo_supp),
        extras_loc=jsround(extras_loc),
        activities_total=jsround(activities_total),
        resto_total=jsround(resto_total),
        transport_total=jsround(transport_total),
    )

    hotel = estimate_hotel_total(
        family=family,
        estimate={
            "saisonKey": est.saison_key,
            "nuits": est.nuits,
            "transportTotal": est.transport_total,
        },
    )
    est.hotel_estimate = hotel
    est.hotel_savings = max(0, hotel - est.total)
    est.savings_pct = (est.hotel_savings / hotel * 100) if hotel > 0 else 0.0
    est.display_metrics = DisplayMetrics(
        per_day_family=jsround(est.total / est.nuits),
        per_person_per_day=jsround(est.per_person / est.nuits),
        total_vtf_stay_only=est.total - est.activities_total,
        savings_pct=est.savings_pct,
        discount_pct=jsround(est.discount_rate * 100),
    )
    est.budget_breakdown = BudgetBreakdown(
        stay=est.stay_subtotal + est.adhesion + est.extras_loc,
        restoration=est.resto_total,
        transport=est.transport_total,
        activities=est.activities_total,
    )
    
    return est


def estimate_to_dict(est: SejourEstimate) -> dict:
    """Convert dataclass → dict (snake_case keys). Serializer maps to camelCase."""
    return asdict(est)