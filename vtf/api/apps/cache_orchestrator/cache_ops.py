"""Low-level cache helpers — atomic writes and Redis stats (spec AC-3.3 / US-5.3)."""
from __future__ import annotations

import logging
import time
from typing import Any

from django.core.cache import cache

logger = logging.getLogger(__name__)

_STAGING_SUFFIX = ":__staging__"
_KEY_TTL_LISTING_DEFAULT_LIMIT = 200


def is_redis_cache_backend() -> bool:
    """True when Django cache is backed by django-redis.

    Django wraps the backend in ``ConnectionProxy``, so we inspect the client
    module instead of ``cache.__class__.__name__``.
    """
    try:
        return cache.client.__class__.__module__.startswith("django_redis")
    except Exception:
        return "Redis" in cache.__class__.__name__


def _django_redis_client():
    """django-redis ``DefaultClient`` (handles key prefix/version)."""
    if not is_redis_cache_backend():
        return None
    try:
        return cache.client
    except Exception:
        logger.debug("cache_ops_django_redis_client_unavailable", exc_info=True)
        return None


def _raw_redis_client():
    """Underlying redis-py client for INFO/TTL/RENAME."""
    drf_client = _django_redis_client()
    if drf_client is None:
        return None
    try:
        return drf_client.get_client(write=True)
    except Exception:
        logger.debug("cache_ops_redis_client_unavailable", exc_info=True)
        return None


def count_logical_keys(pattern: str) -> int:
    """Count logical cache keys matching *pattern* (Redis only)."""
    return len(_logical_keys_matching(pattern))


def _logical_keys_matching(pattern: str) -> list[str]:
    """Return logical cache keys matching *pattern* (django-redis aware)."""
    drf_client = _django_redis_client()
    if drf_client is None:
        return []
    try:
        return list(drf_client.keys(pattern))
    except Exception:
        logger.debug("logical_keys_matching_failed pattern=%s", pattern, exc_info=True)
        return []


def atomic_cache_set(key: str, value: Any, timeout: int) -> None:
    """Write *value* with minimal stale-read window (Redis RENAME when available)."""
    drf_client = _django_redis_client()
    raw_client = _raw_redis_client()
    if drf_client is None or raw_client is None:
        cache.set(key, value, timeout)
        return

    staging = f"{key}{_STAGING_SUFFIX}"
    try:
        cache.set(staging, value, timeout)
        raw_client.rename(
            drf_client.make_key(staging),
            drf_client.make_key(key),
        )
    except Exception:
        logger.debug("atomic_cache_set_rename_failed key=%s — falling back", key, exc_info=True)
        cache.set(key, value, timeout)
        try:
            cache.delete(staging)
        except Exception:
            pass


def delete_patterns(patterns: list[str]) -> int:
    """Delete keys matching Redis patterns; LocMem falls back to prefix scan."""
    deleted = 0
    drf_client = _django_redis_client()
    if drf_client is not None:
        for pattern in patterns:
            try:
                deleted += drf_client.delete_pattern(pattern, itersize=500)
            except Exception as exc:
                logger.warning("delete_patterns failed pattern=%s: %s", pattern, exc)
        return deleted

    # LocMem: scan internal store when available.
    try:
        store = getattr(cache, "_cache", None)
        if store is None:
            return deleted
        all_keys = list(store.keys())
        for pattern in patterns:
            prefix = pattern.rstrip("*")
            for raw_key in all_keys:
                key = raw_key[0] if isinstance(raw_key, tuple) else raw_key
                key_str = str(key)
                if pattern.endswith("*") and key_str.startswith(prefix):
                    if cache.delete(key_str):
                        deleted += 1
                elif key_str == pattern and cache.delete(key_str):
                    deleted += 1
    except Exception as exc:
        logger.debug("delete_patterns_locmem_scan_failed: %s", exc)
    return deleted


def collect_key_ttl_listing(*, max_keys: int = _KEY_TTL_LISTING_DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Per-key TTL snapshot for ops dashboard (Redis only).

    Returns up to *max_keys* ``vtf:*`` entries sorted by key name.
    LocMem returns an empty list (no TTL introspection).
    """
    drf_client = _django_redis_client()
    raw_client = _raw_redis_client()
    if drf_client is None or raw_client is None:
        return []

    logical_keys = [
        k
        for k in _logical_keys_matching("vtf:*")
        if not k.endswith(_STAGING_SUFFIX)
    ]
    logical_keys.sort()
    logical_keys = logical_keys[:max_keys]

    listing: list[dict[str, Any]] = []
    for logical_key in logical_keys:
        try:
            ttl = int(raw_client.ttl(drf_client.make_key(logical_key)))
        except Exception:
            continue
        entry: dict[str, Any] = {
            "key": logical_key,
            "ttlSeconds": None,
            "noExpiry": False,
        }
        if ttl == -2:
            continue  # key disappeared between KEYS and TTL
        if ttl == -1:
            entry["noExpiry"] = True
        elif ttl >= 0:
            entry["ttlSeconds"] = ttl
        listing.append(entry)
    return listing


def collect_cache_health_stats() -> dict[str, Any]:
    """Stats for ``GET /api/v1/health`` and admin cache status."""
    backend_name = cache.__class__.__name__
    is_redis = is_redis_cache_backend()
    stats: dict[str, Any] = {
        "backend": "redis" if is_redis else "locmem",
        "connected": True,
        "totalKeys": None,
        "memoryUsedMb": None,
        "hitRatePercent": None,
        "oldestKeyAgeSec": None,
    }

    try:
        cache.set("vtf:health:ping", 1, 5)
        stats["connected"] = bool(cache.get("vtf:health:ping"))
    except Exception:
        stats["connected"] = False
        return stats

    drf_client = _django_redis_client()
    raw_client = _raw_redis_client()
    if drf_client is not None and raw_client is not None:
        try:
            stats["totalKeys"] = len(_logical_keys_matching("vtf:*"))
        except Exception:
            pass
        try:
            info = raw_client.info(section="memory")
            used = info.get("used_memory", 0)
            stats["memoryUsedMb"] = round(used / (1024 * 1024), 2)
        except Exception:
            pass
        try:
            info = raw_client.info(section="stats")
            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total = hits + misses
            if total > 0:
                stats["hitRatePercent"] = round(100.0 * hits / total, 1)
        except Exception:
            pass
        try:
            oldest: float | None = None
            for logical_key in _logical_keys_matching("vtf:*")[:200]:
                try:
                    ttl = raw_client.ttl(drf_client.make_key(logical_key))
                    if ttl > 0:
                        # Approximate age from remaining TTL vs a 24h default max.
                        age = max(0, TTL_GUESS_SECONDS - ttl)
                        oldest = age if oldest is None else max(oldest, age)
                except Exception:
                    continue
            if oldest is not None:
                stats["oldestKeyAgeSec"] = int(oldest)
        except Exception:
            pass
    else:
        try:
            store = getattr(cache, "_cache", {})
            vtf_count = sum(
                1
                for raw_key in store
                if "vtf:" in str(raw_key[0] if isinstance(raw_key, tuple) else raw_key)
            )
            stats["totalKeys"] = vtf_count
        except Exception:
            pass

    return stats


TTL_GUESS_SECONDS = 60 * 60 * 24


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)
