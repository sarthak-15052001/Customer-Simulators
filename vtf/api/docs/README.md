# `vtf/api/` — Documentation index

This folder contains everything needed to **build the Django backend** that will replace
the frontend mocks in `vtf/front/src/mocks/*.json` and centralize the calculation logic
currently in `vtf/front/src/utils/*.ts`.

> ⚠️ **No code here yet.** This is a docs-only folder until Phase 1 starts (see Milestone 0
> in `09-implementation-roadmap.md`). The frontend in `vtf/front/` is the **source of truth**
> for all business logic.

## Reading order

| #   | Doc                                                              | Audience              | Purpose                                                       |
|-----|------------------------------------------------------------------|-----------------------|---------------------------------------------------------------|
| –   | [`CLAUDE.md`](./CLAUDE.md)                                       | Claude Code           | Quick-start for AI coding sessions                            |
| 0   | [`00-overview.md`](./00-overview.md)                             | Everyone              | Vision, success metrics, phasing, key decisions               |
| 1   | [`01-frontend-source-of-truth.md`](./01-frontend-source-of-truth.md) | Backend dev      | What to port from `vtf/front/` (mocks + utils + types)        |
| 2   | [`02-fixtures-mapping.md`](./02-fixtures-mapping.md)             | Backend dev          | 32 villages → VTF URL mapping + URL builder + child-age buckets |
| 3   | [`03-data-models.md`](./03-data-models.md)                       | Backend dev          | Django ORM models for catalog, pricing, recommender, scraper, cache |
| 4   | [`04-services.md`](./04-services.md)                             | Backend dev          | Pricing/calculation services porting + booking URL service     |
| 5   | [`05-api-endpoints.md`](./05-api-endpoints.md)                   | Backend + Frontend   | REST endpoints contract (catalog, pricing, reco, admin, system) |
| 6   | [`06-data-collection-strategy.md`](./06-data-collection-strategy.md) | Backend + Data   | What to log to power Phase 2 reco                             |
| 7   | [`07-recommendation-engine.md`](./07-recommendation-engine.md)   | Backend + Data       | 5-tier waterfall, content-based scoring, SVD activation       |
| 8   | [`08-cache-and-scraping.md`](./08-cache-and-scraping.md)         | Backend / DevOps     | Redis cache orchestrator + activity scraping pipeline (Phase 3) |
| 9   | [`09-implementation-roadmap.md`](./09-implementation-roadmap.md) | Tech lead            | Sprint plan, AI generation protocol, frontend migration       |
| 10  | [`10-config-and-reference.md`](./10-config-and-reference.md)     | Ops + Backend        | Env vars, management commands, glossary, open questions, CI   |
| 11  | [`11-booking-redirect.md`](./11-booking-redirect.md)             | Backend + Product    | Token-based redirect service for conversion tracking          |

## Spec source

These docs are derived from **VTF Customer Simulators API — Engineering Specification v1.0
(May 2026)**. Section references in each doc point back to spec §x.y for traceability.

The spec is intended to be fed directly to an AI coding agent (see §9 §AI Generation Protocol).

## Glossary (quick lookup — full version in `10-config-and-reference.md`)

- **VTF** — Vacances Tourisme Familles (operator)
- **Village** — Holiday resort (32 in catalog)
- **Formule** — Stay format: `PC` (full board) · `DP` (half board) · `LOC` (rental)
- **Saison** — Season: `hs` (off) · `vs` (school holidays) · `ete` (summer) · `fetes` (year-end)
- **QF** — Quotient familial (CAF income index, drives discounts)
- **SVD** — Singular Value Decomposition (collaborative filtering for recommendations)
- **SimulationLog** — Server-side row created on every `/estimate/stay` call, primary data source for Phase 2
- **BookingClick** — Server-side row created on every booking redirect, strongest implicit signal for the recommender
- **Waterfall** — 5-tier cascading recommendation strategy that **never returns empty**
