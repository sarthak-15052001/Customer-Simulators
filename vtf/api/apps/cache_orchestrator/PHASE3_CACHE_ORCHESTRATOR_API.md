# Cache Orchestrator — API Reference

> **Base path:** `/api/v3/admin/cache/`  
> **Auth:** Staff only — HTTP Basic Auth (`Authorization: Basic <base64(user:pass)>`)  
> **Response envelope:** Standard VTF envelope with `success`, `message`, `data`.

All three endpoints are **staff-only**. Unauthenticated requests are rejected before reaching the view logic.

---

## Endpoints at a Glance

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v3/admin/cache/rebuild` | Invalidate + re-warm cache by scope |
| `GET` | `/api/v3/admin/cache/status` | Live cache health dashboard |
| `GET` | `/api/v3/admin/cache/logs` | List recent rebuild audit log entries |

---

## 1. `POST /api/v3/admin/cache/rebuild`

**Purpose:** Invalidates all Redis keys matching the given scope, then re-populates them from the database. Runs **synchronously** and returns when complete (typically under 5 seconds for `scope=all`).

**Auth:** Staff only (HTTP Basic)

---

### Flow Diagram

```
  Client
    │
    │  POST /api/v3/admin/cache/rebuild
    │  { "scope": "pricing", "reason": "..." }
    │
    ▼
  CacheRebuildView.post()
    │
    ├── CacheRebuildRequestSerializer.is_valid()?
    │     NO  ──► 400 Bad Request  { errors: {...} }
    │
    │     YES ─┐
    │          ▼
    │   CacheOrchestrator.rebuild(
    │     scope, reason, triggered_by=request.user.email
    │   )
    │          │
    │     ┌────┴────────────────────────┐
    │     │ _invalidate(scope)          │
    │     │ → delete Redis key patterns │
    │     └────┬────────────────────────┘
    │          │
    │     ┌────┴────────────────────────┐
    │     │ _warm(scope)                │
    │     │ → serialize DB → Redis      │
    │     └────┬────────────────────────┘
    │          │
    │     CacheRebuildLog.create(...)
    │          │
    │          ▼
    │   summary dict + timestamp
    │
    ▼
  200 OK  { success: true, data: summary }
```

---

### Request Body

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `scope` | string | No | `"all"` | See valid scopes below |
| `reason` | string | No | `""` | Human-readable reason; stored in audit log |

#### Valid Scopes

| Scope | Keys Affected |
|---|---|
| `all` | `vtf:*` — everything |
| `catalog` | `vtf:catalog:*` |
| `pricing` | `vtf:catalog:pricing_rules`, `seasons`, `season:date:*`, `promos_catalog` |
| `recommendations` | `vtf:reco:*` |
| `booking_urls` | `vtf:booking:*` |
| `villages:<id>` | `vtf:catalog:villages:<id>:*` (single village) |
| `regions:<key>` | `vtf:catalog:regions:<slug>:*` (single region) |

---

### Sample Request — Pricing rebuild

```http
POST /api/v3/admin/cache/rebuild
Authorization: Basic <base64(user:pass)>
Content-Type: application/json

{
  "scope": "pricing",
  "reason": "New pricing rules uploaded for summer 2027"
}
```

### Sample Request — Single village rebuild

```http
POST /api/v3/admin/cache/rebuild
Authorization: Basic <base64(user:pass)>
Content-Type: application/json

{
  "scope": "villages:biarritz",
  "reason": "Village data updated by admin"
}
```

### Sample Request — Full rebuild (default scope)

```http
POST /api/v3/admin/cache/rebuild
Authorization: Basic <base64(user:pass)>
Content-Type: application/json

{}
```

---

### Success Response — `200 OK`

```json
{
  "success": true,
  "message": "Cache rebuild completed for scope='pricing'.",
  "data": {
    "status": "completed",
    "scope": "pricing",
    "keysInvalidated": 12,
    "keysRebuilt": 11,
    "durationMs": 847,
    "triggeredBy": "admin@vtf.fr",
    "reason": "New pricing rules uploaded for summer 2027",
    "timestamp": "2026-06-24T14:32:10.123456+00:00"
  }
}
```

### Response Fields

| Field | Type | Description |
|---|---|---|
| `status` | string | Always `"completed"` on success |
| `scope` | string | Scope that was rebuilt |
| `keysInvalidated` | int | Number of Redis keys deleted |
| `keysRebuilt` | int | Number of Redis keys warmed |
| `durationMs` | int | Wall-clock time for the full rebuild |
| `triggeredBy` | string | Email of the staff user who triggered it |
| `reason` | string | Reason passed in the request |
| `timestamp` | ISO datetime | UTC timestamp of rebuild completion |

---

### Error Responses

| Status | When |
|---|---|
| `400 Bad Request` | Invalid `scope` value (not in allowed list and not a `villages:` or `regions:` prefix) |
| `401 Unauthorized` | Missing or invalid Basic Auth credentials |
| `403 Forbidden` | Authenticated but not a staff user |

#### Sample 400 — Invalid scope

```json
{
  "success": false,
  "message": "Invalid request body.",
  "errors": {
    "scope": [
      "Invalid scope 'unknown'. Must be one of ['all', 'catalog', 'pricing', 'recommendations', 'booking_urls'] or 'villages:<id>' / 'regions:<key>'."
    ]
  }
}
```

---

## 2. `GET /api/v3/admin/cache/status`

**Purpose:** Returns a live snapshot of the Redis cache: connectivity, key counts by scope, memory usage, hit rate, and the most recent rebuild metadata. Designed as an **ops dashboard** endpoint.

**Auth:** Staff only (HTTP Basic)

---

### Flow Diagram

```
  Client
    │
    │  GET /api/v3/admin/cache/status?keyLimit=200
    │
    ▼
  CacheStatusView.get()
    │
    ├── collect_cache_health_stats()
    │     ├── ping Redis (vtf:health:ping)
    │     ├── count vtf:* keys
    │     ├── Redis INFO memory  → memoryUsedMb
    │     └── Redis INFO stats   → hitRatePercent
    │
    ├── CacheRebuildLog.objects.order_by("-created_at").first()
    │     └── lastRebuild, lastRebuildScope, lastRebuildDurationMs
    │
    ├── _scope_key_counts()
    │     └── count keys per scope: catalog / reco / booking
    │
    └── collect_key_ttl_listing(max_keys=keyLimit)
          └── vtf:* keys sorted by name with TTL values
    │
    ▼
  200 OK { success: true, data: stats }
```

---

### Query Parameters

| Param | Type | Default | Notes |
|---|---|---|---|
| `keyLimit` | int | `200` | Max keys to include in the per-key TTL listing. Clamped to 1–500. |

---

### Sample Request

```http
GET /api/v3/admin/cache/status?keyLimit=100
Authorization: Basic <base64(user:pass)>
```

---

### Success Response — `200 OK`

```json
{
  "success": true,
  "message": "Cache status fetched.",
  "data": {
    "backend": "redis",
    "connected": true,
    "totalKeys": 87,
    "memoryUsedMb": 12.45,
    "hitRatePercent": 94.3,
    "oldestKeyAgeSec": 3600,
    "lastRebuild": "2026-06-24T14:32:10.123456+00:00",
    "lastRebuildScope": "all",
    "lastRebuildDurationMs": 2341,
    "scopes": {
      "catalog": 71,
      "reco": 12,
      "booking": 4
    },
    "keys": [
      {
        "key": "vtf:catalog:animations",
        "ttlSeconds": 597834,
        "noExpiry": false
      },
      {
        "key": "vtf:catalog:pricing_rules",
        "ttlSeconds": 81240,
        "noExpiry": false
      },
      {
        "key": "vtf:reco:cf_model",
        "ttlSeconds": null,
        "noExpiry": true
      }
    ]
  }
}
```

### Response Fields

| Field | Type | Description |
|---|---|---|
| `backend` | string | `"redis"` or `"locmem"` |
| `connected` | bool | Whether Redis responded to a ping |
| `totalKeys` | int \| null | Count of `vtf:*` keys (Redis only) |
| `memoryUsedMb` | float \| null | Redis memory in MB (Redis only) |
| `hitRatePercent` | float \| null | Cache hit rate 0–100 (Redis only) |
| `oldestKeyAgeSec` | int \| null | Estimated age of oldest key in seconds |
| `lastRebuild` | ISO datetime \| null | Timestamp of the last rebuild |
| `lastRebuildScope` | string \| null | Scope of the last rebuild |
| `lastRebuildDurationMs` | int \| null | Duration of the last rebuild |
| `scopes` | object | Key counts per scope: `catalog`, `reco`, `booking` |
| `keys` | array | Per-key TTL listing (up to `keyLimit` entries) |

#### Key TTL Entry Fields

| Field | Type | Description |
|---|---|---|
| `key` | string | Logical Redis key (e.g. `vtf:catalog:meals`) |
| `ttlSeconds` | int \| null | Remaining TTL in seconds; `null` if key has no expiry |
| `noExpiry` | bool | `true` if the key has no TTL set (`TTL == -1` in Redis) |

---

### Behaviour on LocMem Backend

When Redis is not configured (local dev using Django LocMem cache), the response degrades gracefully:

- `backend`: `"locmem"`
- `totalKeys`: count of in-memory vtf keys (approximate)
- `memoryUsedMb`, `hitRatePercent`, `oldestKeyAgeSec`: `null`
- `scopes`: `{}` (empty)
- `keys`: `[]` (empty — LocMem has no TTL introspection)

---

## 3. `GET /api/v3/admin/cache/logs`

**Purpose:** Returns the most recent cache rebuild audit log entries. Used to check who triggered rebuilds, when, and why.

**Auth:** Staff only (HTTP Basic)

---

### Flow Diagram

```
  Client
    │
    │  GET /api/v3/admin/cache/logs?limit=20
    │
    ▼
  CacheRebuildLogListView.get()
    │
    ├── parse limit param (1–100, default 20)
    │
    └── CacheRebuildLog.objects.all()[:limit]
          (default ordering: -created_at)
    │
    ▼
  CacheRebuildLogSerializer(logs, many=True)
    │
    ▼
  200 OK  { success: true, data: [...] }
```

---

### Query Parameters

| Param | Type | Default | Notes |
|---|---|---|---|
| `limit` | int | `20` | Number of entries to return. Clamped to 1–100. |

---

### Sample Request

```http
GET /api/v3/admin/cache/logs?limit=5
Authorization: Basic <base64(user:pass)>
```

---

### Success Response — `200 OK`

```json
{
  "success": true,
  "message": "Last 5 cache rebuild log entries.",
  "data": [
    {
      "scope": "pricing",
      "keysInvalidated": 4,
      "keysRebuilt": 11,
      "durationMs": 412,
      "triggeredBy": "admin@vtf.fr",
      "reason": "New pricing rules uploaded for summer 2027",
      "createdAt": "2026-06-24T14:32:10.123456+00:00"
    },
    {
      "scope": "all",
      "keysInvalidated": 87,
      "keysRebuilt": 83,
      "durationMs": 2341,
      "triggeredBy": "system:signal:post_load_vtf_mocks",
      "reason": "load_vtf_mocks completed",
      "createdAt": "2026-06-24T09:15:00.000000+00:00"
    },
    {
      "scope": "villages:biarritz",
      "keysInvalidated": 1,
      "keysRebuilt": 1,
      "durationMs": 85,
      "triggeredBy": "system:management_command:rebuild_cache",
      "reason": "CLI: python manage.py rebuild_cache --scope=villages:biarritz",
      "createdAt": "2026-06-23T11:02:45.000000+00:00"
    }
  ]
}
```

### Response Fields (per log entry)

| Field | Type | Description |
|---|---|---|
| `scope` | string | Scope that was rebuilt |
| `keysInvalidated` | int | Number of Redis keys deleted during this rebuild |
| `keysRebuilt` | int | Number of Redis keys warmed during this rebuild |
| `durationMs` | int | Total time for the rebuild in milliseconds |
| `triggeredBy` | string | Who/what triggered the rebuild (email, system signal name, or CLI) |
| `reason` | string | Human-readable reason (may be empty) |
| `createdAt` | ISO datetime | UTC timestamp when the rebuild occurred |

---

### `triggeredBy` Values Reference

| Value pattern | Source |
|---|---|
| `admin@vtf.fr` (user email) | Staff user via POST /rebuild |
| `staff:unknown` | Authenticated staff with no identifiable email |
| `system:signal:PricingRules` | Auto-triggered by `PricingRules.save(is_active=True)` |
| `system:signal:post_load_vtf_mocks` | Auto-triggered after `load_vtf_mocks` command |
| `system:management_command:rebuild_cache` | Manual CLI invocation |
| `system:celery` | Celery task (fallback identifier) |

---

## Quick Reference Table

| Method | Path | Auth | Purpose | Key Params |
|---|---|---|---|---|
| `POST` | `/api/v3/admin/cache/rebuild` | Staff | Trigger invalidation + warming | `scope`, `reason` |
| `GET` | `/api/v3/admin/cache/status` | Staff | Live cache health snapshot | `keyLimit` (1–500) |
| `GET` | `/api/v3/admin/cache/logs` | Staff | Rebuild audit history | `limit` (1–100) |

---

## CLI Equivalent

The management command offers the same rebuild functionality as the POST endpoint, running synchronously without needing Celery or an HTTP request:

```bash
# Rebuild all scopes
python manage.py rebuild_cache

# Rebuild only pricing
python manage.py rebuild_cache --scope=pricing

# Rebuild a single village
python manage.py rebuild_cache --scope=villages:biarritz

# With a reason (stored in CacheRebuildLog)
python manage.py rebuild_cache --scope=all --reason="Post-deploy warm"
```

Output example:
```
Rebuilding cache scope='all' …
Done. keys_invalidated=87  keys_rebuilt=83  duration=2341ms
```