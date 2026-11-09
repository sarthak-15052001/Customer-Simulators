# 00 — Overview

> Spec source: `VTF Customer Simulators API — Engineering Specification v1.0` (May 2026).
> This doc summarizes §1 (Executive Summary) and §2 (Architecture). For deep dives see
> the per-area docs (`02-…` to `10-…`).

## 1.1 Vision

The frontend simulator (`vtf/front/`) lets a family compute the budget of a VTF stay by
entering family info, dates, formula, extras, and transport mode. All the data and logic
lives client-side in JSON mocks and TypeScript utilities.

The backend (`vtf/api/`) will:

1. **Replace the mocks** with a Django/DRF read-only API serving the catalog.
2. **Centralize the calculation** (port `stayEstimate.ts` to Python) so multiple clients
   (web, mobile, partner integrations) consume identical numbers.
3. **Capture every simulation + booking click** (`SimulationLog`, `BookingClick`) to fuel a
   recommender and measure simulator → booking conversion.
4. **Power a recommender with a 5-tier waterfall** that **never returns empty**
   (Phase 2: content-based, Phase 2+: SVD collaborative filtering as a re-ranker).
5. **Orchestrate cache + scraping** (Phase 3): on-demand Redis rebuilds and TripAdvisor /
   Google Places / OT-local activity discovery with human review.

## 1.2 Success metrics

| Metric                                     | Target                                | Measurement              |
|--------------------------------------------|---------------------------------------|--------------------------|
| API response time (p95)                    | < 200 ms (catalog), < 500 ms (estimates) | APM (Datadog / Sentry) |
| Calculation parity JS ↔ Python             | 100 % match on **golden master** (50 cases) | CI pipeline        |
| Recommendation non-empty rate              | 100 % (zero empty responses)          | Monitoring + tests       |
| Recommendation relevance                   | > 70 % users interact with a rec'd village | Analytics (Phase 2 KPI) |
| API uptime                                 | 99.5 %                                | Health check endpoint    |

## 1.3 Phasing

| Phase | Scope                                                              | Duration | Dependencies                                  |
|-------|--------------------------------------------------------------------|----------|-----------------------------------------------|
| 1     | Catalog + Pricing + Booking redirect + Data collection             | 6 weeks  | Frozen mocks, golden master from JS           |
| 2     | Interaction tracking + Recommendation engine + SVD prep + Analytics + LLM session labeling | 4 weeks  | Phase 1 deployed, frontend integrated         |
| 3     | Redis cache orchestration + Activity scraping + SVD activation     | **3 weeks**  | Phase 2 stable, scraping API keys secured     |

> §1.3 of the spec also lists an "AI-generation" timeline of **4 days for Phase 1** and
> **1 week for Phase 3** — these are the lower bounds when the spec is fed to an AI coding
> agent. Human-validated full rollout is the durations above.

**Build strategy.** Models, serializers, views, and services in Phase 1 are
**AI-generated from this spec**. The spec IS the prompt. Human time is spent on golden
master validation, fixture verification, and deploy — not on writing boilerplate. See
`09-implementation-roadmap.md` §AI Generation Protocol.

## 2.1 System context

```
┌──────────────┐     ┌──────────────────────────────────────────┐
│ VTF Front    │────▶│  Django API (this project)              │
│ (React SPA)  │◀────│                                          │
└──────────────┘     │ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
                     │ │ catalog  │ │ pricing  │ │ Postgres   │ │
┌──────────────┐     │ │ app      │ │ app      │ │ DB         │ │
│ Mobile App   │────▶│ ├──────────┤ ├──────────┤ └────────────┘ │
│ (future)     │◀────│ │ recomm.  │ │ scraper  │ ┌────────────┐ │
└──────────────┘     │ │ app (P2) │ │ app (P3) │ │ Redis      │ │
                     │ └──────────┘ └──────────┘ └────────────┘ │
┌──────────────┐     └──────────────────────────────────────────┘
│ Partner API  │────▶                  ▲
│ (future)     │◀────                  │ Management commands
└──────────────┘                ┌──────┴──────┐
                                │ VTF Mocks   │
                                │ (JSON src)  │
                                └─────────────┘
```

## 2.2 Key design decisions

| Decision                                | Rationale                                                       |
|-----------------------------------------|-----------------------------------------------------------------|
| No authentication for Phase 1           | Simulator is public; rate-limit by IP instead                   |
| Session-based user ID for Phase 2       | Track interactions without login; upgrade to auth later         |
| camelCase in API responses              | Match existing frontend contract; avoid breaking changes        |
| Pure service functions                  | All calculation in `services/`, no business logic in views      |
| Singleton `PricingRules`                | One active ruleset at a time; versioned via `updated_at`        |
| Content-based reco first                | 32 villages = too few for collaborative filtering; CF added later |
| Booking link via signed-token redirect  | Captures every click as a `BookingClick` row (conversion data)  |
| Cache rebuild on signal                 | `PricingRules.save()` and `load_vtf_mocks` auto-warm Redis      |

## Phases

### Phase 1 — API foundations + data collection (6 weeks)

Sprint plan: see `09-implementation-roadmap.md` §6.1.

| Deliverable                                  | Owner    | DoD                                                    |
|----------------------------------------------|----------|--------------------------------------------------------|
| `apps/catalog` (Village, Activity, Pricing)  | Backend  | Fixtures load, `/api/v1/villages` returns 32 entries   |
| `apps/pricing` services (port from TS)       | Backend  | Golden-master tests match JS to the euro (50 cases)    |
| `apps/pricing` `EstimateStayView`            | Backend  | `POST /api/v1/estimate/stay` returns `SejourEstimate`  |
| Booking redirect (`GET /go/{token}` + log)   | Backend  | Click → 302 to VTF + `BookingClick` row                |
| `SimulationLog` model + write on every call  | Backend  | Each estimate produces 1 row                           |
| Frontend signal endpoint `POST /signals`     | Backend  | `session_start`, `village_view`, etc. logged           |
| OpenAPI schema (drf-spectacular)             | Backend  | `/api/schema/` + `/api/docs/` available                |
| Frontend migration (replace mocks → API)     | Frontend | `vtf/front/src/data/*.ts` reads from API client        |

**No recommendation engine in Phase 1.** Just data capture (`SimulationLog`,
`BookingClick`, `VillageInteraction`) so Phase 2 starts with real signals on day 1.

### Phase 2 — Recommendation engine (4 weeks)

- `apps/recommender` with a **5-tier waterfall** (`07-recommendation-engine.md`):
  - **Tier 1**: Personalized content-based scoring
  - **Tier 2**: Relaxed constraints (drop budget filter)
  - **Tier 3**: Region + season only
  - **Tier 4**: Popularity fallback
  - **Tier 5**: Hardcoded safety net (works even with empty DB)
- Endpoint: `POST /api/v1/recommend/villages` — **always returns ≥1 village**.
- `GET /api/v1/villages/{id}/similar` for "similar villages" widget.
- Tunable weights (`RecoWeights` model, admin-editable without deploy).

### Phase 2+ — SVD collaborative filtering

Activates when thresholds met (env: `RECO_MIN_CF_INTERACTIONS=500`):
- ≥ 500 simulations · ≥ 100 unique sessions · ≥ 50 multi-village sessions · ≥ 20 villages with ≥10 sims.

Trained nightly with `surprise.SVD`, used as a **re-ranker**: `score = 0.7 × content + 0.3 × CF`.

### Phase 3 — Cache + scraping (3 weeks)

- **Cache orchestrator**: admin endpoint `POST /api/v1/admin/cache/rebuild` with
  scopes `all|catalog|pricing|villages:{id}|regions:{key}|recommendations|booking_urls`.
  Auto-rebuild on `PricingRules.save()` and after `load_vtf_mocks`.
- **Scraping engine**: Google Places + TripAdvisor + OT local adapters →
  `ScrapingCandidate` staging → human review → upsert into `Activity`.
- **Price-change alerts** when re-scraping detects > 10 % delta on existing activities.
- **SVD activation**: collaborative-filtering re-ranker auto-enables when
  `SimulationLog` reaches the gates (see `07-recommendation-engine.md` §9).

## Non-goals

- ❌ Authentication / user accounts (Phase 1 — sessions are anonymous via `X-Session-ID` header).
- ❌ Booking flow (we redirect to vtf-vacances.com).
- ❌ Payment.
- ❌ I18n on the API (all FR for now; the frontend handles i18n already).

## Architectural choices

| Choice                                     | Why                                                  |
|--------------------------------------------|------------------------------------------------------|
| Django + DRF (not FastAPI)                 | Admin, ORM, migrations, batteries-included for ops   |
| `JSONField` for `tarifs`                   | Stays close to source mock; tarifs evolve as a unit  |
| `SimulationLog` from Phase 1 (not Phase 2) | Cold-start data for SVD; otherwise we'd wait months  |
| Surprise (not TF/PyTorch) for SVD          | Tiny dataset (~32 villages); CPU-only; ships in 50KB |
| Anonymous sessions (no login)              | Match current frontend; no PII                       |

## Risks

| Risk                                       | Mitigation                                           |
|--------------------------------------------|------------------------------------------------------|
| JS↔Python rounding/calc divergence         | Golden-master tests, CI runs both runtimes           |
| Mocks drift between front & api            | Single management command, CI assert sha256 match    |
| Frontend breaking change on cutover        | Keep camelCase JSON, feature flag on env var         |
| GDPR (logging IP, UA)                      | Hash IP, truncate UA, 90-day retention by default    |
| VTF URL slugs change (booking redirect)    | `verify_vtf_urls` cron + alert                       |
