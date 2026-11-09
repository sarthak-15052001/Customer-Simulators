"""Redis-specific cache orchestrator tests (AC-3.3 + staging smoke).

Skipped automatically when REDIS_URL is not set (CI uses LocMem).

Run against local Redis:
  REDIS_URL=redis://localhost:6379/0 pytest tests/test_cache_redis.py -v

Or use the standalone smoke script:
  python scripts/redis_smoke_test.py
"""
from __future__ import annotations

import os
import threading
import time

import pytest
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.cache_orchestrator.cache_ops import (
    atomic_cache_set,
    collect_key_ttl_listing,
    is_redis_cache_backend,
)
from apps.cache_orchestrator.service import CacheOrchestrator

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("REDIS_URL"),
        reason="REDIS_URL not set — Redis integration tests skipped",
    ),
    pytest.mark.django_db,
]

REDIS_CACHE = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}


@pytest.fixture(autouse=True)
def clear_redis_between_tests():
    cache.clear()
    yield
    cache.clear()


@override_settings(CACHES=REDIS_CACHE)
class TestRedisCacheOrchestrator(TestCase):


    def test_settings_use_redis_for_celery_when_redis_url_set(self):
        """When REDIS_URL is configured, Celery defaults to Redis (not SQLite)."""
        from django.conf import settings as django_settings

        assert django_settings.CACHES["default"]["BACKEND"].endswith("RedisCache")
        assert django_settings.CELERY_BROKER_URL.startswith("redis://")
        assert django_settings.CELERY_RESULT_BACKEND.startswith("redis://")

    def test_atomic_cache_set_concurrent_readers_never_see_corrupt_value(self):
        """AC-3.3 — concurrent writers/readers must not observe partial payloads."""
        assert is_redis_cache_backend()
        key = "vtf:test:atomic-concurrency"
        stop = threading.Event()
        errors: list[str] = []

        def writer() -> None:
            for i in range(200):
                atomic_cache_set(
                    key,
                    {"version": i, "payload": "x" * 2048},
                    120,
                )

        def reader() -> None:
            while not stop.is_set():
                val = cache.get(key)
                if val is None:
                    continue
                if not isinstance(val, dict):
                    errors.append(f"non-dict value: {type(val)!r}")
                    continue
                if "version" not in val or "payload" not in val:
                    errors.append(f"missing fields: {val!r}")
                    continue
                if len(val["payload"]) != 2048:
                    errors.append(f"truncated payload at version={val.get('version')}")

        writer_thread = threading.Thread(target=writer)
        readers = [threading.Thread(target=reader) for _ in range(8)]
        writer_thread.start()
        for t in readers:
            t.start()
        writer_thread.join()
        time.sleep(0.05)
        stop.set()
        for t in readers:
            t.join(timeout=2)

        assert errors == [], f"stale/corrupt reads detected: {errors[:5]}"

    def test_pricing_rebuild_populates_key_ttl_listing(self):
        CacheOrchestrator.rebuild(scope="pricing", triggered_by="redis-smoke")
        listing = collect_key_ttl_listing(max_keys=50)
        warmed_keys = {row["key"] for row in listing}
        assert "vtf:catalog:season:date:2026-07-15" in warmed_keys or any(
            k.startswith("vtf:catalog:season:date:") for k in warmed_keys
        )

    def test_full_rebuild_completes_under_five_seconds_on_redis(self):
        start = time.perf_counter()
        result = CacheOrchestrator.rebuild(scope="all", triggered_by="redis-perf")
        elapsed = time.perf_counter() - start
        assert result["status"] == "completed"
        assert elapsed < 5.0, f"full rebuild took {elapsed:.2f}s on Redis"

