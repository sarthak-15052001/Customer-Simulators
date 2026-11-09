# Cache Orchestrator — How It Works

> **App path:** `vtf/api/apps/cache_orchestrator/`  
> **Spec reference:** §5.1 / US-5.1  
> **Backend:** Redis (via `django-redis`); falls back to Django LocMem for local dev.

---

## Overview

The **CacheOrchestrator** is a scope-aware Redis cache management layer for the VTF API. Its job is simple: when data changes, **invalidate** the stale keys, then **re-warm** fresh data back into Redis before the next HTTP request arrives — so end-users always hit a warm cache and never wait for a cold database round-trip.

It is called from **three entry points**:

| Trigger | Path | Scope |
|---|---|---|
| Django signal (`PricingRules.save`) | Automatic, async via Celery | `pricing` |
| Management command (`rebuild_cache`) | CLI, synchronous | Any scope |
| Admin HTTP endpoint (`POST /admin/cache/rebuild`) | Staff-only REST call | Any scope |

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TRIGGER SOURCES                              │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  PricingRules    │  │  Management Cmd  │  │  Admin REST API  │  │
│  │  .save()         │  │  rebuild_cache   │  │  POST /rebuild   │  │
│  │  (Django signal) │  │  (CLI, sync)     │  │  (staff only)    │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
└───────────┼─────────────────────┼─────────────────────┼────────────┘
            │ async (Celery)      │ sync                │ sync
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CacheOrchestrator.rebuild(scope)                  │
│                         service.py                                   │
│                                                                     │
│   1. _invalidate(scope)  →  delete_patterns(patterns)               │
│   2. _warm(scope)        →  atomic_cache_set(key, value, ttl)       │
│   3. CacheRebuildLog.objects.create(...)                            │
│   4. _maybe_notify(summary)  →  Discord webhook (if configured)     │
└─────────────────────────────────────────────────────────────────────┘
            │                     │
            ▼                     ▼
     ┌─────────────┐       ┌─────────────┐
     │    Redis    │       │  Sqlite3  │
     │  (cache)    │       │  (DB source) │
     └─────────────┘       └─────────────┘
```

---

## Step-by-Step Flow

### 1. Trigger

```
  PricingRules saved (is_active=True)
          │
          ▼
  signals.py: on_pricing_rules_saved()
          │
          ├─── Celery available? ──YES──► task_rebuild_cache.delay(scope="pricing")
          │                                       │
          │                                       ▼
          │                              Celery Worker picks up task
          │                              (max 3 retries, 30s apart)
          │
          └─── Celery DOWN? ─────NO───► CacheOrchestrator.rebuild() [sync fallback]
```

---

### 2. Scope Resolution

The scope string controls **which keys get deleted** and **which data gets re-warmed**.

```
scope passed to rebuild()
          │
          ├── "all"            → patterns: ["vtf:*"]
          ├── "catalog"        → patterns: ["vtf:catalog:*"]
          ├── "pricing"        → patterns: ["vtf:catalog:pricing_rules",
          │                                 "vtf:catalog:seasons",
          │                                 "vtf:catalog:season:date:*",
          │                                 "vtf:catalog:promos_catalog"]
          ├── "recommendations"→ patterns: ["vtf:reco:*"]
          ├── "booking_urls"   → patterns: ["vtf:booking:*"]
          ├── "villages:<id>"  → patterns: ["vtf:catalog:villages:<id>:*"]
          └── "regions:<key>"  → patterns: ["vtf:catalog:regions:<slug>:*"]
```

---

### 3. Invalidation

```
_invalidate(scope)
      │
      ▼
delete_patterns(patterns)   ← cache_ops.py
      │
      ├── Redis backend?
      │     └── drf_client.delete_pattern(pattern, itersize=500)
      │
      └── LocMem backend?
            └── scan internal _cache store, delete prefix matches
      │
      ▼
returns: int (number of keys deleted)
```

---

### 4. Warming

Warming serialises **live database data** and writes it into Redis with an appropriate TTL so subsequent HTTP reads are instant.

```
_warm(scope)
      │
      ├── scope == "all" or "catalog"    ──► _warm_catalog()
      ├── scope == "all" or "pricing"    ──► _warm_pricing()
      ├── scope == "all" or "recommendations" ► _warm_recommendations()
      ├── scope == "all" or "booking_urls"   ► _warm_booking_urls()
      ├── scope starts with "villages:" ──► _warm_village(id)
      └── scope starts with "regions:"  ──► _warm_region(key)
```

#### What each warm function writes

| Warm Function | Keys Written | TTL |
|---|---|---|
| `_warm_catalog()` | `vtf:catalog:villages:{id}:detail` (per village) | 24h |
| | `vtf:catalog:attractions` | 24h |
| | `vtf:catalog:regions:list` | 7d |
| | `vtf:catalog:regions:{key}:activities:{kind}:{season}` (per combo) | 24h |
| | `vtf:catalog:meals`, `formules`, `fuels`, `promos_catalog`, `animations` | 7d |
| | `vtf:catalog:landing_map` | 7d |
| | `vtf:catalog:marketing_seasons` | 7d |
| | `vtf:catalog:environments:{season_key}` | 7d |
| `_warm_pricing()` | `vtf:catalog:pricing_rules` | 24h |
| | `vtf:catalog:seasons` | 7d |
| | `vtf:catalog:promos_catalog` | 7d |
| | `vtf:catalog:season:date:{date}` (8 sample dates) | 1h |
| `_warm_recommendations()` | `vtf:reco:popularity:{village_id}` (per village) | 6h |
| | `vtf:reco:cf_model` (if present) | 7d |
| `_warm_booking_urls()` | `vtf:booking:token:{token}` (non-expired tokens) | 72h |
| `_warm_village(id)` | `vtf:catalog:villages:{id}:detail` | 24h |
| `_warm_region(key)` | `vtf:catalog:regions:{key}:activities:{kind}:{season}` | 24h |

---

### 5. Atomic Cache Write

To avoid a **read window** where a key exists but holds stale data during the overwrite, all cache writes use the `atomic_cache_set()` helper:

```
atomic_cache_set(key, value, ttl)
      │
      ├── Redis available?
      │     ├── Write to staging key:  "{key}:__staging__"
      │     └── RENAME staging → final key (atomic in Redis)
      │
      └── Redis unavailable?
            └── cache.set(key, value, ttl)  [standard Django write]
```

---

### 6. Logging & Notification

After every rebuild, the orchestrator:

1. Writes a `CacheRebuildLog` row to PostgreSQL (scope, keys_invalidated, keys_rebuilt, duration_ms, triggered_by, reason).
2. Optionally posts a Discord embed via webhook (enabled by `CACHE_REBUILD_NOTIFY=True` + `DISCORD_WEBHOOK` in settings).

```
rebuild() completes
      │
      ├── CacheRebuildLog.objects.create(...)
      │
      └── _maybe_notify(summary)
                │
                ├── CACHE_REBUILD_NOTIFY == True?  ──NO──► skip
                │
                └── YES → POST Discord webhook
                          fields: scope, keysInvalidated,
                                  keysRebuilt, durationMs,
                                  triggeredBy, reason
```

---

## Key Registry

All cache key patterns and TTLs are centrally defined in `key_registry.py`. This is the **single source of truth** for naming conventions.

```
Key pattern                              → Endpoint served             TTL
─────────────────────────────────────────────────────────────────────────
vtf:catalog:villages:{id}:detail         GET /villages/{id}/           24h
vtf:catalog:attractions                  GET /attractions              24h
vtf:catalog:regions:list                 GET /regions                   7d
vtf:catalog:regions:{key}:activities:*   GET /regions/{key}/activities 24h
vtf:catalog:pricing_rules                GET /pricing-rules            24h
vtf:catalog:seasons                      GET /seasons                   7d
vtf:catalog:season:date:{date}           GET /season?date=             1h
vtf:catalog:meals                        GET /meals                     7d
vtf:catalog:formules                     GET /formules                  7d
vtf:catalog:fuels                        GET /fuels                     7d
vtf:catalog:promos_catalog               GET /promos/catalog            7d
vtf:catalog:animations                   GET /animations                7d
vtf:catalog:landing_map                  GET /landing-map               7d
vtf:catalog:marketing_seasons            GET /marketing-seasons         7d
vtf:catalog:environments:{key}           GET /environments/{key}        7d
vtf:reco:popularity:{village_id}         popularity score               6h
vtf:reco:cf_model                        trained SVD model              7d
vtf:booking:token:{token}               redirect token payload         72h
```

> **Note:** `vtf:catalog:villages:list` (village list) is intentionally **not warmed** — disabled per client request.

---

## Database Model

`CacheRebuildLog` records every rebuild event for auditability.

| Column | Type | Notes |
|---|---|---|
| `id` | AutoField | Primary key |
| `scope` | CharField(64) | e.g. `all`, `pricing`, `villages:biarritz` |
| `keys_invalidated` | IntegerField | Count of keys deleted |
| `keys_rebuilt` | IntegerField | Count of keys warmed |
| `duration_ms` | IntegerField | Total time for the rebuild |
| `triggered_by` | CharField(128) | e.g. user email, `system:signal:PricingRules` |
| `reason` | TextField | Human-readable reason |
| `created_at` | DateTimeField | Auto-set, indexed, ordered DESC |

---

## Components Map

```
cache_orchestrator/
│
├── service.py          ← CacheOrchestrator class (core logic)
│                          .rebuild()       — main entry point
│                          ._invalidate()   — delete Redis keys
│                          ._warm_*()       — populate Redis keys
│                          ._maybe_notify() — Discord webhook
│
├── cache_ops.py        ← Low-level Redis helpers
│                          atomic_cache_set()    — staging rename trick
│                          delete_patterns()     — pattern-based delete
│                          collect_cache_health_stats() — ops dashboard
│                          collect_key_ttl_listing()    — per-key TTLs
│
├── key_registry.py     ← Central cache key patterns & TTLs
│                          REGISTRY, SCOPE_PATTERNS, TTL_* constants
│                          Helper functions: activities_cache_key(),
│                          village_detail_cache_key(), etc.
│
├── signals.py          ← Django signal wiring
│                          on_pricing_rules_saved() — scope=pricing
│                          on_load_vtf_mocks_done() — scope=all
│
├── tasks.py            ← Celery task wrapper
│                          task_rebuild_cache() — async + retry logic
│
├── views.py            ← REST API views (staff only)
│                          CacheRebuildView
│                          CacheStatusView
│                          CacheRebuildLogListView
│
├── serializers.py      ← Request/response shapes
├── models.py           ← CacheRebuildLog ORM model
├── urls.py             ← URL routing
└── management/
    └── commands/
        └── rebuild_cache.py  ← CLI command (synchronous)
```

---

## TTL Reference

| Constant | Value | Used For |
|---|---|---|
| `TTL_1H` | 3 600s | Season date lookups (change frequently) |
| `TTL_6H` | 21 600s | Village popularity scores |
| `TTL_24H` | 86 400s | Village details, activities, pricing rules |
| `TTL_72H` | 259 200s | Booking redirect tokens |
| `TTL_7D` | 604 800s | Reference data (meals, seasons, regions…) |

---

## Celery Task Retry Policy

```
task_rebuild_cache
  max_retries: 3
  default_retry_delay: 30s (between retries)
  ignore_result: False
  bind: True (self reference for retry())
```

If all retries fail, the exception propagates to Celery's failure handler. The management command and synchronous fallback paths do **not** retry — they raise on failure and log the error.

---

## Full Rebuild Flow (end-to-end)

```
  ┌─────────────────────────────────────────────────────────────┐
  │                     TRIGGER                                 │
  │  (signal / CLI / API)                                       │
  └───────────────────────────┬─────────────────────────────────┘
                              │
                              ▼
                   CacheOrchestrator.rebuild(
                     scope, reason, triggered_by
                   )
                              │
               ┌──────────────┴──────────────┐
               │ PHASE 1: INVALIDATE          │
               │ _invalidate(scope)           │
               │ → resolve scope → patterns   │
               │ → delete_patterns(patterns)  │
               │ → returns keys_invalidated   │
               └──────────────┬──────────────┘
                              │
               ┌──────────────┴──────────────┐
               │ PHASE 2: WARM               │
               │ _warm(scope)                │
               │ → query DB via ORM          │
               │ → serialize with DRF        │
               │ → atomic_cache_set()        │
               │   (staging RENAME trick)    │
               │ → returns keys_rebuilt      │
               └──────────────┬──────────────┘
                              │
               ┌──────────────┴──────────────┐
               │ PHASE 3: LOG & NOTIFY        │
               │ CacheRebuildLog.create(...)  │
               │ _maybe_notify() → Discord    │
               │ return summary dict          │
               └──────────────────────────────┘