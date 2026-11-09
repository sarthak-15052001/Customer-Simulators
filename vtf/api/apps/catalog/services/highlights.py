"""Village highlights (icon + label list, max 3).

Port of vtf/front/src/utils/stayTab.ts:getHighlights.
"""
from __future__ import annotations

ENV_LABELS: dict[str, str] = {
    "🌊": "Bord de mer / plage",
    "⛰️": "Cadre montagnard",
    "🌲": "Nature & forêts",
    "🌻": "Campagne / Provence",
    "☀️": "Soleil & Méditerranée",
}


def get_highlights(village) -> list[dict]:
    """Accepts either a Village ORM instance or a dict with the same fields."""
    if isinstance(village, dict):
        env = village.get("env_emoji") or village.get("env", "")
        ski = village.get("ski", False)
        bebe_club = village.get("bebe_club") or village.get("bebeClub", False)
        has_loc = village.get("has_loc") or village.get("hasLoc", False)
        forfait_rm = village.get("forfait_rm") or village.get("forfaitRM", False)
        enf_solo_half = village.get("enf_solo_half") or village.get("enfSoloHalf", False)
        qf_exc = village.get("qf_exc") or village.get("qfExc", False)
        formules = village.get("formules") or []
    else:
        env = village.env_emoji
        ski = village.ski
        bebe_club = village.bebe_club
        has_loc = village.has_loc
        forfait_rm = village.forfait_rm
        enf_solo_half = village.enf_solo_half
        qf_exc = village.qf_exc
        formules = village.formules or []

    hl: list[dict] = []
    if env in ENV_LABELS:
        hl.append({"icon": env, "txt": ENV_LABELS[env]})
    if ski:
        hl.append({"icon": "⛷️", "txt": "Ski à proximité immédiate"})
    if bebe_club:
        hl.append({"icon": "👶", "txt": "Club bébé dès 4 mois"})
    if has_loc:
        hl.append({"icon": "🏡", "txt": "Locations & chambres disponibles"})
    if forfait_rm:
        hl.append({"icon": "🎿", "txt": "Forfait remonte-pentes inclus"})
    if enf_solo_half:
        hl.append({"icon": "💛", "txt": "Enfants -50% parent solo (été)"})
    if qf_exc:
        hl.append({"icon": "🏅", "txt": "Tarif exclusif QF"})
    if "LOC" in formules and "PC" in formules:
        hl.append({"icon": "🍽️", "txt": "PC, DP ou location au choix"})
    return hl[:3]
