# """JS-compatible rounding helper.

# JS `Math.round` rounds half toward +∞ (so Math.round(2.5)=3, Math.round(-2.5)=-2).
# Python's built-in `round()` is banker's rounding. Use `jsround` everywhere a
# TS source called `Math.round` so JS↔Python parity holds to the euro.
# """
# from __future__ import annotations

# import math


# def jsround(x: float) -> int:
#     return int(math.floor(x + 0.5))




"""JS-compatible rounding helper.

JS `Math.round` rounds half toward +∞ (so Math.round(2.5)=3, Math.round(-2.5)=-2).
Python's built-in `round()` is banker's rounding. Use `jsround` everywhere a
TS source called `Math.round` so JS↔Python parity holds to the euro.

jsround is canonical in common/utils.py — re-exported here so all existing
callers (stay_estimate, transport, qf, hotel) keep working unchanged.
"""
from common.utils import jsround  # noqa: F401  re-export

__all__ = ["jsround"]
