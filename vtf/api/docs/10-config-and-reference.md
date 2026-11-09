# 10 — Config & reference

> Spec source: §8 (Appendices) — env vars, management commands, glossary, open questions.

## 1. Environment variables (spec §8.1)

| Variable                        | Required          | Default                       | Notes                                                       |
|---------------------------------|-------------------|-------------------------------|-------------------------------------------------------------|
| `DATABASE_URL`                  | yes               | —                             | PostgreSQL connection (`postgres://…`). SQLite OK in dev.   |
| `DJANGO_SECRET_KEY`             | yes               | —                             | Generate with `python -c 'import secrets; print(secrets.token_urlsafe(64))'` |
| `DJANGO_DEBUG`                  | no                | `False`                       |                                                             |
| `ALLOWED_HOSTS`                 | yes               | —                             | Comma-separated                                             |
| `CORS_ALLOWED_ORIGINS`          | yes               | —                             | Comma-separated                                             |
| `CACHE_URL`                     | no                | `locmem://`                   | Redis URL for production (`redis://redis:6379/0`)           |
| `BOOKING_REDIRECT_SECRET`       | yes               | —                             | HMAC key for `/go/{token}` (rotate quarterly)               |
| `BOOKING_TOKEN_TTL_HOURS`       | no                | `72`                          | Booking redirect token expiry                               |
| `RECO_MIN_CF_INTERACTIONS`      | no                | `500`                         | Threshold to enable collaborative filtering                  |
| `OLLAMA_BASE_URL`               | Phase 2           | `http://localhost:11434`      | Local LLM endpoint for session labeling                     |
| `OLLAMA_LABEL_MODEL`            | Phase 2           | `mistral`                     | Model name (`mistral`, `phi3`, `llama3.1`)                  |
| `MISTRAL_API_KEY`               | Phase 2 (opt.)    | —                             | Cloud fallback when Ollama is down                          |
| `SESSION_LABELING_ENABLED`      | Phase 2           | `false`                       | Feature flag — enable rule-based session labels             |
| `SESSION_LABELING_USE_LLM`      | Phase 2           | `false`                       | Feature flag — also enrich labels via LLM                   |
| `GOOGLE_PLACES_API_KEY`         | Phase 3           | —                             | Activity enrichment (Text Search + Nearby fallback)          |
| `TRIPADVISOR_API_KEY`           | Phase 3           | —                             | TripAdvisor Content API (partnership required)              |
| `ANTHROPIC_API_KEY`             | Phase 3 (opt.)    | —                             | Claude API for activity classification + price estimation   |
| `SCRAPER_NOTIFY_SLACK_WEBHOOK`  | no                | —                             | Slack webhook for scraping alerts                           |
| `SCRAPER_MONTHLY_CRON`          | no                | `true`                        | Enable / disable monthly auto-scrape                        |
| `CACHE_REBUILD_NOTIFY`          | no                | `false`                       | Send notification on cache rebuild                          |
| `SECRET_IP_SALT`                | yes               | —                             | Used to hash IP addresses (rotate yearly)                   |

`.env.example` should ship in `vtf/api/` with placeholder values.

## 2. Management commands (spec §8.2)

| Command                                            | Phase | Purpose                                                                   |
|----------------------------------------------------|-------|---------------------------------------------------------------------------|
| `load_vtf_mocks --src=PATH`                        | 1     | Load mocks + VTF URL fixtures into DB (idempotent, transactional)         |
| `verify_vtf_urls`                                  | 1     | Hit each village's VTF URL, report 200/404                                |
| `export_golden_master --out=PATH`                  | 1     | Generate golden master JSON from current JS (Node script wrapper)         |
| `simulation_stats --period=30d`                    | 1     | Report simulation counts per village, conversion rates                    |
| `refresh_popularity`                               | 2     | Refresh `VillagePopularityCache` (cron 6 h)                               |
| `check_cf_readiness`                               | 2     | Check if SVD thresholds met, set feature flag                             |
| `train_cf_model`                                   | 2+    | Train Surprise SVD from `SimulationLog` (cron daily 03:00)                |
| `tune_reco_weights`                                | 2+    | Monthly grid search: optimize 7 scoring weights from booking-click data   |
| `label_sessions [--use-llm]`                       | 2     | Compute rule-based labels (and optional LLM enrichment) on `SimulationLog`/`VillageInteraction` rows |
| `cleanup_interactions --days=90`                   | 2     | Archive old interactions                                                  |
| `rebuild_cache --scope=all`                        | 3     | CLI trigger for cache rebuild (same as admin endpoint)                    |
| `scrape_activities --village=biarritz`             | 3     | Scrape activities for one village                                         |
| `scrape_activities --all --notify`                 | 3     | Monthly cron: scrape all 32 villages, notify staff                        |
| `review_scraping_candidates`                       | 3     | List pending candidates for review                                        |

## 3. Cron schedule

| Command                                  | Schedule              | Owner       |
|------------------------------------------|-----------------------|-------------|
| `verify_vtf_urls`                        | Weekly Sunday 02:00   | Ops         |
| `refresh_popularity`                     | Every 6 hours         | Backend     |
| `check_cf_readiness`                     | Daily 02:30           | Backend     |
| `train_cf_model`                         | Daily 03:00           | Backend     |
| `label_sessions --use-llm`               | Hourly                | Backend     |
| `tune_reco_weights`                      | Monthly 1st 02:00     | Backend     |
| `cleanup_interactions --days=90`         | Weekly Sunday 04:00   | Ops         |
| `scrape_activities --all --notify`       | Monthly 1st 04:00     | Ops         |

## 4. Glossary (spec §8.3)

| Term                | Definition                                                                |
|---------------------|---------------------------------------------------------------------------|
| **VTF**             | Vacances Tourisme Familles (operator)                                     |
| **Village**         | Holiday resort (32 in catalog)                                            |
| **PC**              | Pension Complète — full board (3 meals/day + activities + clubs)          |
| **DP**              | Demi-Pension — half board (breakfast + dinner)                            |
| **LOC**             | Location — accommodation only                                              |
| **Saison**          | Season key: `hs` (off) · `vs` (school holidays) · `ete` (summer) · `fetes` (year-end) |
| **QF**              | Quotient Familial — CAF income index that drives social pricing tiers     |
| **Quinzaine futée** | -10 % discount for 14+ night stays in PC formule                          |
| **Maxi-famille**    | -20 % on children if family has ≥ 3 kids and `maxiFamily=true`            |
| **Bébé club**       | Childcare from 4 months — only available in some villages                  |
| **Forfait RM**      | Ski-lift pass included in package (only some villages)                    |
| **QF exclusif**     | Some villages have reduced QF discount (10 %/5 % vs standard 17 %/10 %)   |
| **Solo half**       | Some villages offer -50 % on children for solo parents (summer only)      |
| **Golden master**   | Snapshot of JS calculation outputs used to validate the Python port       |
| **Waterfall**       | Cascading recommendation strategy chain ensuring non-empty results        |
| **Confidence**      | 0–1 score indicating how well the recommendation matches user intent      |
| **CF / SVD**        | Collaborative Filtering / Singular Value Decomposition (Surprise library) |

## 5. Open questions (spec §8.4)

| #   | Question                                                                                      | Owner       | Status                                                          |
|-----|-----------------------------------------------------------------------------------------------|-------------|-----------------------------------------------------------------|
| 1   | Should the API require authentication for estimation endpoints?                              | Product     | **Decided: No** for Phase 1; revisit Phase 3                    |
| 2   | i18n: should the API return labels in French only, or accept `Accept-Language`?              | Product     | **Pending** — French-only for Phase 1                           |
| 3   | Should `estimatedTotal` in recommendations use a full or lightweight estimate?               | Engineering | **Decided: Lightweight** (skip transport/resto for ranking)     |
| 4   | How to handle `vtfInfra` and `vtfClubsEte` — only 1 village populated?                       | Data        | **Block: need VTF to provide complete data**                    |
| 5   | Rate limiting strategy for public API without auth?                                          | Engineering | **Decided: IP-based + session-based for interactions**          |
| 6   | Use Claude API to classify scraped activity types (museum/sport/nature/park)?                | Engineering | Phase 3 optional — `ANTHROPIC_API_KEY`                          |
| 7   | Retention policy for `BookingClick`?                                                          | Legal       | **Pending** — default: 90 d hot, 1 y aggregated                 |
| 8   | Should we store user agents in plain text or fingerprint them?                               | Privacy     | **Decided: Plain text truncated to 256 char** (no PII risk)     |

## 6. CI pipeline (spec §7.4)

```yaml
# .github/workflows/ci.yml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres: { image: postgres:16-alpine }
      redis:    { image: redis:7-alpine }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r vtf/api/requirements.txt
      - run: cd vtf/api && python manage.py migrate
      - run: cd vtf/api && pytest apps/ --tb=short -q
      - run: cd vtf/api && pytest tests/golden_master/ -v
      - run: cd vtf/api && pytest tests/reco_fuzzing/ -v
      - run: cd vtf/api && python manage.py spectacular --validate --fail-on-warn
      - run: cd vtf/api && ruff check apps/
      - run: cd vtf/api && mypy apps/
```

## 7. Monitoring (spec §6.5)

- **Health**: `GET /api/v1/health` — DB connectivity, data version, uptime, cache stats.
- **Metrics**: response time, error rate, cache hit rate per endpoint (Prometheus / Datadog).
- **Alerts**:
  - **Empty recommendation response** → page on-call (should never happen, AC-2.1)
  - **PricingRules missing** → page on-call
  - **p95 latency > 1 s** on calc endpoints
  - **Cache hit rate < 80 %** → investigate
  - **Booking redirect 5xx rate > 1 %** → investigate token signing

## 8. Test pyramid (spec §7.1)

```
       ┌──────────┐
       │ E2E (5)  │            Cypress / Playwright: full simulator flow
       ├──────────┤
   ┌───┤ API (30) ├───┐        DRF test client: endpoint contracts
   │   ├──────────┤   │
┌──┤Integration   ├──┐│        Django TestCase: DB + services
│  │   (40)       │  ││
│  │ ┌────────────┐  ││
│  │ │ Unit (100+)│  ││        pytest: pure service functions
└──┴─┴────────────┴──┴┘
```

| Layer       | Count target | Tools                            | Runtime    |
|-------------|--------------|----------------------------------|------------|
| Unit        | 100+         | pytest, pure functions           | < 30 s     |
| Integration | 40           | Django TestCase, DB              | < 2 min    |
| API         | 30           | DRF APIClient, end-to-end routes | < 3 min    |
| Golden master | 50         | pytest parametrize on JSON cases | < 1 min    |
| Reco fuzzing | 100         | random inputs, AC-2.1            | < 30 s     |
| E2E         | 5            | Playwright, full browser flow    | < 10 min   |
