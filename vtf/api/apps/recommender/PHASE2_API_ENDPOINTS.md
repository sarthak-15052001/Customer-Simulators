# Phase 2 — API endpoints reference

This document describes every **Phase 2** HTTP endpoint: what it does, sample payloads, and responses.  
All responses use the standard envelope:

```json
{
  "success": true,
  "message": "Human-readable message",
  "data": { }
}
```

Errors use `"success": false` and may include an `"errors"` object for validation.

---

## API version split (client agreement)

| Base path | App | Phase 2 scope |
|-----------|-----|----------------|
| `/api/v1/` | `pricing` (+ `catalog` for Phase 1) | **Interactions** and **signals** only (among Phase 2 features) |
| `/api/v2/` | `recommender` | Recommendations, similar villages, bookmarks, admin reco |

The frontend should call **v1** for tracking and **v2** for the recommendation engine.

---

## 1. `POST /api/v1/interactions` — Track village interaction

**Purpose:** Record explicit user actions on a village (view, simulate, bookmark, rate, click CTA). Data feeds popularity ranking and the SVD matrix.

**Auth:** None (public simulator)  
**Rate limit:** 100 requests / hour / **session** (`X-Session-ID` header or `sessionId` in body)  
**Throttle:** `InteractionsSessionThrottle`

### Request

| Field | Type | Required | Notes |
|-------|------|----------|--------|
| `sessionId` | string | Recommended | Frontend UUID; also accepted via header `X-Session-ID` |
| `villageId` | string (slug) | Yes | e.g. `biarritz` |
| `kind` | string | Yes | `view`, `simulate`, `bookmark`, `rate`, `click_cta` |
| `value` | number | No | Default `1.0`; use `1–5` for `rate` |
| `metadata` | object | No | Free JSON (family, formule, estimate, etc.) |

### Sample payload

```json
{
  "sessionId": "abc-123-def-456",
  "villageId": "biarritz",
  "kind": "simulate",
  "metadata": {
    "formule": "PC",
    "saison": "ete",
    "estimatedTotal": 2847
  }
}
```

### Success response — `201 Created`

```json
{
  "success": true,
  "message": "Interaction recorded.",
  "data": {
    "id": 42
  }
}
```

### Errors

| Status | When |
|--------|------|
| `404` | Unknown `villageId` |
| `400` | Validation error |
| `429` | More than 100 interactions/hour for this session |

### What we implemented

- Persists a `VillageInteraction` row.
- Does **not** toggle bookmarks (use v2 bookmark endpoints for create/remove).
- Fast insert (target &lt; 50ms).

---

## 2. `POST /api/v1/signals` — Lightweight frontend beacons

**Purpose:** Fire-and-forget events from the simulator UI (`navigator.sendBeacon` friendly). Some map to `VillageInteraction`; others are stored as session-level `FrontendSignal`.

**Auth:** None  
**Rate limit:** Not throttled separately (keep payloads small).

### Request

| Field | Type | Required | Notes |
|-------|------|----------|--------|
| `sessionId` | string | Recommended | Same as interactions |
| `villageId` | string | No | Omit for session-only events |
| `kind` | string | Yes | See table below |
| `value` | number | No | Default `1.0` |
| `metadata` | object | No | e.g. `referrer`, `step`, `durationMs` |

### Signal kinds

| `kind` | Stored as | Used for |
|--------|-----------|----------|
| `session_start` | `FrontendSignal` | Funnel / acquisition |
| `step_complete` | `FrontendSignal` | Engagement depth |
| `result_dwell` | `FrontendSignal` | Time on results |
| `compare_villages` | `FrontendSignal` | Village switching |
| `village_view` | `VillageInteraction` → `view` | Dropdown selection |
| `result_view` | `VillageInteraction` → `view` | Results page |
| `recap_view` | `VillageInteraction` → `view` | Recap page |
| `share_click` | `VillageInteraction` → `click_cta` | Share / PDF |
| `view`, `simulate`, `bookmark`, `rate`, `click_cta` | `VillageInteraction` | Direct mapping |

### Sample — session start (no village)

```json
{
  "sessionId": "abc-123-def-456",
  "kind": "session_start",
  "metadata": {
    "referrer": "https://www.vtf-vacances.com/",
    "utmSource": "newsletter_mai",
    "deviceType": "mobile"
  }
}
```

### Sample — village view

```json
{
  "sessionId": "abc-123-def-456",
  "villageId": "biarritz",
  "kind": "village_view",
  "metadata": {
    "stepNumber": 2
  }
}
```

### Success response — `201 Created`

```json
{
  "success": true,
  "message": "Signal recorded.",
  "data": null
}
```

### What we implemented

- Mapping logic in `apps/pricing/services/signals.py`.
- Never blocks the UI on failure (errors swallowed server-side for beacons).

---

## 3. `POST /api/v2/recommend/villages` — Personalized recommendations

**Purpose:** Return **1–6** ranked villages for a family profile and preferences. **Always HTTP 200** with at least one village (waterfall guarantees non-empty).

**Auth:** None  
**Rate limit:** 100 requests / hour / IP (`RecommendIpThrottle`)

### Request

| Field | Type | Required | Notes |
|-------|------|----------|--------|
| `family` | object | Yes | See below |
| `preferences` | object | No | Empty `{}` → popularity fallback |
| `sessionId` | string | No | Enables interaction boost + optional CF re-rank |
| `limit` | integer | No | 1–10, default `6` |
| `explain` | boolean | No | Default `false`; `true` adds French `reasons` / `warnings` |

**`family`**

| Field | Type | Notes |
|-------|------|--------|
| `adultes` | int | 1–10 |
| `enfants` | array | `[{ "age": 4 }, { "age": 8 }]` |
| `qfVal` | int \| null | Quotient familial |
| `isSoloParent` | boolean | Solo-parent pricing |
| `maxiFamily` | boolean | Optional |

**`preferences`**

| Field | Type | Notes |
|-------|------|--------|
| `envs` | string[] | `sea`, `mountain`, `forest`, `countryside`, `sun` |
| `formule` | string | `PC`, `DP`, `LOC` |
| `budget` | int | Soft filter (not hard cutoff) |
| `dates` | object | `{ "debut": "2026-07-05", "fin": "2026-07-12" }` |
| `mustHave` | string[] | `bebeClub`, `ski`, `forfaitRM`, `enfSoloHalf`, `qfExc`, `hasLoc` |
| `avoidSki` | boolean | Penalizes ski villages |

### Sample payload (full preferences)

```json
{
  "family": {
    "adultes": 2,
    "enfants": [{ "age": 2 }, { "age": 7 }],
    "qfVal": 750,
    "isSoloParent": false,
    "maxiFamily": false
  },
  "preferences": {
    "envs": ["sea", "sun"],
    "formule": "PC",
    "budget": 2500,
    "dates": { "debut": "2026-07-05", "fin": "2026-07-12" },
    "mustHave": ["bebeClub"],
    "avoidSki": true
  },
  "sessionId": "abc-123-def-456",
  "limit": 6,
  "explain": true
}
```

### Sample payload (zero preferences — popularity fallback)

```json
{
  "family": {
    "adultes": 2,
    "enfants": [],
    "qfVal": null,
    "isSoloParent": false
  },
  "preferences": {}
}
```

### Success response — `200 OK`

```json
{
  "success": true,
  "message": "Recommendations generated.",
  "data": {
    "villages": [
      {
        "village": {
          "id": "biarritz",
          "nom": "Biarritz",
          "nom2": "",
          "region": "Aquitaine / Landes",
          "env": "🌊",
          "envCode": "sea",
          "formules": ["PC", "DP"],
          "ski": false,
          "bebeClub": true,
          "qfExc": true,
          "enfSoloHalf": false,
          "hasLoc": false
        },
        "score": 0.92,
        "reasons": [
          "Mer — environnement souhaité",
          "Club bébé dès 4 mois — idéal pour votre enfant de 2 ans",
          "Éligible quotient familial (-17%)",
          "Dans votre budget (estimé ~2 180€)"
        ],
        "warnings": [],
        "estimatedTotal": 2180,
        "bookingUrl": "https://api.example.com/api/v1/go/eyJ...",
        "rank": 1
      }
    ],
    "strategy": "personalized",
    "confidence": 0.88,
    "totalScored": 32,
    "relaxedFilters": [],
    "fallbackUsed": false,
    "abGroup": null
  }
}
```

### Response fields

| Field | Meaning |
|-------|---------|
| `strategy` | `personalized`, `personalized_cf`, or `popular_fallback` |
| `confidence` | 0.0–1.0 — how strong the match tier is |
| `totalScored` | Villages evaluated (usually 32) |
| `relaxedFilters` | Constraints dropped in waterfall (e.g. `budget`) |
| `fallbackUsed` | `true` from Tier 4+ (popularity / seed) |
| `abGroup` | `cf` or `control` when CF A/B test applies; else `null` |

### What we implemented

- 5-tier waterfall in `engine.py` (see `PHASE2_RECOMMENDATION_ENGINE.md`).
- Lightweight `estimatedTotal` per village.
- Signed `bookingUrl` via booking redirect service.
- Optional collaborative re-ranking when data thresholds are met.

---

## 4. `GET /api/v2/villages/{id}/similar` — Similar villages

**Purpose:** Suggest alternatives on a village detail page (same region, environment, formules).

### Query parameters

| Param | Type | Default | Notes |
|-------|------|---------|--------|
| `limit` | int | `3` | Max 10 |
| `sessionId` | string | `anon` | For booking link context |
| `explain` | boolean | false | `true` / `1` / `yes` |

### Example

```http
GET /api/v2/villages/biarritz/similar?limit=3&sessionId=abc-123&explain=true
```

### Success response — `200 OK`

Same envelope as recommend; `data.strategy` is `"similar"`. Current village is **excluded**.

### Errors

| Status | When |
|--------|------|
| `404` | Unknown village id |

---

## 5. `POST /api/v2/interactions/bookmark` — Add bookmark

**Purpose:** Idempotent **create** — if bookmark already exists, returns existing id (`created: false`).

### Request

```json
{
  "sessionId": "abc-123-def-456",
  "villageId": "biarritz"
}
```

`sessionId` may be sent as header `X-Session-ID` instead.

### Success — `200 OK`

```json
{
  "success": true,
  "message": "Bookmark added.",
  "data": {
    "bookmarked": true,
    "id": 15,
    "created": true
  }
}
```

---

## 6. `POST /api/v2/interactions/bookmark/remove` — Remove bookmark

### Request

Same shape as bookmark create.

### Success — `200 OK`

```json
{
  "success": true,
  "message": "Bookmark removed.",
  "data": {
    "bookmarked": false,
    "removed": 1
  }
}
```

---

## 7. `GET /api/v2/admin/interactions/stats` — Interaction analytics (staff)

**Purpose:** Aggregated views / simulations / bookmarks per village for dashboards.

**Auth:** Staff only (Django user `is_staff=True` or session auth)

### Query parameters

| Param | Values | Notes |
|-------|--------|--------|
| `period` | `7d`, `30d`, `90d` | Default `30d` if no custom dates |
| `start_date` | `YYYY-MM-DD` | Custom range (with `end_date`) |
| `end_date` | `YYYY-MM-DD` | Custom range |

Note: `period=all` from the original spec is **not** implemented; use custom dates for full history.

### Example

```http
GET /api/v2/admin/interactions/stats?period=30d
```

### Success — `200 OK`

```json
{
  "success": true,
  "message": "Interaction stats fetched.",
  "data": {
    "period": "30d",
    "villages": [
      {
        "villageId": "biarritz",
        "villageNom": "Biarritz",
        "views": 342,
        "simulations": 89,
        "bookmarks": 23,
        "total": 454
      }
    ]
  }
}
```

---

## 8. `GET /api/v2/admin/reco-weights` — Read scoring weights

**Auth:** Staff only

### Success — `200 OK`

```json
{
  "success": true,
  "message": "Scoring weights fetched.",
  "data": {
    "budget_fit": 0.30,
    "env_match": 0.25,
    "family_fit": 0.20,
    "season_availability": 0.15,
    "extras_match": 0.10,
    "popularity_boost": 0.05,
    "interaction_boost": 0.05
  }
}
```

---

## 9. `POST /api/v2/admin/reco-weights` — Update scoring weights

**Purpose:** Tune content-based scoring without redeploying code.

**Auth:** Staff only

### Sample payload (partial update)

```json
{
  "budget_fit": 0.40,
  "env_match": 0.20
}
```

Merges with current active weights and creates a new active `RecoWeights` row.

---

## Quick reference table

| Method | Path | Version | Purpose |
|--------|------|---------|---------|
| POST | `/interactions` | v1 | Track interaction |
| POST | `/signals` | v1 | Frontend beacon |
| POST | `/recommend/villages` | v2 | Get recommendations |
| GET | `/villages/{id}/similar` | v2 | Similar villages |
| POST | `/interactions/bookmark` | v2 | Add bookmark |
| POST | `/interactions/bookmark/remove` | v2 | Remove bookmark |
| GET | `/admin/interactions/stats` | v2 | Staff analytics |
| GET | `/admin/reco-weights` | v2 | Read weights |
| POST | `/admin/reco-weights` | v2 | Update weights |
