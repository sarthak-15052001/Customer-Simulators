# Phase 2 — Recommendation engine (waterfall, strategies, estimates)

This document explains **how recommendations are built**: the 5-tier waterfall, scoring strategies, lightweight estimates, signals/interactions, and collaborative filtering (SVD).

**Flowcharts in this file**

| # | Diagram |
|---|---------|
| 1 | [Full recommendation API request](#flowchart-1--recommendation-api-full-request) |
| 2 | [Waterfall tiers 1–5 detail](#flowchart-2--waterfall-tiers-15-detail) |
| 3 | [Content-based scoring](#flowchart-3--content-based-scoring-one-village) |
| 4 | [CF / SVD re-rank](#flowchart-4--collaborative-filtering-cf--svd-re-rank) |
| 5 | [Signals & interactions](#flowchart-5--signals--interactions-data-collection) |
| 6 | [RecommendationSystemState runtime state](#flowchart-6--recommendationsystemstate-runtime-state) |

> Flowcharts below are plain ASCII — render in any viewer, terminal, or editor with no plugins needed.

---

## Flowchart 1 — Recommendation API (full request)

Top-down flow matching the live `RecommendVillagesView` → `engine.recommend()` path.

```text
POST /api/v2/recommend/villages
              |
              v
        Validate JSON
   family + preferences + sessionId
              |
              v
   +------------------------+
   |  preferences empty?    |
   +------------------------+
        |              |
       yes             no
        |              |
        v              v
  Popular /        Lightweight price
  Seed fallback    per village
  Tier 0           bulk_estimate x32
                        |
                        v
               Score all villages
               content-based weights
                        |
                        v
             Apply session interaction
                    boosts
                        |
                        v
   +------------------------------------+
   |  CF ready + session history?       |
   +------------------------------------+
        |                    |
       yes (A/B cf arm)      no
        |                    |
        v                    |
    CF re-rank               |
    70% content              |
    30% SVD                  |
        |                    |
        +--------------------+
                 |
                 v
       Waterfall tiers 1-5
       pick first that succeeds
                 |
                 v
      Build result per village
      rank + bookingUrl + reasons
                 |
                 v
       Always HTTP 200 >= 1 village
```

**Contract:** The API **never** returns an empty `villages` array. If the engine throws, the view falls back to seed villages before responding.

---

## Flowchart 2 — Waterfall tiers 1–5 (detail)

After content-based scoring (+ optional CF re-rank), the engine walks tiers until one succeeds.

```text
Enter waterfall
sorted content scores ready
         |
         v
+----------------------------+
|  Tier 1: >= 3 villages     |
|  score > 0.3?              |
+----------------------------+
      |               |
     yes              no
      |               |
      v               v
 STOP            Tier 2: drop budget filter
 personalized    re-score all villages
 conf 0.85-0.95       |
                      v
               +----------------------------+
               |  >= 3 villages score > 0.2?|
               +----------------------------+
                     |               |
                    yes              no
                     |               |
                     v               v
                STOP            Tier 3: region + season only
                personalized    drop formule, mustHave, avoidSki
                relaxed:budget       |
                conf 0.5-0.7         v
                             +----------------------------+
                             |  >= 1 village score > 0.1? |
                             +----------------------------+
                                   |               |
                                  yes              no
                                   |               |
                                   v               v
                              STOP            Tier 4: VillagePopularityCache
                              popular_fallback most interacted villages
                              relaxed: budget,      |
                              formule, mustHave      v
                                             +-------------------+
                                             |  cache has rows?  |
                                             +-------------------+
                                                   |         |
                                                  yes        no
                                                   |         |
                                                   v         v
                                              STOP      Tier 5: SEED_RANKING
                                              popular_  biarritz, chamonix,
                                              fallback  bandol, lacanau,
                                              fallback: saint-cast, bedoin
                                              true           |
                                              conf 0.1-0.2   v
                                                        STOP
                                                        popular_fallback
                                                        fallbackUsed: true
                                                        confidence: 0.05
```

---

## Flowchart 3 — Content-based scoring (one village)

How a single village gets its score before the waterfall checks.

```text
For each village
        |
        v
  Compute dimensions
        |
   +----+----+----+----+----+----+----+
   |    |    |    |    |    |    |    |
   v    v    v    v    v    v    v    v

budget  env   fam  season extras  pop  inter
_fit   _match _fit  _avail _match boost boost
x0.30  x0.25 x0.20 x0.15  x0.10  x0.05 x0.05

   |    |    |    |    |    |    |    |
   +----+----+----+----+----+----+----+
                    |
                    v
       Weighted sum -> raw_score
                    |
                    v
     +----------------------------------+
     |  mustHave missing?               |
     |  or avoidSki + ski village?      |
     +----------------------------------+
            |                  |
           yes                 no
            |                  |
            v                  v
     final_score =       final_score =
       min 0.05            raw_score
            |                  |
            +--------+---------+
                     |
                     v
        Build French reasons
        + warnings if explain=true
                     |
                     v
        Sort all villages by score desc
```

---

## Flowchart 4 — Collaborative filtering (CF / SVD re-rank)

CF runs **inside Tier 1**, not as a separate waterfall exit.

```text
Content-based scores computed
              |
              v
  +------------------------------+
  |  cf_model_ready?             |
  |  cache -> DB fallback        |
  +------------------------------+
       |                  |
      yes                 no -------> Skip CF
       |                              keep content order
       v                                    |
  +------------------------------+          |
  |  sessionId present           |          |
  |  + >= 2 interactions?        |          |
  +------------------------------+          |
       |                  |                 |
      yes                 no --> Skip CF    |
       |                        keep order  |
       v                             |      |
  +------------------------------+  |      |
  |  hash(sessionId) % 2 == 0?  |  |      |
  |  (A/B: cf arm)               |  |      |
  +------------------------------+  |      |
       |                  |         |      |
      yes                 no --> Skip CF   |
       |                        keep order |
       v                             |     |
  Load SVD model                    |     |
  vtf:reco:cf_model                 |     |
       |                            |     |
       v                            |     |
  Predict rating per village        |     |
  Surprise SVD                      |     |
       |                            |     |
       v                            |     |
  new_score =                       |     |
  content x 0.70 + cf/5.0 x 0.30   |     |
       |                            |     |
       v                            |     |
  Re-sort -> strategy: personalized_cf    |
       |                            |     |
       +----------------------------+-----+
                      |
                      v
           Continue to waterfall
```

---

## The 5-tier waterfall (detailed)

Implementation: `apps/recommender/engine.py`

| Tier | Name | When it runs | Stop condition | `strategy` | `confidence` (typical) | `fallbackUsed` |
|------|------|----------------|----------------|------------|------------------------|----------------|
| **0** | Zero preferences | `preferences` empty | Always (short-circuit) | `popular_fallback` | 0.1 or 0.05 | `true` |
| **1** | Personalized content-based | Full preferences | ≥3 villages with **score > 0.3** | `personalized` or `personalized_cf` | 0.85–0.95 | `false` |
| **2** | Relaxed budget | Tier 1 failed | ≥3 villages with **score > 0.2** (budget removed) | `personalized` | 0.5–0.7 | `false` |
| **3** | Region + season only | Tier 2 failed | ≥1 village with **score > 0.1** | `popular_fallback`* | 0.3–0.5 | `false` |
| **4** | Popularity cache | Tier 3 failed | `VillagePopularityCache` has data | `popular_fallback` | 0.1–0.2 | `true` |
| **5** | Seed safety net | Tier 4 empty / DB issue | Always returns 6 hardcoded IDs | `popular_fallback` | **0.05** | `true` |

\*Tier 3 still uses content-based scoring but with minimal filters; the `strategy` label is `popular_fallback` in code (broader match tier).

### Tier 0 — Empty preferences

If the user sends `"preferences": {}` (no envs, formule, budget, dates, mustHave, avoidSki):

1. Call `popular_villages(limit)` from popularity cache.
2. If cache empty → `seed_villages(limit)` (hardcoded list).
3. Return immediately with `fallbackUsed: true`.

**Seed village IDs (Tier 5 / day-1):**  
`biarritz`, `chamonix`, `bandol`, `lacanau`, `saint-cast`, `bedoin`

### Tier 1 — Full content-based + optional CF

1. Score all villages with `content_based.score_all_villages()`.
2. Apply **session interaction boosts** (see below).
3. Optionally **CF re-rank** (Tier 1.5 — not a separate waterfall exit):
   - `cf_model_ready` cache flag is `true`
   - Session has ≥2 interactions/simulations
   - A/B: `hash(sessionId) % 2 == 0` → **cf** arm applies 70/30 blend
4. Keep villages with `score > 0.3`; need **at least 3**.

### Tier 2 — Drop budget

Re-score with `preferences.budget = null`. Threshold: **score > 0.2**, ≥3 villages.  
`relaxedFilters: ["budget"]`

### Tier 3 — Minimal content filter

Preferences reduced to:

```python
{
  "envs": <user envs or []>,
  "formule": None,
  "budget": None,
  "dates": <user dates>,
  "mustHave": [],
  "avoidSki": False,
}
```

Threshold: **score > 0.1**, ≥1 village.  
`relaxedFilters: ["budget", "formule", "mustHave", "avoidSki"]`

### Tier 4 — Popularity

Order villages by `VillagePopularityCache.score` (refreshed every 6h).  
`relaxedFilters: ["all_filters"]`, `fallbackUsed: true`

### Tier 5 — Nuclear seed

Works even if the `Village` table is empty (returns placeholder entries).  
`confidence: 0.05`, `fallbackUsed: true`

---

## Strategy 1 — Content-based scoring

**File:** `apps/recommender/strategies/content_based.py`

Every village gets a score **0.0–1.0**. Villages are **not removed** from the list (waterfall can still use low scorers in later tiers).

### Scoring dimensions (default weights from `RecoWeights`)

| Dimension | Weight | Logic |
|-----------|--------|--------|
| **Budget fit** | 0.30 | Sigmoid: 1.0 at/under budget; smooth decay above. Neutral 0.5 if no budget or no estimate |
| **Environment match** | 0.25 | 1.0 if `env_code` in `preferences.envs`, else 0.2 |
| **Family fit** | 0.20 | Baby club, ski for teens, solo-parent half, QF eligibility bonuses |
| **Season availability** | 0.15 | 1.0 if village open on `dates.debut`, else 0.05 |
| **Extras / formule** | 0.10 | Formule available in village |
| **Popularity boost** | 0.05 | From `VillagePopularityCache` (normalized) |
| **Interaction boost** | 0.05 | From current session history |

**Final score** = weighted sum, then:

- **`mustHave`** missing on village → cap at **0.05** (hard penalty, not exclusion)
- **`avoidSki`** + ski village → same penalty

### Budget sigmoid (soft filter)

```
ratio = estimatedTotal / budget
if ratio ≤ 1.0 → score 1.0
else → max(0, 1.0 - (ratio - 1.0) * 2)
```

Example: 10% over budget → 0.8; 25% over → 0.5; 50% over → 0.0

### French explanations (`explain=true`)

`_build_reasons()` adds human-readable strings, e.g.:

- Environment match
- Baby club / warnings if missing
- QF discount tier (-17% / -10%)
- Budget fit or over-budget warning
- Solo-parent tariff
- Ski for teens

---

## Strategy 2 — Popularity-based fallback

**File:** `apps/recommender/strategies/popularity.py`

Used for:

- Tier 0 (empty preferences)
- Tier 4 (waterfall)
- Cache-empty day-1 fallback inside `popular_villages()`

**Composite score** (when refreshing cache):

```
score = views×1 + simulations×3 + bookmarks×5
```

(Last 30 days of `VillageInteraction`, via `refresh_popularity`.)

---

## Strategy 3 — Collaborative filtering (SVD re-rank)

**File:** `apps/recommender/strategies/collaborative.py`

CF is **not** a separate waterfall tier. It **re-ranks** Tier 1 content scores when:

| Condition | Threshold |
|-----------|-----------|
| Total `SimulationLog` rows | ≥ 500 (`RECO_MIN_CF_INTERACTIONS`) |
| Unique sessions | ≥ 100 |
| Sessions with ≥2 different villages | ≥ 50 |
| Villages with ≥10 simulations each | ≥ 20 villages |

Flag: `get_cf_model_ready()` — set by `check_cf_readiness`.

The fast path is Django cache, but the durable source is
`RecommendationSystemState(key="cf_model_ready")`. If the cache expires, the
system reads the DB row and writes the value back into cache.

**Blend (cf arm only):**

```
new_score = content_score × 0.70 + (cf_prediction / 5.0) × 0.30
```

**A/B test:** `hash(sessionId) % 2` → even = `cf`, odd = `control` (no CF change).

**Cold start:** No `sessionId` or &lt;2 history → CF skipped.

---

## RecommendationSystemState runtime state

**File:** `apps/recommender/models.py`

`RecommendationSystemState` is a small DB-backed key-value table for global
recommender runtime state. It does **not** store recommendations and it does
**not** store the trained SVD model object. It stores durable flags and metadata
around CF readiness/training so the system can recover when cache expires or
Redis restarts.

| Key | `value_bool` meaning | Metadata contains |
|-----|----------------------|-------------------|
| `cf_model_ready` | Whether enough data exists for CF/SVD | counts, thresholds, failed checks, checked time |
| `cf_model_training` | Latest training outcome | status, reason, matrix size, model key, timestamps |

### Important distinction

| Thing | Stored in | Meaning |
|-------|-----------|---------|
| `cf_model_ready` | Cache + `RecommendationSystemState` | Enough data exists to train/use CF |
| `cf_model_training` | `RecommendationSystemState` | Last training attempt status |
| `vtf:reco:cf_model` | Django cache only | Actual trained Surprise SVD model object |

So deleting `vtf:reco:cf_model` from cache does **not** make
`cf_model_ready` false. Readiness is about data thresholds, not whether the
cached model object currently exists.

### State lifecycle

1. `check_cf_readiness` or `task_check_cf_readiness` evaluates thresholds from
   `SimulationLog` and `VillageInteraction`.
2. `save_cf_readiness_state()` writes the result to:
   - `cache["cf_model_ready"]`
   - `RecommendationSystemState(key="cf_model_ready")`
3. `train_cf_model` checks `get_cf_model_ready()` before training.
4. If ready is false, training is skipped and `cf_model_training` becomes
   `skipped_not_ready`.
5. If ready is true, SVD trains and the model is cached at
   `vtf:reco:cf_model`; `cf_model_training` becomes `trained`.
6. During recommendations, CF re-rank needs both:
   - `cf_model_ready = true`
   - `cache["vtf:reco:cf_model"]` present
7. If the model cache is missing/expired, CF is skipped and
   `cf_model_training` is updated to `model_missing_or_expired`.

### Example states

Not enough data:

```json
{
  "key": "cf_model_ready",
  "value_bool": false,
  "metadata": {
    "ready": false,
    "counts": {
      "simulation_logs": 184,
      "unique_sessions": 168
    },
    "failed_checks": ["min_simulations"]
  }
}
```

Training skipped because readiness is false:

```json
{
  "key": "cf_model_training",
  "value_bool": false,
  "metadata": {
    "status": "skipped_not_ready",
    "reason": "cf_model_ready is false",
    "force": false
  }
}
```

Enough data and training succeeded:

```json
{
  "key": "cf_model_training",
  "value_bool": true,
  "metadata": {
    "status": "trained",
    "model_type": "SVD",
    "model_key": "vtf:reco:cf_model",
    "matrix_rows": 184,
    "unique_sessions": 168,
    "unique_villages": 32
  }
}
```

Model removed from cache after successful training:

```text
cf_model_ready = true
cf_model_training = trained or model_missing_or_expired
cache["vtf:reco:cf_model"] = missing
```

In that case the recommendation API still works, but CF re-rank is skipped
until `train_cf_model` runs again, or `train_cf_model --force` is used in a dev
environment.

---

## Flowchart 6 — RecommendationSystemState runtime state

How CF readiness, training, DB state, and cache relate to each other.

```text
POST /estimate/stay
      |
      v
SimulationLog created
      |
      v
post_save signal
      |
      v
task_check_cf_readiness_after_estimate
      |
      v
evaluate_cf_readiness()
counts SimulationLog + VillageInteraction
      |
      v
+-----------------------------+
|  thresholds met?            |
+-----------------------------+
      |                 |
     yes                no
      |                 |
      v                 v
save cf_model_ready=true   save cf_model_ready=false
DB + cache                 DB + cache
      |                 |
      +--------+--------+
               |
               v
        train_cf_model
               |
               v
     get_cf_model_ready()
     cache -> DB fallback
               |
               v
+-----------------------------+
|  cf_model_ready true?       |
+-----------------------------+
      |                 |
     yes                no
      |                 |
      v                 v
Build SVD matrix       save cf_model_training
Train Surprise SVD     status=skipped_not_ready
      |
      v
cache["vtf:reco:cf_model"]
save cf_model_training
status=trained
      |
      v
Recommendation request
      |
      v
Content scoring
      |
      v
+-----------------------------+
| ready true + model cached?  |
+-----------------------------+
      |                 |
     yes                no
      |                 |
      v                 v
CF 70/30 re-rank       Skip CF
personalized_cf        content/popularity fallback still works
```

---

## Lightweight estimate service (`estimate.py`)

**File:** `apps/recommender/services/estimate.py`

### Why it exists

Full `POST /api/v1/estimate/stay` includes transport, restaurant, activities, promos — too slow to run 32× per recommendation request. The spec allows a **lightweight** estimate target **&lt; 500ms** for 6 results.

### What it does

`lightweight_estimate(village, family, preferences)`:

1. Loads active `PricingRules`.
2. Requires `preferences.dates` (debut/fin).
3. Picks `formule` from preferences or village default.
4. Calls `estimate_sejour_total()` with:
   - **No transport** (`mode: "none"`)
   - **No restaurant** (`qtyByMealId: {}`)
   - **No activities** (zeros)
   - **No promo discount** (rates 0)

Returns **integer total euros** or `None` on failure.

`bulk_estimate()` runs this for all villages once per recommend call; results feed **budget_fit** scoring.

### Accuracy

Tests require `estimatedTotal` within **±5%** of a full estimate (same dates/formule/family, no extras). Good enough for ranking, not for final checkout.

### Booking URL

After scoring, `_build_result()` in `engine.py` calls `BookingRedirectService.create_token()` so each village gets a signed `bookingUrl` (`/api/v1/go/{token}`).

---

## Session interaction boost

When `sessionId` is provided, past `VillageInteraction` rows add boost weight:

| Kind | Weight |
|------|--------|
| `view` | 0.5 |
| `simulate` | 1.0 |
| `bookmark` | 2.0 |
| `rate` | 1.5 |
| `click_cta` | 2.5 |

Summed per village, capped when applying `interaction_boost` dimension (max 1.0 contribution).

---

## Flowchart 5 — Signals & interactions (data collection)

Why we collect data and where it flows in Phase 2.

```text
Simulator UI
      |
      +-------------------+--------------------+
      |                   |                    |
      v                   v                    v
POST /signals    POST /interactions    POST /estimate/stay
      |                   |                    |
      v                   |                    v
+------------------+      |           SimulationLog
|  Has villageId?  |      |           family, dates,
|  maps to         |      |           total, QF
|  interaction?    |      |                   |
+------------------+      |                   |
     |         |           |                   |
    yes        no          |                   |
     |         |           |                   |
     v         v           v                   v
VillageInteraction  FrontendSignal    train_cf_model   check_cf_readiness
     |              session_start,    -> SVD matrix    -> cf_model_ready
     |              step_complete...
     |
     +------------------+------------------+
     |                  |                  |
     v                  v                  v
refresh_popularity  train_cf_model    Session boost
-> VillagePopularity -> SVD matrix    in recommend
   Cache                               engine
```

| Data source | What it captures | Why |
|-------------|------------------|-----|
| **SimulationLog** | Every `/estimate/stay` (family, dates, total, QF, promos) | Primary matrix for SVD; implicit rating 2.0–5.0 |
| **POST /interactions** | Explicit typed events | Popularity aggregates + matrix + session boost |
| **POST /signals** | Lightweight beacons | Funnel analytics; some map to interactions |
| **BookingClick** (Phase 1 redirect) | Click-through intent | Strongest signal (rating 5.0) when linked to simulation |

### Implicit ratings for SVD (1–5 scale)

Built in `train_cf_model._collect_interaction_rows()`:

| Behavior | Rating |
|----------|--------|
| Simulated once | 2.0 |
| Simulated ≥2 times (same session+village) | 2.5 |
| Booking click on simulation | 5.0 |
| `view` interaction | 1.0 |
| `bookmark` | 3.5 |
| `click_cta` | 5.0 |

Duplicate (session, village) pairs keep the **maximum** rating.

---

## End-to-end: one recommendation request

1. **Client** sends family + preferences + optional `sessionId`.
2. **Engine** loads all villages + active `RecoWeights`.
3. **bulk_estimate** computes 32 lightweight totals (if dates present).
4. **Content-based** scores each village; applies mustHave penalties.
5. **CF** may re-rank top list (if ready + session warm + A/B arm).
6. **Waterfall** picks tier (1 → 2 → 3 → 4 → 5).
7. **_build_result** adds rank, `bookingUrl`, strips reasons if `explain=false`.
8. **View** wraps in `{ success, message, data }`.

---

## Configuration knobs

| Knob | Where | Purpose |
|------|-------|---------|
| `RecoWeights` payload | DB + admin API | Tune dimension weights |
| `RECO_MIN_CF_INTERACTIONS` | `settings` (default 500) | When CF can activate |
| `cf_model_ready` | Django cache + `RecommendationSystemState` | Durable readiness gate for training + re-rank |
| `cf_model_training` | `RecommendationSystemState` | Latest SVD training status |
| `vtf:reco:cf_model` | Django cache | Serialized Surprise SVD model |
