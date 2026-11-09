"""VTF booking URL builder + signed token mint/verify. Spec §3.4 + §US-2.8."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from django.conf import settings


def saison_to_url_segment(saison_key: str, date_debut: str) -> str:
    """`summer` for ete + warm-month vs/hs ; `winter` for fetes + cold-month vs/hs."""
    if saison_key == "ete":
        return "summer"
    if saison_key == "fetes":
        return "winter"
    month = int(date_debut[5:7])
    return "winter" if month in (1, 2, 3, 10, 11, 12) else "summer"


def bucket_children(enfants: list[dict]) -> dict[str, int]:
    """VTF buckets: 0–1 babies, 2–5 nbChildren3, 6–11 nbChildren1, 12+ nbChildren2."""
    buckets = {"nbBabies": 0, "nbChildren3": 0, "nbChildren1": 0, "nbChildren2": 0}
    for child in enfants:
        age = child.get("age", 0)
        if age <= 1:
            buckets["nbBabies"] += 1
        elif age <= 5:
            buckets["nbChildren3"] += 1
        elif age <= 11:
            buckets["nbChildren1"] += 1
        else:
            buckets["nbChildren2"] += 1
    return buckets


VTF_FALLBACK_URL = "https://www.vtf-vacances.com/fr_FR/"


def build_vtf_booking_url(
    *, village, family: dict, dates: dict, saison_key: str
) -> tuple[str, dict[str, int | str]]:
    """Build the pre-filled VTF booking URL. Returns (url, params_used).

    When the village has no `vtf_department/vtf_city/vtf_slug`, fall back to
    the VTF homepage rather than emit a malformed `…/village-vacances///?…`
    URL. Search-engine params are still appended so the booking widget can
    pre-fill if VTF chooses to honor them on the homepage.
    """
    season_segment = saison_to_url_segment(saison_key, dates["debut"])
    has_full_path = all([village.vtf_department, village.vtf_city, village.vtf_slug])
    if has_full_path:
        base = (
            f"https://www.vtf-vacances.com/fr_FR/{season_segment}/"
            f"village-vacances/"
            f"{village.vtf_department}/{village.vtf_city}/{village.vtf_slug}"
        )
    else:
        base = VTF_FALLBACK_URL

    buckets = bucket_children(family.get("enfants") or [])
    nb_persons = family["adultes"] + len(family.get("enfants") or [])
    params: dict[str, int | str] = {
        "search_engine[startedAt]": dates["debut"],
        "search_engine[endedAt]": dates["fin"],
        "search_engine[nbPersons]": nb_persons,
        "search_engine[nbAdults]": family["adultes"],
    }
    for k, v in buckets.items():
        params[f"search_engine[{k}]"] = v
    return f"{base}?{urlencode(params)}", {
        "season": season_segment,
        "nbPersons": nb_persons,
        "nbAdults": family["adultes"],
        **buckets,
    }


def _booking_secret() -> bytes:
    secret = getattr(settings, "BOOKING_REDIRECT_SECRET", None) or settings.SECRET_KEY
    return secret.encode()


def mint_token(
    *, village_id: str, session_id: str, payload_hash: str, ttl_hours: int = 72
) -> tuple[str, datetime]:
    """HMAC-SHA256 signed token (not a JWT). Returns (token, expires_at_utc)."""
    nonce = secrets.token_urlsafe(16)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    body = f"{village_id}|{session_id}|{payload_hash}|{int(expires_at.timestamp())}|{nonce}"
    sig = hmac.new(_booking_secret(), body.encode(), hashlib.sha256).hexdigest()
    token = f"{nonce}.{int(expires_at.timestamp())}.{sig[:32]}"
    return token, expires_at


def verify_token(
    token: str, *, village_id: str, session_id: str, payload_hash: str
) -> bool:
    """Recompute the signature and constant-time compare."""
    try:
        nonce, exp_str, sig_short = token.split(".", 2)
        expires_at = datetime.fromtimestamp(int(exp_str), tz=timezone.utc)
    except (ValueError, OverflowError):
        return False
    if expires_at < datetime.now(timezone.utc):
        return False
    body = f"{village_id}|{session_id}|{payload_hash}|{int(expires_at.timestamp())}|{nonce}"
    expected = hmac.new(_booking_secret(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(expected, sig_short)


def hash_payload(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
