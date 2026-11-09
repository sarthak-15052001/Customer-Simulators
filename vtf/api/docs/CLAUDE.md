# `CLAUDE.md` — Quick reference for Claude Code

> Read this **first** if you are an AI assistant working on `vtf/api/`.
> It tells you where things live, what conventions to follow, and how to verify your work.

## TL;DR

- The **frontend** in `../front/src/` is the **source of truth**. The API ports JS → Python.
- The **mocks** in `../front/src/mocks/*.json` become **fixtures** loaded into Django.
- The **utils** in `../front/src/utils/*.ts` become **services** in `apps/pricing/services/`.
- **Never** invent business rules. If unclear, read the TS code (`../front/src/utils/stayEstimate.ts`).
- All sums of money are **integer euros** (`Math.round` at the end of each calc).
- Dates are ISO `YYYY-MM-DD` (no timezone). Use Python `date`, not `datetime`.
- API key naming = camelCase in JSON I/O (frontend compat). Snake_case in Python ORM.

## Where things live

| Concern                            | Frontend path (read-only)                  | Backend path (to create)                  |
|------------------------------------|--------------------------------------------|-------------------------------------------|
| Village catalog                    | `../front/src/mocks/vtfStay.mock.json`     | `apps/catalog/fixtures/villages.json`     |
| Activities (free + paid)           | `../front/src/mocks/vtfExtras.mock.json`   | `apps/catalog/fixtures/activities.json`   |
| Pricing rules                      | `../front/src/mocks/vtfPricingRules.mock.json` | `apps/catalog/fixtures/pricing_rules.json` |
| VTF URL mapping (32 villages)      | (none)                                     | `apps/catalog/fixtures/vtf_url_mapping.json` (see `02-fixtures-mapping.md`) |
| Stay estimate logic                | `../front/src/utils/stayEstimate.ts`       | `apps/pricing/services/stay_estimate.py`  |
| Hotel comparison                   | `../front/src/utils/viewDetails.ts`        | `apps/pricing/services/hotel.py`          |
| Promo eligibility                  | `../front/src/utils/promosTab.ts`          | `apps/pricing/services/promos.py`         |
| Transport (car/train)              | `../front/src/utils/transportTab.ts`       | `apps/pricing/services/transport.py`      |
| Resto                              | `../front/src/utils/restoTab.ts`           | `apps/pricing/services/resto.py`          |
| QF computation                     | `../front/src/utils/qfCalc.ts`             | `apps/pricing/services/qf.py`             |
| Calendar / season                  | `../front/src/utils/stayTab.ts`            | `apps/pricing/services/calendar.py`       |
| Highlights                         | `../front/src/utils/stayTab.ts:getHighlights` | `apps/catalog/services/highlights.py`  |
| Booking URL builder + tokens       | (none — new service)                       | `apps/pricing/services/booking_url.py` + `booking_redirect.py` |
| Types (state shape)                | `../front/src/types/*.ts`                  | DRF serializers in each app               |
| Existing audit                     | `../front/docs/api-exports.md`             | (read-only reference)                     |

## Conventions

### Python

- Python ≥ 3.11, type hints everywhere (`from __future__ import annotations` ok).
- Format: `ruff format` + `ruff check`. No `black` separately.
- Linter rules: enable `RUF`, `B`, `I`, `UP`, `S`, `SIM`.
- Tests: `pytest` + `pytest-django`. Aim for 90%+ on `apps/pricing/services/`.
- ORM: `django.db.models` + `JSONField` for the `tarifs` blob (don't normalize tarifs into a separate table — they're 4 saisons × 2 formules = 8 numbers, kept as JSON for simplicity and to match the source mock).

### Django

- One app per bounded context (`catalog`, `pricing`, `recommender`, `cache_orchestrator`, `scraper`).
- All apps under `apps/` (configure via `settings.py`).
- Use `viewsets.ReadOnlyModelViewSet` for catalog, `APIView` for calc endpoints.
- DRF: enable `drf-spectacular` for OpenAPI from day 1.

### Naming (API contract)

- **JSON keys** in request/response: `camelCase` to match the frontend (`hasLoc`, `qfVal`, etc.). Use `source=` in serializers to map to snake_case Python.
- **Python identifiers**: `snake_case` (`has_loc`, `qf_val`).
- **DB columns**: `snake_case`.
- **Enum values**: lowercase with underscores (`'hs'`, `'ete'`, `'fetes'`, `'pc'`/`'dp'`/`'loc'`).

### Money & rounding

- All `€` amounts stored as `IntegerField` (rounded to the nearest euro at the end).
- Match JS `Math.round` (half-away-from-zero) — `round()` in Python is banker's rounding,
  use `decimal.Decimal` + `ROUND_HALF_UP` if it matters, or write a tiny helper.
- Never compare totals to JS for equality without a golden-master test.

### Dates

- Always ISO `YYYY-MM-DD` strings on the wire.
- Always `datetime.date` (not `datetime.datetime`) in Python.
- Saison computation: port `dateToSaisonIdx` exactly (see `../front/src/utils/stayTab.ts:33-45`). The cutoff days matter (e.g. 6/28 = start of summer).

## Common tasks for AI

### "Port function X from TS to Python"

1. Open `../front/src/utils/<file>.ts` and read the *whole* file.
2. Note: every const, helper, and edge case (e.g. `if (!dateDebut) return null`).
3. Write the Python service with the *same* function names (snake_case).
4. Add a golden-master test:
   - Call the JS function from a small Node script.
   - Capture inputs/outputs as JSON in `apps/pricing/tests/golden/<name>.json`.
   - Assert Python output equals JS output for each case.

### "Add a new endpoint"

1. Update `vtf/api/docs/05-api-endpoints.md` first (contract-first).
2. Write the DRF serializer (`apps/<app>/serializers.py`).
3. Write the view (`apps/<app>/views.py`).
4. Wire up `apps/<app>/urls.py`.
5. Verify the OpenAPI schema with `python manage.py spectacular --file schema.yml`.
6. Update the frontend type generator if you have one.

### "Update the catalog"

1. Modify `../front/src/mocks/<file>.json`.
2. Re-run `python manage.py load_vtf_mocks --src ../front/src/mocks/`.
3. Bump `pricing_rules.json:updatedAt`.
4. Bust the Redis cache (`python manage.py rebuild_cache catalog`).

## Verification checklist before merging

- [ ] Tests pass: `pytest apps/`
- [ ] Lint clean: `ruff check apps/`
- [ ] OpenAPI schema validates: `python manage.py spectacular --validate`
- [ ] Golden master tests match JS output to the euro
- [ ] No new business rule introduced without TS counterpart (or doc updated explaining the divergence)
- [ ] `vtf/front/src/mocks/*.json` and `apps/catalog/fixtures/*.json` are in sync

## Don'ts

- ❌ Don't normalize `tarifs` into a separate table. Keep as `JSONField`.
- ❌ Don't add new business logic in the API that's not in the frontend (yet). The frontend is the spec.
- ❌ Don't skip the `SimulationLog` write in `EstimateStayView` — it's the data foundation for Phase 2 reco. See `06-data-collection-strategy.md`.
- ❌ Don't return raw VTF URLs from any endpoint. Always go through `/api/v1/go/{token}` so the click is logged. See `11-booking-redirect.md`.
- ❌ Don't return an empty `villages[]` from `/recommend/villages` — **ever**. The waterfall in `07-recommendation-engine.md` guarantees ≥ 1 result. AC-2.1 fuzz test will catch regressions.
- ❌ Don't read environment variables outside `config/settings/`. Pass them as kwargs.
- ❌ Don't use `datetime.now()` in services. Pass `now: date` as a parameter so tests are deterministic.

## Cardinal rules from the spec

1. **Calculation parity**: `/estimate/stay` must match the JS golden master to ±1 € on all 50 cases (AC-1.3).
2. **Never empty recommendations**: `/recommend/villages` always returns ≥ 1 village, even with empty DB (AC-2.1, AC-2.3).
3. **Every click logged**: every booking link goes through `/go/{token}` → `BookingClick` row (AC-1.13, US-2.8).
4. **Cache freshness on signals**: `PricingRules.save()` and `load_vtf_mocks` auto-rebuild Redis (AC-3.4, AC-3.5).
5. **Idempotent fixtures**: `load_vtf_mocks` must be safe to re-run, transactional (AC-1.1).
6. **Phase 3 = 3 weeks** (not 1 week). The 1-week / 4-day numbers in spec §1.3 are AI-agent-only baselines; human-validated rollout is in `09-implementation-roadmap.md`.
7. **Session labeling is Phase 2** (env vars `OLLAMA_*`, `MISTRAL_API_KEY`, `SESSION_LABELING_*`). Local LLM (Ollama) first, cloud Mistral as fallback. See `07-recommendation-engine.md` §11.

## When stuck

- Check `09-implementation-roadmap.md` for sequencing + AI generation prompts.
- Check `../front/docs/api-exports.md` for the full audit (signatures, sources, dedups).
- Check `10-config-and-reference.md` for env vars / mgmt commands / glossary.
- The frontend mocks are tiny (~30 KB total) — re-read them when in doubt.
