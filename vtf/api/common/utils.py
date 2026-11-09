"""Shared pure utility functions for the VTF API.

All functions are import-safe from any app (no Django model imports).

Key functions:
    clamp(value, min_val, max_val)    — clamp a number to [min_val, max_val]
    jsround(x)                        — JS Math.round()-compatible rounding (half-up, not banker's)
    parse_iso_date(s)                 — parse YYYY-MM-DD string to date, or None
    diff_nuits(date_debut, date_fin)  — number of nights between two dates
    date_to_saison_idx(d)             — 0=hs, 1=vs, 2=ete, 3=fetes
    saison_key_from_date(d)           — "hs" | "vs" | "ete" | "fetes"
    get_client_ip(request)            — extract real client IP from request
    hash_ip(ip)                       — salted SHA-256 hash of an IP address
    get_session_id(request, meta)     — extract/truncate request session ID
"""
from __future__ import annotations

import hashlib
import math
from datetime import date
from typing import Any

from django.conf import settings

# ─── Numeric helpers ──────────────────────────────────────────────────────

def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp *value* into the inclusive range [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def jsround(x: float) -> int:
    """JS Math.round() semantics: half-up (0.5 rounds towards +∞).

    Python's built-in round() uses banker's rounding (half-to-even), which
    diverges from the JS golden master on .5 boundaries. This function
    replicates the JS behaviour so pricing calculations match exactly.

    Examples:
        jsround(0.5)  → 1   (Python round(0.5) → 0)
        jsround(1.5)  → 2   (Python round(1.5) → 2, same)
        jsround(2.5)  → 3   (Python round(2.5) → 2)
        jsround(-0.5) → 0   (JS: Math.round(-0.5) = 0, not -1)
    """
    return math.floor(x + 0.5)


# ─── Date helpers ─────────────────────────────────────────────────────────

def parse_iso_date(s: str | None) -> date | None:
    """Parse an ISO-8601 date string (YYYY-MM-DD) into a `date` object.

    Returns None if the string is missing or malformed.
    """
    if not s:
        return None
    try:
        return date.fromisoformat(str(s))
    except (ValueError, TypeError):
        return None


def diff_nuits(date_debut: date | None, date_fin: date | None) -> int | None:
    """Return the number of nights between *date_debut* and *date_fin*.

    Returns None if either date is missing. Negative values are possible if
    the dates are reversed — callers should validate before using.
    """
    if not date_debut or not date_fin:
        return None
    return (date_fin - date_debut).days


# ─── Season helpers ───────────────────────────────────────────────────────

_SAISON_KEYS: list[str] = ["hs", "vs", "ete", "fetes"]


def date_to_saison_idx(d: date | None) -> int:
    """Map a date to a saison index: 0=hs, 1=vs, 2=ete, 3=fetes.

    Port of stayTab.ts:dateToSaisonIdx. Identical logic so pricing services
    produce the same season buckets as the frontend.
    """
    if d is None:
        return 2  # default to ete
    m, j = d.month, d.day
    jj = m * 100 + j
    # Treat June 20 (620) and later as summer (`ete`) to match frontend expectations
    # and allow mid-June stays (e.g. 20 June) to be considered summer.
    if 620 <= jj <= 901:
        return 2  # ete: 28 June – 1 Sept
    if jj >= 1220 or jj <= 106:
        return 3  # fetes: 20 Dec – 6 Jan
    # Vacances scolaires windows (winter + spring)
    if (m == 2 and j >= 15) or (m == 3 and j <= 3):
        return 1
    if (m == 4 and j >= 12) or (m == 5 and j <= 4):
        return 1
    if (m == 10 and j >= 19) or (m == 11 and j <= 2):
        return 1
    return 0  # hs


def saison_key_from_date(d: date | None) -> str:
    """Return the saison key string ("hs" | "vs" | "ete" | "fetes") for a date."""
    return _SAISON_KEYS[date_to_saison_idx(d)]


# ─── Network helpers ──────────────────────────────────────────────────────

def get_client_ip(request: Any) -> str:
    """Extract the real client IP from a Django request.

    Respects X-Forwarded-For for proxied environments (production behind
    nginx / load balancer). Falls back to REMOTE_ADDR.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded_for:
        # Take the first IP (leftmost = original client)
        return x_forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def hash_ip(ip: str) -> str:
    """Return a salted SHA-256 hash for an IP address."""
    if not ip:
        return ""
    salt = getattr(settings, "SECRET_IP_SALT", "")
    return hashlib.sha256(f"{salt}|{ip}".encode()).hexdigest()


def get_session_id(request: Any, fallback_meta: dict | None = None) -> str:
    """Extract X-Session-ID, falling back to sessionId in request metadata."""
    sid = request.headers.get("X-Session-ID") or ""
    if sid:
        return sid[:64]
    if fallback_meta:
        return (fallback_meta.get("sessionId") or "")[:64]
    return ""
