# 09 — Implementation roadmap

> Spec source: §6 (Migration playbook) + §7 (AI generation protocol).
>
> Sequenced delivery plan. Each milestone has a Definition of Done (DoD).
> Run linter + tests + OpenAPI validation at every step.

## Sprint plan (spec §6.1–6.3)

### Phase 1 — 6 weeks

| Week | Focus                                | Deliverables                                                                                          |
|------|--------------------------------------|-------------------------------------------------------------------------------------------------------|
| 1    | Project setup + data models         | Django project, models, migrations, `load_vtf_mocks` command, 32 villages loaded                      |
| 2    | Catalog API                         | All `GET` endpoints, serializers, filters, pagination, OpenAPI spec                                   |
| 3    | Pricing services (port from JS)     | `transport.py`, `qf.py`, `resto.py`, `promos.py`, `hotel_comparison.py` + unit tests                  |
| 4    | Core estimation service             | `stay_estimate.py` — full port with golden master tests (50 cases)                                    |
| 5    | Integration + frontend switchover   | API integration tests, frontend migration (replace mock imports with API calls), booking redirect     |
| 6    | Polish + deploy                     | Caching, rate limiting, CORS, staging deploy, load testing, documentation                             |

### Phase 2 — 4 weeks

| Week | Focus                              | Deliverables                                                                              |
|------|------------------------------------|-------------------------------------------------------------------------------------------|
| 7    | Interaction tracking              | `VillageInteraction` model, `POST /interactions`, rate limiting                           |
| 8    | Recommendation engine             | Content-based strategy, waterfall orchestrator, core `/recommend/villages`                |
| 9    | Fallback chain + similar villages | All 5 tiers tested, `VillagePopularityCache`, `/villages/{id}/similar`                    |
| 10   | Analytics + weights tuning        | Admin stats endpoint, `RecoWeights` admin, monitoring, production deploy                  |

### Phase 3 — 3 weeks

> Spec §5 says "Duration: 3 weeks". Spec §7.3 lists a compressed 5-day "AI-generated"
> baseline (1-2 cache, 3-4 scraping, 5 review+deploy) — that's the floor for an AI
> coding agent generating skeleton code. Below is the human-validated 3-week rollout.

| Week | Focus                                  | Deliverables                                                                                              |
|------|----------------------------------------|-----------------------------------------------------------------------------------------------------------|
| 1    | Redis cache orchestration              | `CacheOrchestrator` service, key registry, admin `/cache/rebuild`, auto-warm signals (`PricingRules.save`, `load_vtf_mocks`), health-endpoint cache stats, signal-driven scope rebuilds |
| 2    | Scraping engine + adapters             | TripAdvisor + Google Places + OT-local adapters, `ScrapingJob`/`ScrapingCandidate`/`PriceChangeAlert` models, dedup engine (`match_confidence` formula), monthly cron, async job runner |
| 3    | Review workflow + SVD activation + deploy | Admin import/reject flow, price-change Slack notifications, `train_cf_model` + `check_cf_readiness` daily cron, A/B test setup, weight tuning grid search (`tune_reco_weights`), production deploy |

## Milestone 0 — Bootstrap (½ day)

**Goal:** empty Django project with DRF + spectacular + Postgres + Redis.

### Tasks

- [ ] Create `vtf/api/pyproject.toml` (Poetry or uv).
- [ ] Pin: `django>=4.2`, `djangorestframework`, `drf-spectacular`, `django-redis`, `psycopg[binary]`, `requests`, `rapidfuzz` (Phase 3 prep).
- [ ] Dev deps: `pytest`, `pytest-django`, `pytest-cov`, `ruff`, `mypy`, `factory-boy`.
- [ ] Generate skeleton: `django-admin startproject config .` then `python manage.py startapp catalog --directory apps/catalog` etc.
- [ ] Configure `config/settings/{base,dev,prod}.py`.
- [ ] Create `Makefile` with `make dev`, `make test`, `make lint`, `make schema`.
- [ ] Add `.env.example`, `.dockerignore`, `Dockerfile` (Python 3.11 slim).

### DoD

- `make test` passes (no tests yet, just framework ready).
- `python manage.py runserver` serves `/api/docs/` (empty Swagger).
- `python manage.py migrate` creates schema in dev DB.

## Milestone 1 — Catalog (1 day)

**Goal:** read-only catalog mirrors the JSON mocks.

### Tasks

- [ ] Models: `Village`, `Attraction`, `Activity`, `Animation`, `VillageInfra`, `VillageClubsEte`, `PricingRules`, `Meal`, `FuelOption`, `Promo`.
- [ ] Migrations: `python manage.py makemigrations catalog`.
- [ ] Management command: `apps/catalog/management/commands/load_vtf_mocks.py`. Loads from `vtf/front/src/mocks/*.json` (path configurable).
- [ ] Re-key `attractionsProches` from `nom` → `village_id` during load.
- [ ] Compute `env_code` from `env_emoji` during load.
- [ ] Map VTF URL fields from `02-fixtures-mapping.md`.
- [ ] Serializers: `VillageListSerializer`, `VillageDetailSerializer`, etc. — **camelCase output**.
- [ ] Views: `ReadOnlyModelViewSet` for `villages`, `activities`. `RetrieveAPIView` for `pricing-rules`.
- [ ] URLs.
- [ ] Tests: load mocks, hit each endpoint, snapshot response shape.

### DoD

- `python manage.py load_vtf_mocks --src ../front/src/mocks` loads 32 villages.
- `GET /api/v1/villages` returns 32 entries (camelCase).
- `GET /api/v1/villages/biarritz` returns village + attractions + infra + clubs.
- `GET /api/v1/pricing-rules` returns the active singleton.
- OpenAPI schema includes all catalog endpoints.

## Milestone 2 — Pricing services (port from TS) (2-3 days)

**Goal:** every util function in `vtf/front/src/utils/` is reproduced in Python.

### Order (follow dependency graph)

1. `family.py`, `qf.py` (no deps)
2. `calendar.py` (no deps; includes `parse_ouverture`)
3. `transport.py`, `resto.py` (no deps)
4. `promos.py` (no deps; takes `now: date`)
5. `hotel.py` (deps on saison)
6. `stay_estimate.py` (deps on all of the above) — last, hardest

### Tests strategy

- Unit tests for each pure function.
- **Golden master** for `stay_estimate`:
  - Write a Node script that calls JS `estimateSejourTotal` on 20 cases.
  - Save inputs/outputs to `vtf/api/tests/golden/cases.json`.
  - Pytest asserts Python output == JS output to the euro for every case.

### DoD

- 90%+ coverage on `apps/pricing/services/`.
- Golden master test passes.
- `ruff check` clean.

## Milestone 3 — Calculation API (1 day)

**Goal:** the frontend can call `POST /api/v1/estimate/stay`.

### Tasks

- [ ] Input serializers: `EstimateStayInputSerializer`, `FamilySerializer`, `SejourSerializer`.
  - Validate `dateFin > dateDebut`, `formule` ∈ enum, etc.
- [ ] `EstimateStayView` (`APIView`).
  - Loads `Village.objects.values().get(pk=...)`.
  - Loads active `PricingRules` (cached).
  - Calls `estimate_sejour_total`.
  - Returns 400 if estimation impossible (no tarif for saison/formule).
- [ ] Other calc endpoints (`/promos/available`, `/transport/car`, `/transport/train`, `/family/qf`, `/resto/total`, `/stay/days`, `/season`).
- [ ] OpenAPI: enrich each endpoint with `OpenApiExample` so consumers see realistic samples.

### DoD

- Frontend (`vtf/front/`) can swap `estimateSejourTotal()` for a call to the API and produce the same numbers.
- `POST /api/v1/estimate/stay` works with the schema in `05-api-endpoints.md`.

## Milestone 4 — Data collection (½ day)

**Goal:** every estimate is logged; lightweight signals captured.

### Tasks

- [ ] `SimulationLog`, `BookingClick`, `VillageInteraction` models + migrations.
- [ ] `transaction.on_commit` write inside `EstimateStayView`.
- [ ] `BookingRedirectView` (`GET /api/v1/villages/{id}/booking-url`):
  - Build URL, log `BookingClick`, mark latest matching `SimulationLog.clicked_booking = True`.
  - Returns the URL (frontend redirects).
- [ ] `SignalView` (`POST /api/v1/signals`):
  - Validate `kind` in allowed set.
  - INSERT `VillageInteraction` row.
  - Returns `204`.
- [ ] Frontend instrumentation: add `vtf/front/src/api/signals.ts` helper, wire into key UI events.

### DoD

- Each `/estimate/stay` call produces 1 `SimulationLog`.
- A test session that books generates 1 `SimulationLog` + 1 `BookingClick` + ≥3 `VillageInteraction`.
- Privacy: `ip_hash` is sha256, no plain IP stored.

## Milestone 5 — Frontend cutover (1 day, frontend team)

**Goal:** `vtf/front/` reads from API instead of JSON mocks.

### Tasks

- [ ] Generate TS types from OpenAPI (`openapi-typescript`) → `vtf/front/src/api/schema.d.ts`.
- [ ] Tiny client (`vtf/front/src/api/client.ts`) — fetch wrapper with `X-Session-ID` header.
- [ ] Replace `import { VTF_VILLAGES } from '../data/vtfStay'` with `client.getVillages()`.
- [ ] Replace `estimateSejourTotal(...)` calls with `client.estimateStay(...)`.
- [ ] Feature flag (`VITE_USE_API`) for staged rollout.
- [ ] Smoke test: identical numbers between mock and API mode (use the golden cases).

### DoD

- Frontend works with `VITE_USE_API=true`.
- Lighthouse score not regressed.
- Network tab shows `/api/v1/*` calls, not local JSON.

## Milestone 6 — Phase 2: content-based recommender (2 days)

**Goal:** `POST /api/v1/recommendations` returns ranked villages from family + preferences.

### Tasks

- [ ] `apps/recommender/` skeleton.
- [ ] Define preferences schema: `{ env: SeaSpot|Mountain|..., wantsSki: bool, wantsPool: bool, wantsBebeClub: bool, distanceMaxKm?: number }`.
- [ ] Scoring function in `apps/recommender/strategies/content_based.py`:
  - Score = weighted match between family attrs (qf, ages) and village flags (qfExc, bebeClub, hasLoc).
  - Reasons emitted alongside the score (for `?explain=true`).
- [ ] Fallback chain (popular → regional → random).
- [ ] Endpoint + serializer + tests (snapshot top-6 for fixed personas).

### DoD

- Recommendation latency < 100ms (p95).
- Determinism: same inputs → same outputs.
- 5 personas have snapshot tests.

## Milestone 7 — Phase 2+: SVD activation (1 day, conditional on data threshold)

**Goal:** when threshold met, blend CF into recommendations and A/B test.

See `07-svd-roadmap.md` for code. Tasks:

- [ ] `apps/recommender/strategies/collaborative.py`.
- [ ] `train_cf_model` management command (cron 03:00 daily).
- [ ] `check_cf_readiness` management command (sets feature flag).
- [ ] Re-rank in `recommend()` with 70/30 blend.
- [ ] A/B split + log `ab_group` in `SimulationLog`.

### DoD

- Threshold met → SVD model trained nightly.
- Recommendation strategy returned in response (`personalized` vs `personalized_cf`).
- Dashboards show booking CTR per cohort.

## Milestone 8 — Phase 3: cache + scraping (2-3 days)

See `08-cache-and-scraping.md`. Tasks:

- [ ] `apps/cache_orchestrator/` (key registry, service, signals, admin endpoint, mgmt cmd).
- [ ] `apps/scraper/` (adapters ABC + Google Places adapter as MVP, dedup, candidates, alerts).
- [ ] Admin UI for reviewing candidates.

### DoD

- `PricingRules.save()` invalidates `vtf:catalog:*`.
- `python manage.py scrape_activities --region "Aquitaine / Landes"` produces ≥1 candidate.
- Promote action moves candidate to `Activity`.

## Cross-cutting concerns (every milestone)

| Concern         | Approach                                                              |
|-----------------|-----------------------------------------------------------------------|
| Logging         | Structured JSON via `python-json-logger`. `request_id` per request.   |
| Error reporting | Sentry. Tag with `app`, `version`, `session_id`.                      |
| Observability   | Prometheus metrics (request counts, latency, cache hits).             |
| Security        | CORS allowlist, CSRF off (read-only-public + session header).         |
| Throttling      | DRF `AnonRateThrottle` (`60/min`) on calc endpoints.                  |
| CI              | `make lint test schema` on every PR. Block on red.                    |
| Deploy          | Docker image, `gunicorn` + `uvicorn worker` (or `daphne` if WS later).|

## Out-of-scope reminder

- ❌ User auth / accounts (Phase 1).
- ❌ Multi-language API (FR only for now; the frontend handles i18n).
- ❌ Booking flow (we redirect to vtf-vacances.com).
- ❌ Payments.

## Suggested team / pairing

| Phase                   | Effort | Skills                                  |
|-------------------------|--------|-----------------------------------------|
| Milestone 0–4 (Phase 1) | ~5 days | 1 Python backend dev                    |
| Milestone 5 (cutover)   | ~1 day | 1 frontend dev                          |
| Milestone 6 (CB reco)   | ~2 days | 1 backend + 1 PM (preference taxonomy)  |
| Milestone 7 (SVD)       | ~1 day | 1 data scientist                        |
| Milestone 8 (cache+scrape) | ~3 days | 1 backend dev + 1 ops                |
| **Total Phase 1+2**     | **~9 days** | 1 backend + small frontend slot      |

## AI generation protocol (spec §7.4)

This spec is designed to be fed **directly to an AI coding agent**. Each section maps to
a generation task. Human time is spent validating, not writing boilerplate.

### Day 1 — Bootstrap

```
claude "Read vtf/api/docs/. Generate the complete Django project:
  - All models from 03-data-models.md
  - All enums (Region, Saison, Formule, FuelKey, EnvKey)
  - load_vtf_mocks management command from 02-fixtures-mapping.md
  - Migrations
  Output to vtf/api/ directory."
```

### Day 2 — Catalog + Pricing

```
claude "Using the models already generated, create:
  - All serializers from 05-api-endpoints.md
  - All ViewSets and APIViews from 05-api-endpoints.md endpoint table
  - All pricing services by porting the TypeScript from vtf/front/src/utils/
    (mapping in 01-frontend-source-of-truth.md)
  - URL routing
  Wire everything up. Run tests."
```

### Day 3 — Validation + redirect

```
claude "Port stayEstimate.ts line-by-line to apps/pricing/services/stay_estimate.py.
  Here is the JS source: [paste vtf/front/src/utils/stayEstimate.ts]
  Here are 50 golden master test cases: [paste tests/golden/cases.json]
  Implement the booking redirect flow per 11-booking-redirect.md.
  Make all tests pass within ±1 € tolerance."
```

### What AI generates vs what humans validate

| AI generates (≈ 90 % of code)    | Human validates (≈ 10 % of time)                                |
|----------------------------------|-----------------------------------------------------------------|
| Models, migrations               | Check field types match audit                                   |
| Serializers                      | Verify camelCase output matches frontend types                  |
| ViewSets, filters, pagination    | Spot-check query performance (N+1)                              |
| Service functions (port from JS) | Run golden master, fix rounding edge cases                      |
| URL routing                      | Verify OpenAPI spec is clean                                    |
| Management commands              | Run `load_vtf_mocks`, check counts                              |
| Test suites                      | Review coverage, add edge cases                                 |
| Docker / deploy config           | Run staging deploy, smoke test                                  |
| Booking redirect service         | Click through, verify VTF page loads with params                |

## Frontend migration checklist (spec §6.3)

| Current import                                                            | Replaced by                                              | When     |
|---------------------------------------------------------------------------|----------------------------------------------------------|----------|
| `import villages from 'mocks/vtfStay.mock.json'`                          | `GET /api/v1/villages`                                   | Week 5   |
| `import extras from 'mocks/vtfExtras.mock.json'`                          | `GET /api/v1/regions/{r}/activities`                     | Week 5   |
| `import rules from 'mocks/vtfPricingRules.mock.json'`                     | `GET /api/v1/pricing-rules`                              | Week 5   |
| `import { estimateSejourTotal } from 'utils/stayEstimate'`                | `POST /api/v1/estimate/stay`                             | Week 5   |
| `import { carCostBreakdown } from 'utils/transportTab'`                   | `POST /api/v1/transport/car`                             | Week 5   |
| `import { calcQfFromIncomeParts } from 'utils/qfCalc'`                    | `POST /api/v1/family/qf`                                 | Week 5   |
| (new)                                                                     | `POST /api/v1/recommend/villages`                        | Week 9   |
| (new)                                                                     | `POST /api/v1/interactions`                              | Week 9   |
| (new)                                                                     | `POST /api/v1/admin/cache/rebuild`                       | Phase 3  |
| (new)                                                                     | `POST /api/v1/admin/scraper/activities`                  | Phase 3  |
