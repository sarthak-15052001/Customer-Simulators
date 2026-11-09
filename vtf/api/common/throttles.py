"""Custom DRF throttle classes — spec §5.2.

Rate limits (per spec table):
    Catalog GET endpoints       → 1000 / hour / IP
    POST /estimate/*            → 200  / hour / IP
    POST /recommend/*           → 100  / hour / IP
    POST /interactions          → 100  / hour / Session

All classes inherit from DRF's built-in AnonRateThrottle / SimpleRateThrottle
so they integrate transparently with the DEFAULT_THROTTLE_CLASSES setting and
return the standard 429 response with a Retry-After header.

Configure rates in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] (see base.py).
"""
from __future__ import annotations

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


# ─── IP-based throttles ───────────────────────────────────────────────────

class CatalogIpThrottle(AnonRateThrottle):
    """1000 requests / hour per IP — applied to all catalog GET endpoints."""
    scope = "catalog_ip"


class EstimateIpThrottle(AnonRateThrottle):
    """200 requests / hour per IP — applied to POST /estimate/stay."""
    scope = "estimate_ip"


class RecommendIpThrottle(AnonRateThrottle):
    """100 requests / hour per IP — applied to POST /recommend/*."""
    scope = "recommend_ip"


# ─── Session-based throttle ───────────────────────────────────────────────

class InteractionsSessionThrottle(SimpleRateThrottle):
    """100 requests / hour per session — applied to POST /interactions.

    The cache key is built from the X-Session-ID header so each frontend
    session has its own bucket (not IP, which would penalise shared NAT).
    Falls back to IP when the header is absent.
    """
    scope = "interactions_session"

    def get_cache_key(self, request, view):
        session_id = (
            request.headers.get("X-Session-ID")
            or request.data.get("sessionId")
            or ""
        )
        if session_id:
            ident = session_id[:64]
        else:
            # Graceful fallback — use IP like the IP throttles do.
            ident = self.get_ident(request)

        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }
