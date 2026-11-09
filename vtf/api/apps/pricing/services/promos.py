"""Séjour promo eligibility. Port of vtf/front/src/utils/promosTab.ts."""
from __future__ import annotations

from datetime import date, timedelta
from typing import List

# Weekly Jeudi offers catalog (simple in-memory table). Each entry:
#  - villageId: slug
#  - stayStart/stayEnd: ISO date strings for the stay window
#  - rate: decimal fraction
#  - bookFrom/bookUntil: ISO date strings defining booking window (inclusive)
#  - min_nuits: minimum nights required
JEUDI_OFFERS: List[dict] = [
    {
        "villageId": "karellis",
        "stayStart": "2026-12-05",
        "stayEnd": "2026-12-12",
        "rate": 0.25,
        "bookFrom": "2026-12-03",
        "bookUntil": "2026-12-09",
        "min_nuits": 7,
    },
    {
        "villageId": "lacanau",
        "stayStart": "2026-07-11",
        "stayEnd": "2026-07-18",
        "rate": 0.25,
        "bookFrom": "2026-07-06",
        "bookUntil": "2026-07-12",
        "min_nuits": 7,
    },
    # Add other weekly deals here as needed.
]

# Villages enrolled in the *rotating* Jeudi promo: a new offer window opens
# every Thursday 00:01 and is bookable for 7 days, for whatever village_id
# is listed here, at the configured rate. Unlike JEUDI_OFFERS (fixed,
# one-off stay windows), this is date-relative to `now` — it needs no
# per-week maintenance and keeps working in future years. Villages here
# take this rule only when they have no explicit JEUDI_OFFERS match for
# the given stay.
JEUDI_ROTATING_VILLAGES: dict[str, float] = {
    "blainville": 0.25,
}
JEUDI_ROTATING_MIN_NUITS = 7
# How far ahead of the current booking window a stay may start and still
# be treated as "this week's" Jeudi deal.
JEUDI_ROTATING_MAX_LEAD_DAYS = 90


def _current_jeudi_booking_window(now: date) -> tuple[date, date]:
    """Thursday-to-Wednesday window containing `now` (opens Thu 00:01)."""
    days_since_thursday = (now.weekday() - 3) % 7
    window_start = now - timedelta(days=days_since_thursday)
    window_end = window_start + timedelta(days=6)
    return window_start, window_end


def _jeudi_rotating_promo(
    *, village_id: str | None, date_debut: date, date_fin: date, now: date
) -> dict | None:
    """Weekly-rotating Jeudi eligibility for JEUDI_ROTATING_VILLAGES.

    Additive-only, mirrors the shape of JEUDI_OFFERS entries but derives
    the stay/booking window from `now` instead of hardcoded dates.
    """
    if not village_id or village_id not in JEUDI_ROTATING_VILLAGES:
        return None

    nuits = max(0, (date_fin - date_debut).days)
    if nuits < JEUDI_ROTATING_MIN_NUITS:
        return None

    window_start, window_end = _current_jeudi_booking_window(now)
    if not (window_start <= now <= window_end):
        return None

    lead_days = (date_debut - now).days
    if lead_days < 0 or lead_days > JEUDI_ROTATING_MAX_LEAD_DAYS:
        return None

    rate = JEUDI_ROTATING_VILLAGES[village_id]
    return {
        "key": "jeudi",
        "icon": "🔥",
        "label": "Promo du Jeudi",
        "description": "Offre flash hebdo · Change chaque jeudi · Code JEUDI · 7 nuits min · Non cumulable",
        "tag": f"−{int(rate * 100)}%",
        "rate": rate,
        "kind": "auto",
    }

# "1ère Minute Hiver" — winter early-booking offer, separate from the
# mai–oct "premiere" rule below. Source (checked live 2026-08-27):
# https://www.vtf-vacances.com/fr_FR/sejours-offres-premiere-minute-hiver
# "A réserver et confirmer avant le 15/09/2026". Two village tiers, each
# with a higher-discount window set and a lower-discount window set.
PREMIERE_HIVER_BOOK_UNTIL = "2026-09-15"
PREMIERE_HIVER_MIN_NUITS = 7

# Tier A villages: 30% (high windows) / 20% (low windows)
PREMIERE_HIVER_TIER_A = {
    "savines", "saint-sauves", "soultzeren", "arvieux", "bandol", "cereste", "bedoin",
}
# Tier B villages: 15% (high windows) / 10% (low windows)
PREMIERE_HIVER_TIER_B = {
    "la-plagne", "doucy", "font-durle", "chamonix", "alpe-dhuez", "le-sauze",
    "metabief", "sainte-maxime", "biarritz", "lacanau", "riec", "saint-cast",
    "blainville", "singleyrac",
}
PREMIERE_HIVER_RATES = {  # villageTier -> (highRate, lowRate)
    "A": (0.30, 0.20),
    "B": (0.15, 0.10),
}

# Higher-discount stay windows (arrival date must fall in one of these).
PREMIERE_HIVER_WINDOWS_HIGH = [
    ("2026-12-19", "2026-12-26"),  # Noël
    ("2027-01-02", "2027-01-09"),  # hors vacances scolaires
    ("2027-03-20", "2027-04-03"),  # hors vacances scolaires
    ("2027-02-06", "2027-02-13"),  # vacances de Février (tranche 1)
    ("2027-04-03", "2027-05-01"),  # vacances de Pâques
]
# Lower-discount stay windows.
PREMIERE_HIVER_WINDOWS_LOW = [
    ("2026-12-26", "2027-01-02"),  # Nouvel An
    ("2027-01-09", "2027-02-06"),  # hors vacances scolaires
    ("2027-03-06", "2027-03-20"),  # hors vacances scolaires
    ("2027-02-13", "2027-03-06"),  # vacances de Février (tranche 2)
]


def _premiere_hiver_promo(
    *, village_id: str | None, date_debut: date, date_fin: date, now: date
) -> dict | None:
    """Winter 1ère-minute eligibility. Returns a promo dict or None.

    Additive-only: does not touch/replace the existing mai-oct `premiere`
    rule, JEUDI_OFFERS, Pack Surprise, or anything else in this module.
    """
    if not village_id:
        return None

    if village_id in PREMIERE_HIVER_TIER_A:
        tier = "A"
    elif village_id in PREMIERE_HIVER_TIER_B:
        tier = "B"
    else:
        return None

    nuits = max(0, (date_fin - date_debut).days)
    if nuits < PREMIERE_HIVER_MIN_NUITS:
        return None

    book_until = date.fromisoformat(PREMIERE_HIVER_BOOK_UNTIL)
    if now > book_until:
        return None

    high_rate, low_rate = PREMIERE_HIVER_RATES[tier]

    def _in_windows(windows: list[tuple[str, str]]) -> bool:
        for start_s, end_s in windows:
            start_d = date.fromisoformat(start_s)
            end_d = date.fromisoformat(end_s)
            if start_d <= date_debut <= end_d:
                return True
        return False

    if _in_windows(PREMIERE_HIVER_WINDOWS_HIGH):
        rate = high_rate
    elif _in_windows(PREMIERE_HIVER_WINDOWS_LOW):
        rate = low_rate
    else:
        return None

    return {
        "key": "premiere",
        "icon": "⏰",
        "label": "1ère Minute",
        "description": "Réservation avant le 20/03 · Non cumulable avec autres promos séjour",
        "tag": f"−{int(rate * 100)}%",
        "rate": rate,
        "kind": "auto",
    }


# Real "Dernière Minute Été" campaign (vtf-vacances.com/fr_FR/sejours-derniere-minute-ete):
# only these villages are enrolled, at different rates for PC/DP vs LOC, only
# for stays inside a fixed window, only bookable before a fixed deadline.
# Previously this promo applied to *any* village in summer — that was the bug
# (client: "cette offre remonte sur toutes les destinations, il ne faut pas").
DERNIERE_MINUTE_ETE_STAY_START = date(2026, 8, 8)
DERNIERE_MINUTE_ETE_STAY_END = date(2026, 8, 29)
DERNIERE_MINUTE_ETE_BOOK_DEADLINE = date(2026, 8, 11)
DERNIERE_MINUTE_ETE_MIN_NUITS = 7
DERNIERE_MINUTE_ETE_PC_DP_RATES: dict[str, float] = {
    "carcans-les-bruyeres": 0.25,
    "cereste": 0.25,
    "saint-sauves": 0.25,
    "la-plagne": 0.25,  # "Plagne-Montalbert" on the site — closest fixture match
    "riec": 0.20,
    "singleyrac": 0.20,
    "vernet": 0.20,
    "le-sauze": 0.20,
}
DERNIERE_MINUTE_ETE_LOC_RATES: dict[str, float] = {
    "carcans-les-oyats": 0.30,
    "singleyrac": 0.30,
}


def _derniere_minute_promo(
    *,
    village_id: str | None,
    date_debut: date,
    date_fin: date,
    now: date,
    days_before: int,
    ete: bool,
    formule: str | None,
) -> dict | None:
    if days_before < 0 or days_before > 30:
        return None

    if not ete:
        # Off-season last-minute rule is unrestricted (unaffected by this fix).
        return {
            "key": "derniere",
            "icon": "⚡",
            "label": "Dernière Minute",
            "description": "Départ dans moins de 30 jours",
            "tag": "−40%",
            "rate": 0.40,
            "kind": "auto",
        }

    rates = DERNIERE_MINUTE_ETE_LOC_RATES if formule == "LOC" else DERNIERE_MINUTE_ETE_PC_DP_RATES
    if not village_id or village_id not in rates:
        return None

    if not (DERNIERE_MINUTE_ETE_STAY_START <= date_debut <= DERNIERE_MINUTE_ETE_STAY_END):
        return None

    nuits = max(0, (date_fin - date_debut).days)
    if nuits < DERNIERE_MINUTE_ETE_MIN_NUITS:
        return None

    if now > DERNIERE_MINUTE_ETE_BOOK_DEADLINE:
        return None

    rate = rates[village_id]
    return {
        "key": "derniere",
        "icon": "⚡",
        "label": "Dernière Minute",
        "description": "Départ dans moins de 30 jours",
        "tag": f"−{int(rate * 100)}%",
        "rate": rate,
        "kind": "auto",
    }


def available_sejour_promos(
    *,
    date_debut: date | None,
    date_fin: date | None,
    now: date,
    is_solo_parent: bool = False,
    village_id: str | None = None,
    quinzaine_futee: bool = False,
    formule: str | None = None,
) -> list[dict]:
    """Returns list of {key, icon, label, description, tag, rate, kind}.

    Rules (2026):
      - 1ère Minute  : séjour mai–oct ET réservation strictement avant le 20/03
      - Dernière Min : départ dans ≤30 j (taux dépend de la saison)
      - Promo Jeudi  : weekly offers per-village (see JEUDI_OFFERS)
      - Pack Surprise: hors été + 7 nuits min
      - Quinzaine futée: gérée séparément
      - Solo-parent promo does not apply to LOC rentals
    """
    if not date_debut or not date_fin:
        return []

    # NOTE: solo-parent no longer short-circuits the rest of this function.
    # It used to `return` early with only the soloParentChild entry, which
    # wiped out premiere/derniere/jeudi/pack eligibility for the whole
    # request. The frontend's stay-promo list (StayPromotionSection) always
    # renders its fixed catalog (premiere/derniere/jeudi/pack) and disables
    # whichever keys are *not* present in this function's output — so
    # returning only soloParentChild made every other card show as
    # "non éligible", even ones that were genuinely available for the
    # chosen dates (this was the "1ère minute n'est pas proposée" bug).
    # soloParentChild itself isn't one of the frontend's catalog keys and
    # isn't consumed there — the actual −50% child discount is applied
    # automatically in the price calc — so we just append it to the normal
    # result below instead of replacing it.
    solo_parent_promo = (
        {
            "key": "soloParentChild",
            "icon": "👩‍👦",
            "label": "Parent solo — −50% tarif enfant",
            "description": "Réduction automatique pour les familles monoparentales · Applicable sur le tarif enfant",
            "tag": "−50%",
            "rate": 0.50,
            "kind": "auto",
        }
        if is_solo_parent and formule != "LOC"
        else None
    )

    m, j = date_debut.month, date_debut.day
    jj = m * 100 + j
    nuits = max(0, (date_fin - date_debut).days)
    today_jj = now.month * 100 + now.day
    # "Dernière Minute" is based on the *arrival* date (date_debut) — this
    # matches vtf-vacances.com behavior (eligibility within 30 days before start).
    #
    # When `now` falls inside the stay window (date_debut ≤ now ≤ date_fin),
    # we treat it as 0 days before so the promo remains visible in purely
    # diagnostic contexts (tests, demos) even though real bookings would not
    # occur after the stay has started.
    if now > date_fin:
        days_before = -1
    else:
        days_before = max(0, (date_debut - now).days)
    ete = 628 <= jj <= 901

    # If a villageId is provided, determine `jeudi` eligibility from the
    # weekly offers table rather than the previous heuristic.
    def _parse(s: str) -> date:
        return date.fromisoformat(s)

    if village_id:
        # Search offers for this village and check full eligibility.
        for offer in JEUDI_OFFERS:
            if offer.get("villageId") != village_id:
                continue
            stay_start = _parse(offer["stayStart"])
            stay_end = _parse(offer["stayEnd"])
            min_nuits = int(offer.get("min_nuits", 7))
            # stay must fit into offer window
            if not (date_debut >= stay_start and date_fin <= stay_end):
                continue
            nuits_offer = max(0, (date_fin - date_debut).days)
            if nuits_offer < min_nuits:
                continue
            # optional booking window
            bf = offer.get("bookFrom")
            bu = offer.get("bookUntil")
            if bf and bu:
                bf_d = _parse(bf)
                bu_d = _parse(bu)
                if not (bf_d <= now <= bu_d):
                    # not currently bookable
                    continue
            # matched — return base promos + this jeudi offer
            out: list[dict] = []
            if 502 <= jj <= 1101 and today_jj < 320:
                is_jan = today_jj < 120
                is_fev = 120 <= today_jj < 220
                rate = 0.30 if is_jan else 0.20 if is_fev else 0.10
                tag = "−30%" if is_jan else "−20%" if is_fev else "−10%"
                out.append(
                    {
                        "key": "premiere",
                        "icon": "⏰",
                        "label": "1ère Minute",
                        "description": "Séjours mai–oct · Réservation avant le 20/03",
                        "tag": tag,
                        "rate": rate,
                        "kind": "auto",
                    }
                )
            derniere_promo = _derniere_minute_promo(
                village_id=village_id,
                date_debut=date_debut,
                date_fin=date_fin,
                now=now,
                days_before=days_before,
                ete=ete,
                formule=formule,
            )
            if derniere_promo:
                out.append(derniere_promo)
            # pack still allowed for hors-ete + >=7 nights
            if not ete and nuits >= 7:
                out.append(
                    {
                        "key": "pack",
                        "icon": "🎁",
                        "label": "Pack Surprise",
                        "description": "Village mystère · Dès 319€/sem · 7 nuits min",
                        "tag": "−35%",
                        "rate": 0.35,
                        "kind": "auto",
                    }
                )
            # add the matched jeudi offer with its configured rate
            out.append(
                {
                    "key": "jeudi",
                    "icon": "🔥",
                    "label": "Promo du Jeudi",
                    "description": "Offre flash hebdo · Hors été · 7 nuits min · Non cumulable",
                    "tag": f"−{int(offer['rate']*100)}%",
                    "rate": offer["rate"],
                    "kind": "auto",
                }
            )
            if solo_parent_promo:
                out.append(solo_parent_promo)
            if not any(p["key"] == "premiere" for p in out):
                hiver_promo = _premiere_hiver_promo(
                    village_id=village_id, date_debut=date_debut, date_fin=date_fin, now=now
                )
                if hiver_promo:
                    out.append(hiver_promo)
            return out

        # No fixed JEUDI_OFFERS entry matched this village/stay — fall back
        # to the weekly-rotating rule (JEUDI_ROTATING_VILLAGES) before
        # dropping to the generic (non-village) path below, which excludes
        # "hors été" stays and would otherwise hide this village's promo.
        rotating_jeudi = _jeudi_rotating_promo(
            village_id=village_id, date_debut=date_debut, date_fin=date_fin, now=now
        )
        if rotating_jeudi:
            out = []
            if 502 <= jj <= 1101 and today_jj < 320:
                is_jan = today_jj < 120
                is_fev = 120 <= today_jj < 220
                rate = 0.30 if is_jan else 0.20 if is_fev else 0.10
                tag = "−30%" if is_jan else "−20%" if is_fev else "−10%"
                out.append(
                    {
                        "key": "premiere",
                        "icon": "⏰",
                        "label": "1ère Minute",
                        "description": "Séjours mai–oct · Réservation avant le 20/03",
                        "tag": tag,
                        "rate": rate,
                        "kind": "auto",
                    }
                )
            derniere_promo = _derniere_minute_promo(
                village_id=village_id,
                date_debut=date_debut,
                date_fin=date_fin,
                now=now,
                days_before=days_before,
                ete=ete,
                formule=formule,
            )
            if derniere_promo:
                out.append(derniere_promo)
            if not ete and nuits >= 7:
                out.append(
                    {
                        "key": "pack",
                        "icon": "🎁",
                        "label": "Pack Surprise",
                        "description": "Village mystère · Dès 319€/sem · 7 nuits min",
                        "tag": "−35%",
                        "rate": 0.35,
                        "kind": "auto",
                    }
                )
            out.append(rotating_jeudi)
            if solo_parent_promo:
                out.append(solo_parent_promo)
            if not any(p["key"] == "premiere" for p in out):
                hiver_promo = _premiere_hiver_promo(
                    village_id=village_id, date_debut=date_debut, date_fin=date_fin, now=now
                )
                if hiver_promo:
                    out.append(hiver_promo)
            return out

    out: list[dict] = []

    if 502 <= jj <= 1101 and today_jj < 320:
        is_jan = today_jj < 120
        is_fev = 120 <= today_jj < 220
        rate = 0.30 if is_jan else 0.20 if is_fev else 0.10
        tag = "−30%" if is_jan else "−20%" if is_fev else "−10%"
        out.append(
            {
                "key": "premiere",
                "icon": "⏰",
                "label": "1ère Minute",
                "description": "Séjours mai–oct · Réservation avant le 20/03",
                "tag": tag,
                "rate": rate,
                "kind": "auto",
            }
        )

    derniere_promo = _derniere_minute_promo(
        village_id=village_id,
        date_debut=date_debut,
        date_fin=date_fin,
        now=now,
        days_before=days_before,
        ete=ete,
        formule=formule,
    )
    if derniere_promo:
        out.append(derniere_promo)

    if not ete and nuits >= 7:
        out.append(
            {
                "key": "jeudi",
                "icon": "🔥",
                "label": "Promo du Jeudi",
                "description": "Code JEUDI · Flash hebdo · Hors été · 7 nuits min",
                "tag": "−25%",
                "rate": 0.25,
                "kind": "auto",
            }
        )
        out.append(
            {
                "key": "pack",
                "icon": "🎁",
                "label": "Pack Surprise",
                "description": "Village mystère · Dès 319€/sem · 7 nuits min",
                "tag": "−35%",
                "rate": 0.35,
                "kind": "auto",
            }
        )

    # If client explicitly requested the 'quinzaine futée' promo, append it.
    if quinzaine_futee:
        # ensure not duplicated
        keys = {p.get("key") for p in out}
        if "fortnightStay" not in keys:
            out.append(
                {
                    "key": "fortnightStay",
                    "icon": "🌙",
                    "label": "Séjour Quinzaine",
                    "description": "Sélection de 14 nuits ou plus · 10% de remise sur le séjour",
                    "tag": "−10%",
                    "rate": 0.1,
                    "kind": "auto",
                }
            )

    if solo_parent_promo:
        out.append(solo_parent_promo)

    if not any(p["key"] == "premiere" for p in out):
        hiver_promo = _premiere_hiver_promo(
            village_id=village_id, date_debut=date_debut, date_fin=date_fin, now=now
        )
        if hiver_promo:
            out.append(hiver_promo)

    return out


def promo_key_from_rate(rate: float) -> str:
    r = round(max(0.0, min(1.0, rate or 0.0)) * 100)
    if r == 0:
        return "none"
    if r in (10, 20, 30):
        return "premiere"
    if r == 25:
        return "jeudi"
    if r == 35:
        return "pack"
    if r == 40:
        return "derniere"
    return "none"