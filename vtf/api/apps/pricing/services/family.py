"""Family / QF helpers.

Port of vtf/front/src/utils/familyTab.ts (display-only dégressivité + QF badge).
For pricing-aware child discounts, see stay_estimate._child_discount_with_bebe_club.
"""
from __future__ import annotations

QF_SEUIL_BAS = 880
QF_SEUIL_HAUT = 1350


def child_discount_fraction(age: int) -> float:
    """Display-only dégressivité (no village context)."""
    if age < 1:
        return 1.0
    if age < 3:
        return 0.9
    if age < 6:
        return 0.4
    if age < 11:
        return 0.2
    if age < 16:
        return 0.1
    return 0.0


def qf_badge_kind(qf_val: int | None) -> str:
    if qf_val is None:
        return "empty"
    if qf_val < QF_SEUIL_BAS:
        return "r1"
    if qf_val < QF_SEUIL_HAUT:
        return "r2"
    return "plein"
