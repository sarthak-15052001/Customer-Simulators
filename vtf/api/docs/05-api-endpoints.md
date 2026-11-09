# 05 — REST API endpoints

> Spec source: §3.3 + §4.3 + §5.1 + §6.1 (errors / rate limits / CORS).
>
> - Base URL: `/api/v1/`
> - Auth: **none** for Phase 1 (public simulator). Admin endpoints require staff session.
> - Rate-limited by IP / session — see §6.2 below.
> - JSON keys: **camelCase** in I/O (frontend compatibility). Snake_case stays internal.
> - Versioning: URL prefix (`/v1/`). Breaking changes → bump to `/v2/` with a deprecation period.

## Conventions

- **Lecture**: `GET`, cacheable; cache TTLs explicit per-endpoint.
- **Calcul**: `POST` (idempotent but body-heavy). No DB writes for the response itself; logs are `transaction.on_commit`.
- **Always returns ≥ 1 result** for `/recommend/villages` — never empty (spec AC-2.1).
- **Errors**: standardized shape (see §6.1).
- **Pagination**: `?limit=&offset=` (DRF `LimitOffsetPagination`) on `/villages` and `/regions/{r}/activities`.

## Catalog (read-only)

> Spec §3.3. All Phase 1.

| Method | Path                                              | Auth  | Cache | Response                        |
|--------|---------------------------------------------------|-------|-------|---------------------------------|
| `GET`  | `/api/v1/villages`                                | None  | 24 h  | Paginated `VillageList[]`       |
| `GET`  | `/api/v1/villages/{id}`                           | None  | 24 h  | `VillageDetail`                 |
| `GET`  | `/api/v1/regions`                                 | None  | 7 d   | `RegionSummary[]`               |
| `GET`  | `/api/v1/regions/{region}/activities`             | None  | 24 h  | `Activity[]`                    |
| `GET`  | `/api/v1/seasons`                                 | None  | 7 d   | `Season[]`                      |
| `GET`  | `/api/v1/season?date=YYYY-MM-DD`                  | None  | 1 h   | `{ saisonKey, saisonIdx }`      |
| `GET`  | `/api/v1/meals`                                   | None  | 7 d   | `Meal[]`                        |
| `GET`  | `/api/v1/fuels`                                   | None  | 7 d   | `Fuel[]`                        |
| `GET`  | `/api/v1/promos/catalog`                          | None  | 7 d   | `PromoCatalogItem[]`            |
| `GET`  | `/api/v1/pricing-rules`                           | None  | 24 h  | `PricingRules` (active)         |
| `GET`  | `/api/v1/animations`                              | None  | 7 d   | `Animation[]`                   |

### Filters on `/villages`

| Param         | Example                       | Meaning                                                        |
|---------------|-------------------------------|----------------------------------------------------------------|
| `?region=`    | `Aquitaine / Landes`          | Exact match (URL-encoded)                                      |
| `?env=`       | `sea` \| `mountain` \| `sun` … | `env_code` enum                                                |
| `?formule=`   | `PC` \| `DP` \| `LOC`         | Village's `formules` array contains this value                 |
| `?ski=`       | `true` \| `false`             |                                                                |
| `?search=`    | `biar`                        | Case- and accent-insensitive on `nom` and `nom2`               |
| `?openOn=`    | `2026-07-12`                  | Only villages open on this date (parses `ouverture`)           |

### Filters on `/regions/{region}/activities`

| Param      | Example         | Meaning                                                     |
|------------|-----------------|-------------------------------------------------------------|
| `?kind=`   | `free` / `paid` |                                                             |
| `?season=` | `ete`           | Only activities whose `saisons` array contains this value    |

## Pricing (calculation)

> Spec §3.3. All Phase 1.

| Method | Path                                                  | Auth | Cache | Request → Response                                |
|--------|-------------------------------------------------------|------|-------|---------------------------------------------------|
| `POST` | `/api/v1/estimate/stay`                               | None | none  | `EstimateStayInput` → `SejourEstimate`            |
| `POST` | `/api/v1/transport/car`                               | None | none  | `CarCostInput` → `CarCostOutput`                  |
| `POST` | `/api/v1/transport/train`                             | None | none  | `TrainCostInput` → `TrainCostOutput`              |
| `POST` | `/api/v1/family/qf`                                   | None | none  | `QfInput` → `QfOutput`                            |
| `POST` | `/api/v1/resto/total`                                 | None | none  | `RestoTotalInput` → `RestoTotalOutput`            |
| `POST` | `/api/v1/promos/available`                            | None | none  | `AvailablePromosInput` → `PromoChoice[]`          |
| `POST` | `/api/v1/stay/days`                                   | None | none  | `StayDaysInput` → `StayDay[]`                     |
| `POST` | `/api/v1/villages/{id}/booking-link`                  | None | none  | `BookingLinkInput` → `BookingLinkOutput`          |
| `GET`  | `/api/v1/go/{token}`                                  | None | none  | `302 Location: <vtf_url>` (logs `BookingClick`)   |

## Recommendations (Phase 2)

> Spec §4.3.

| Method | Path                                              | Auth  | Returns                                                     |
|--------|---------------------------------------------------|-------|-------------------------------------------------------------|
| `POST` | `/api/v1/recommend/villages`                      | None  | `{ villages[], strategy, confidence, totalScored, relaxedFilters[], fallbackUsed }` — **always ≥ 1** |
| `GET`  | `/api/v1/villages/{id}/similar?limit=3`           | None  | `RecommendedVillage[]`                                      |
| `POST` | `/api/v1/interactions`                            | None  | `{ id }` — fire-and-forget, < 50 ms                         |

`strategy` ∈ `personalized`, `personalized_cf`, `personalized_ab_control`, `relaxed`,
`region_only`, `popular_fallback`, `hardcoded_safety_net`. See `07-recommendation-engine.md`.

## Admin (Phase 2 + 3)

> Spec §4.3 + §5.1 + §5.2. Auth = staff (Django session or token).

| Method | Path                                              | Purpose                                  |
|--------|---------------------------------------------------|------------------------------------------|
| `GET`  | `/api/v1/admin/interactions/stats?period=30d`     | Aggregated interaction stats per village |
| `POST` | `/api/v1/admin/reco-weights`                      | Update content-based scoring weights     |
| `POST` | `/api/v1/admin/cache/rebuild`                     | Body: `{ scope, reason }` — rebuild Redis|
| `POST` | `/api/v1/admin/scraper/activities`                | Body: target village/region; returns `jobId` |
| `GET`  | `/api/v1/admin/scraper/jobs/{jobId}`              | Poll job status + candidates             |
| `POST` | `/api/v1/admin/scraper/import`                    | Approve/reject/edit scraping candidates  |

## System

| Method | Path                          | Auth | Purpose                                        |
|--------|-------------------------------|------|------------------------------------------------|
| `GET`  | `/api/v1/health`              | None | `{ status, version, dataVersion, cache: {...} }` |
| `GET`  | `/api/schema/`                | None | OpenAPI 3.0 spec (JSON, drf-spectacular)        |
| `GET`  | `/api/docs/`                  | None | Swagger UI                                      |
| `GET`  | `/api/redoc/`                 | None | ReDoc UI                                        |

## Schemas — `EstimateStayInput`

> Spec §US-2.1.

```json
{
  "villageId": "biarritz",
  "family": {
    "adultes": 2,
    "enfants": [{ "age": 4 }, { "age": 8 }],
    "qfVal": 900,
    "maxiFamily": false
  },
  "sejour": {
    "dateDebut": "2026-07-05",
    "dateFin": "2026-07-12",
    "formule": "PC",
    "fNuits": 7,
    "extras": { "locCleaningFee": 0, "locKits": 0 },
    "activities": { "outings": 2, "priceAdult": 25, "priceChild": 15 },
    "extraActivities": { "paidQtyById": {} },
    "resto": { "qtyByMealId": { "bistrot": 2 } },
    "transport": { "mode": "car", "distanceOneWayKm": 600, "fuel": "essence" },
    "promos": { "promoSejourRate": 0.10, "quinzaineFutee": false, "soloSupplementMode": "default" }
  },
  "_meta": {
    "sessionId": "abc-123-def",
    "stepTimings": { "family": 12400, "sejour": 34200, "extras": 8100, "transport": 5600, "promos": 15300 },
    "villageChanges": ["chamonix", "lacanau", "biarritz"],
    "referrer": "https://www.vtf-vacances.com/fr_FR/",
    "utmSource": "newsletter_mai",
    "deviceType": "mobile",
    "screenWidth": 390
  }
}
```

`_meta` is **optional, ignored by the calculation, but logged** in `SimulationLog`. Adding
it lets us power Phase 2/SVD later without touching the API contract.

## Schemas — `SejourEstimate`

```json
{
  "total": 2847,
  "perPerson": 712,
  "totalAdults": 1134,
  "totalChildren": 680,
  "perAdultBase": 567,
  "childLines": [
    { "age": 4, "discountFraction": 0.4, "amount": 306 },
    { "age": 8, "discountFraction": 0.2, "amount": 374 }
  ],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0.10,
  "staySubtotal": 1858,
  "adhesion": 44,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 160,
  "restoTotal": 152,
  "transportTotal": 228,
  "hotelEstimate": 4210,
  "hotelSavings": 1363,
  "savingsPct": 32.4,
  "bookingUrl": "https://api.example.com/api/v1/go/eyJhbGciOiJIUzI1NiJ9..."
}
```

`bookingUrl` is the **redirect URL** (not the raw VTF URL). It points to `GET /api/v1/go/{token}`
which 302s to VTF and logs the click. Spec §US-2.8.

## Schemas — `BookingLinkInput` / `BookingLinkOutput`

```json
// POST /api/v1/villages/{id}/booking-link
{
  "family": { "adultes": 2, "enfants": [{ "age": 2 }, { "age": 7 }, { "age": 13 }] },
  "dates": { "debut": "2026-07-05", "fin": "2026-07-12" },
  "sessionId": "abc-123-def",
  "source": "estimate",
  "context": {
    "estimatedTotal": 2847,
    "formule": "PC",
    "promosApplied": ["qf_r1", "premiere_minute"],
    "recoStrategy": null,
    "recoScore": null,
    "recoRank": null
  }
}
```

```json
// Response
{
  "redirectUrl": "https://api.example.com/api/v1/go/eyJhbGciOiJIUzI1NiJ9...",
  "token": "eyJhbGciOiJIUzI1NiJ9...",
  "expiresAt": "2026-07-08T23:59:59Z",
  "targetUrl": "https://www.vtf-vacances.com/fr_FR/summer/village-vacances/pyrenees-atlantiques/biarritz/le-domaine-de-francon?…",
  "params": {
    "season": "summer",
    "nbPersons": 5,
    "nbAdults": 2,
    "nbBabies": 0,
    "nbChildren3": 1,
    "nbChildren1": 1,
    "nbChildren2": 1
  }
}
```

## Schemas — `RecommendInput`

> Spec §US-4.1.

```json
{
  "family": {
    "adultes": 2,
    "enfants": [{ "age": 2 }, { "age": 7 }],
    "qfVal": 750,
    "isSoloParent": false
  },
  "preferences": {
    "envs": ["sea", "sun"],
    "formule": "PC",
    "budget": 2500,
    "dates": { "debut": "2026-07-05", "fin": "2026-07-12" },
    "mustHave": ["bebeClub"],
    "avoidSki": true
  },
  "sessionId": "abc-123-def",
  "limit": 6,
  "explain": true
}
```

```json
// Response (always ≥ 1 village)
{
  "villages": [
    {
      "village": { "id": "biarritz", "nom": "Biarritz", "region": "Aquitaine / Landes" },
      "score": 0.92,
      "reasons": [
        "Bord de mer — environnement souhaité",
        "Club bébé dès 4 mois — idéal pour votre enfant de 2 ans",
        "Éligible quotient familial (-17 %)",
        "Dans votre budget (estimé ~2 180 €)"
      ],
      "warnings": [],
      "estimatedTotal": 2180,
      "bookingUrl": "https://api.example.com/api/v1/go/eyJhbGciOiJIUzI1NiJ9..."
    }
  ],
  "strategy": "personalized",
  "confidence": 0.88,
  "totalScored": 32,
  "relaxedFilters": [],
  "fallbackUsed": false
}
```

## Schemas — `InteractionInput`

> Spec §US-3.1. `kind` ∈ `view | simulate | bookmark | rate | click_cta`.

```json
{
  "sessionId": "abc-123-def",
  "villageId": "biarritz",
  "kind": "simulate",
  "metadata": {
    "family": { "adultes": 2, "enfants": 2 },
    "formule": "PC",
    "saison": "ete",
    "estimatedTotal": 2847
  }
}
```

Returns `201 { "id": 42 }`. **Idempotent** for `bookmark` (toggle behavior via separate endpoint if needed).

## Frontend → API signal events

> Mapped to `VillageInteraction` rows or to lightweight log lines.
> Sent via `POST /api/v1/interactions` (canonical for typed events) or `POST /api/v1/signals` (lightweight beacon).

| Signal              | When                                   | Payload                                                         |
|---------------------|----------------------------------------|-----------------------------------------------------------------|
| `session_start`     | App load                               | `{ sessionId, referrer, utmSource, deviceType }`                |
| `village_view`      | User selects a village in dropdown     | `{ sessionId, villageId, stepNumber }`                          |
| `step_complete`     | User advances a step                   | `{ sessionId, step: 'family|sejour|extras|transport|promos', durationMs }` |
| `result_view`       | Results page rendered                  | `{ sessionId, villageId, total, timeToResultMs }`               |
| `result_dwell`      | User leaves results page               | `{ sessionId, villageId, dwellTimeMs, scrollDepthPct }`         |
| `recap_view`        | Recap page opened                      | `{ sessionId, villageId }`                                      |
| `share_click`       | User clicks share/PDF                  | `{ sessionId, villageId, shareMethod: 'pdf|share_api|copy' }`   |
| `compare_villages`  | User changes village mid-flow          | `{ sessionId, fromVillageId, toVillageId }`                     |
| `bookmark`          | Bookmark toggle                        | `{ sessionId, villageId }`                                      |

## §6.1 Error contract

```json
{
  "detail": "Human-readable message",
  "code":   "MACHINE_READABLE_CODE",
  "errors": { "field": ["Validation message"] }
}
```

| Status | When                                                   |
|--------|--------------------------------------------------------|
| 200    | Success                                                |
| 201    | Interaction created                                    |
| 302    | Booking redirect                                       |
| 400    | Invalid input (validation)                             |
| 404    | Village/region not found                               |
| 429    | Rate limit exceeded                                    |
| 500    | Unexpected server error                                |

> ⚠️ **Critical rule**: `POST /recommend/villages` **always returns 200**. Internal failures
> degrade through the waterfall to Tier 5 (hardcoded safety net), never bubble up as 5xx.

## §6.2 Rate limits

| Endpoint group                          | Limit          | Scope    |
|-----------------------------------------|----------------|----------|
| Catalog (`GET`)                         | 1000 / hour    | IP       |
| Pricing (`POST /estimate/*`)            |  200 / hour    | IP       |
| Recommendation (`POST /recommend/*`)    |  100 / hour    | IP       |
| Interaction tracking (`POST /interactions`) | 100 / hour | Session  |
| Booking redirect (`GET /go/*`)          |  500 / hour    | IP       |

Use DRF `AnonRateThrottle` + custom `SessionRateThrottle`.

## §6.3 CORS

Allow origins: `https://vtf-vacances.com`, `https://*.vtf-vacances.com`, `http://localhost:*` (dev only).

## §6.4 Versioning

URL-based: `/api/v1/`. Breaking changes require `/api/v2/` with a documented deprecation
period (3 months minimum, `Sunset` header).

## §6.5 Headers

| Header             | Required?     | Purpose                                                |
|--------------------|---------------|--------------------------------------------------------|
| `X-Session-ID`     | yes (calc, interactions, recommend) | Session tracking (anonymous UUID, set by frontend) |
| `X-Client-Version` | optional      | Analytics, e.g. `simulator-vtf-1.4.2`                  |
| `Accept-Language`  | optional      | Currently `fr-FR` only; reserved for future i18n       |

## OpenAPI

`drf-spectacular` generates the schema. CI fails the build if
`python manage.py spectacular --validate --fail-on-warn` reports errors.

```yaml
# .github/workflows/ci.yml
- run: python manage.py spectacular --validate --fail-on-warn
```

## Acceptance criteria summary (Phase 1, spec §3.5)

| ID       | Criterion                                                       |
|----------|-----------------------------------------------------------------|
| AC-1.1   | All 32 villages loadable via `load_vtf_mocks`                   |
| AC-1.2   | `/villages` returns correct count with each filter              |
| AC-1.3   | `/estimate/stay` matches JS golden master (50 cases, ±1 €)      |
| AC-1.4   | All endpoints have valid OpenAPI documentation                  |
| AC-1.5   | 404 for unknown village/region; 400 for invalid input           |
| AC-1.6   | Catalog endpoints cached (24 h villages, 7 d reference)         |
| AC-1.7   | No N+1 queries (prefetch attractions, activities)               |
| AC-1.8   | Health endpoint returns data version from `PricingRules`        |
| AC-1.9   | Every `/estimate/stay` creates a `SimulationLog` row (async)    |
| AC-1.10  | `SimulationLog` captures family + estimate + promos             |
| AC-1.11  | `_meta.sessionId` propagated to all logs                        |
| AC-1.12  | All 32 villages have `vtf_slug`/`vtf_department`/`vtf_city`     |
| AC-1.13  | Booking redirect logs `BookingClick` with `source` + reco context |
