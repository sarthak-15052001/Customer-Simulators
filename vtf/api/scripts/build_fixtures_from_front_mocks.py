#!/usr/bin/env python3
"""Build Django loaddata fixtures from the frontend mocks + hardcoded TS data.

This is the canonical seed for `python manage.py loaddata <fixture>` until the
`load_vtf_mocks` management command lands (Milestone 1, doc 09). Re-run after
editing any of the source files.

Inputs (read-only):
  vtf/front/src/mocks/vtfStay.mock.json
  vtf/front/src/mocks/vtfExtras.mock.json
  vtf/front/src/mocks/vtfPricingRules.mock.json
  vtf/front/src/data/vtfPromos.ts        # parsed via known constants
  vtf/front/src/data/vtfResto.ts
  vtf/front/src/data/vtfTransport.ts

Outputs (overwritten):
  vtf/api/apps/catalog/fixtures/villages.json
  vtf/api/apps/catalog/fixtures/activities.json
  vtf/api/apps/catalog/fixtures/pricing_rules.json
  vtf/api/apps/catalog/fixtures/meals.json
  vtf/api/apps/catalog/fixtures/fuel_options.json
  vtf/api/apps/catalog/fixtures/promos.json

Discrepancies handled (per docs/01-frontend-source-of-truth.md):
  - `env` emoji → `env_code` enum (kept side-by-side).
  - `attractionsProches` re-keyed from village `nom` to `village_id`.
  - Free activities → added all seasons: ["hs", "vs", "ete", "fetes"].
"""
from __future__ import annotations

import json
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
FRONT_DIR = API_DIR.parent / "front"
MOCKS = FRONT_DIR / "src" / "mocks"
FIXTURES = API_DIR / "apps" / "catalog" / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)


ENV_EMOJI_TO_CODE = {
    "🌊": "sea",
    "☀️": "sun",
    "⛰️": "mountain",
    "🌲": "forest",
    "🌻": "countryside",
}


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_fixture(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"  wrote {len(rows):3d} row(s) → {path.relative_to(API_DIR)}")


def build_villages_fixture(stay: dict) -> list[dict]:
    villages = stay["villages"]
    nom_to_id = {v["nom"]: v["id"] for v in villages}

    rows: list[dict] = []
    for v in villages:
        env_emoji = v["env"]
        env_code = ENV_EMOJI_TO_CODE.get(env_emoji)
        if env_code is None:
            raise ValueError(f"Unknown env emoji {env_emoji!r} for {v['id']}")
        rows.append(
            {
                "model": "catalog.village",
                "pk": v["id"],
                "fields": {
                    "nom": v["nom"],
                    "nom2": v.get("nom2", ""),
                    "region": v["region"],
                    "env_emoji": env_emoji,
                    "env_code": env_code,
                    "formules": v["formules"],
                    "has_loc": bool(v.get("hasLoc", False)),
                    "ski": bool(v.get("ski", False)),
                    "ouverture": v.get("ouverture", ""),
                    "tarifs": v["tarifs"],
                    "bebe_club": bool(v.get("bebeClub", False)),
                    "forfait_rm": bool(v.get("forfaitRM", False)),
                    "qf_exc": bool(v.get("qfExc", False)),
                    "enf_solo_half": bool(v.get("enfSoloHalf", False)),
                    "vtf_department": "",
                    "vtf_city": "",
                    "vtf_slug": "",
                    "vtf_url_verified_at": None,
                },
            }
        )

    # Attractions — re-key from `nom` to `village_id`.
    attr_pk = 0
    for nom, attractions in stay.get("attractionsProches", {}).items():
        if nom not in nom_to_id:
            raise KeyError(
                f"attractionsProches key {nom!r} has no matching village `nom` "
                "in vtfStay.mock.json — fix the mock or the lookup table."
            )
        village_id = nom_to_id[nom]
        for a in attractions:
            attr_pk += 1
            rows.append(
                {
                    "model": "catalog.attraction",
                    "pk": attr_pk,
                    "fields": {
                        "village": village_id,
                        "nom": a["nom"],
                        "type": a["type"],
                        "icon": a["icon"],
                        "km": int(a["km"]),
                    },
                }
            )

    return rows


def build_extras_rows(extras: dict, nom_to_id: dict[str, str]) -> list[dict]:
    rows: list[dict] = []

    # Activities — free.
    act_pk = 0
    for region, items in extras.get("actGratuit", {}).items():
        for it in items:
            act_pk += 1
            rows.append(
                {
                    "model": "catalog.activity",
                    "pk": act_pk,
                    "fields": {
                        "code": it["id"],
                        "region": region,
                        "kind": "free",
                        "nom": it["nom"],
                        "type": it["type"],
                        "price_adult": 0,
                        "price_child": 0,
                        "saisons": list(it.get("saisons", ["hs", "vs", "ete", "fetes"])),
                    },
                }
            )

    # Activities — paid.
    for region, items in extras.get("activitesPayantes", {}).items():
        for it in items:
            act_pk += 1
            rows.append(
                {
                    "model": "catalog.activity",
                    "pk": act_pk,
                    "fields": {
                        "code": it["id"],
                        "region": region,
                        "kind": "paid",
                        "nom": it["nom"],
                        "type": it["type"],
                        "price_adult": int(it.get("ad", 0)),
                        "price_child": int(it.get("enf", 0)),
                        "saisons": list(it.get("saisons", [])),
                    },
                }
            )

    # Animations.
    for i, anim in enumerate(extras.get("vtfAnimations", []), start=1):
        rows.append(
            {
                "model": "catalog.animation",
                "pk": i,
                "fields": {
                    "nom": anim["nom"],
                    "note": anim["note"],
                    "order": i - 1,
                },
            }
        )

    # VillageInfra (sparse — keyed by village id directly).
    infra_pk = 0
    for village_id, infra in extras.get("vtfInfra", {}).items():
        infra_pk += 1
        anim = infra.get("anim", {}) or {}
        ex = infra.get("extras", {}) or {}
        rows.append(
            {
                "model": "catalog.villageinfra",
                "pk": infra_pk,
                "fields": {
                    "village": village_id,
                    "infra": list(infra.get("infra", [])),
                    "anim_ete": list(anim.get("ete", [])),
                    "anim_hiver": list(anim.get("hiver", [])),
                    "anim_hs": list(anim.get("hs", [])),
                    "extras_ete": ex.get("ete", "") or "",
                    "extras_hiver": ex.get("hiver", "") or "",
                },
            }
        )

    # VillageClubsEte.
    clubs_pk = 0
    for village_id, clubs in extras.get("vtfClubsEte", {}).items():
        clubs_pk += 1
        rows.append(
            {
                "model": "catalog.villageclubsete",
                "pk": clubs_pk,
                "fields": {
                    "village": village_id,
                    "paques": clubs.get("paques", {}),
                    "ete": clubs.get("ete", {}),
                    "toussaint": clubs.get("toussaint", {}),
                },
            }
        )

    return rows


# Hardcoded TS sources (small, change rarely — see docs/01).
MEALS = [
    ("pique", "🧺 Pique-nique", 8, 5),
    ("snack", "🍔 Snack", 14, 9),
    ("bistrot", "🍽️ Bistrot", 24, 14),
    ("gastro", "🥂 Gastro", 48, 25),
]

FUELS = [
    ("essence", "Essence", "0.12"),
    ("diesel", "Diesel", "0.09"),
    ("electrique", "Électrique", "0.04"),
]

PROMOS = [
    ("pack", "🎁", "Pack Surprise",
     "Village mystère · Non cumulable avec autres promos séjour", "−35%",
     "0.35", "auto"),
    ("premiere", "⏰", "1ère Minute",
     "Réservation avant le 20/03 · Non cumulable avec autres promos séjour",
     "jusqu'à −30%", "0.30", "auto"),
    ("jeudi", "🔥", "Promo du Jeudi",
     "Offre flash hebdo · Hors été · 7 nuits min · Non cumulable", "−25%",
     "0.25", "auto"),
    ("derniere", "⚡", "Dernière Minute",
     "Disponibilités limitées · Départ proche · Non cumulable", "−40%",
     "0.40", "auto"),
]


def build_meals_fixture() -> list[dict]:
    return [
        {
            "model": "catalog.meal",
            "pk": code,
            "fields": {
                "label": label,
                "price_adult": p_adult,
                "price_child": p_child,
                "order": i,
            },
        }
        for i, (code, label, p_adult, p_child) in enumerate(MEALS)
    ]


def build_fuels_fixture() -> list[dict]:
    return [
        {
            "model": "catalog.fueloption",
            "pk": key,
            "fields": {"label": label, "cost_per_km": cost},
        }
        for key, label, cost in FUELS
    ]


def build_promos_fixture() -> list[dict]:
    return [
        {
            "model": "catalog.promo",
            "pk": key,
            "fields": {
                "icon": icon,
                "label": label,
                "description": description,
                "tag": tag,
                "rate": rate,
                "kind": kind,
            },
        }
        for key, icon, label, description, tag, rate, kind in PROMOS
    ]


def build_pricing_rules_fixture(payload: dict) -> list[dict]:
    # `created_at` is `auto_now_add` and loaddata bypasses save(); supply it
    # explicitly so the fixture loads on a fresh DB. We anchor it to the
    # mock's `updatedAt` (midnight) — services should rely on the date-only
    # `updated_at` field for cache busting, not on `created_at`.
    return [
        {
            "model": "catalog.pricingrules",
            "pk": 1,
            "fields": {
                "updated_at": payload["updatedAt"],
                "payload": payload,
                "is_active": True,
                "created_at": f"{payload['updatedAt']}T00:00:00+00:00",
            },
        }
    ]


def main() -> None:
    print(f"[build_fixtures] reading mocks from {MOCKS.relative_to(API_DIR.parent.parent)}")
    stay = load_json(MOCKS / "vtfStay.mock.json")
    extras = load_json(MOCKS / "vtfExtras.mock.json")
    pricing = load_json(MOCKS / "vtfPricingRules.mock.json")

    nom_to_id = {v["nom"]: v["id"] for v in stay["villages"]}

    village_rows = build_villages_fixture(stay)
    write_fixture(FIXTURES / "villages.json", village_rows)

    # Doc 01 allocates everything sourced from vtfExtras.mock.json into
    # activities.json — including the per-village infra/clubs blobs.
    write_fixture(FIXTURES / "activities.json",
                  build_extras_rows(extras, nom_to_id))

    write_fixture(FIXTURES / "pricing_rules.json",
                  build_pricing_rules_fixture(pricing))
    write_fixture(FIXTURES / "meals.json", build_meals_fixture())
    write_fixture(FIXTURES / "fuel_options.json", build_fuels_fixture())
    write_fixture(FIXTURES / "promos.json", build_promos_fixture())

    print("[build_fixtures] done.")


if __name__ == "__main__":
    main()
