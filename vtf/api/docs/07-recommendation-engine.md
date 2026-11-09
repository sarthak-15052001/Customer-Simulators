# 07 — Recommendation engine

> Spec source: §4 (full Phase 2). Phase 2+ (SVD) covered at the end.
>
> **Cardinal rule:** `POST /api/v1/recommend/villages` **always returns ≥ 1 village**.
> HTTP 200 always. Never empty. The waterfall in §1 guarantees this.

## 1. The 5-tier waterfall

Each tier runs only if the previous one didn't yield ≥ 3 results (or ≥ 1 for tier 4/5).

```
Tier 1: Personalized content-based scoring
        → If ≥ 3 results with score > 0.3 → return (confidence: 0.85–0.95)

Tier 2: Relaxed constraints (drop budget filter)
        → If ≥ 3 results → return (confidence: 0.5–0.7)

Tier 3: Region + season only (broadest content filter)
        → If ≥ 1 result → return (confidence: 0.3–0.5)

Tier 4: Popularity fallback (most-interacted villages)
        → Always returns ≥ 1 (confidence: 0.1–0.2)

Tier 5: Hardcoded safety net (static list of 6 village IDs)
        → Nuclear fallback — works even if the DB is empty (confidence: 0.05)
```

`relaxedFilters[]` in the response lists which constraints were dropped.
`fallbackUsed: true` is set when tier ≥ 4.

## 2. Tier 1 — Content-based scoring

Every village gets a score in `[0, 1]`. Score = weighted sum of dimensions.

### Default weights (`RecoWeights.payload`)

| Dimension              | Weight | Score logic                                                                                            |
|------------------------|--------|--------------------------------------------------------------------------------------------------------|
| `budget_fit`           | 0.30   | Sigmoid: `1.0` at budget, smooth decay above. Neutral `0.5` if no budget given.                        |
| `env_match`            | 0.25   | `1.0` if `village.env_code in preferences.envs`, else `0.2`                                            |
| `family_fit`           | 0.20   | Composite: `+0.3` `bebeClub` if baby, `+0.2` `ski` if teens, `+0.2` `enf_solo_half` if solo parent     |
| `season_availability`  | 0.15   | `1.0` if village open on selected dates, else `0.05`                                                   |
| `extras_match`         | 0.10   | `1.0` if requested `formule` is available; bonus for QF eligibility                                    |
| `popularity_boost`     | 0.05   | `VillagePopularityCache.score`, normalized to `[0, 1]`                                                  |
| `interaction_boost`    | 0.05   | `1.0` if session has previously viewed/simulated this village                                          |

These are stored in `RecoWeights.payload` (singleton, admin-tunable without redeploy).

### Budget sigmoid

```python
def budget_score(estimated_total: int, budget: int) -> float:
    """Spec §4.4 Strategy 1."""
    if budget <= 0:
        return 0.5                       # neutral when no budget given
    ratio = estimated_total / budget
    if ratio <= 1.0:
        return 1.0                       # at or under budget
    # 10 % over → 0.8, 25 % over → 0.5, 50 % over → 0.0
    return max(0.0, 1.0 - (ratio - 1.0) * 2)
```

### Reasons & warnings (when `explain=true`)

For each village, accumulate human-readable French strings. Examples:

```python
if village.env_code in prefs.envs:
    reasons.append({"sea": "Bord de mer — environnement souhaité", ...}[village.env_code])

if family.has_baby and village.bebe_club:
    reasons.append("Club bébé dès 4 mois — idéal pour votre enfant de 2 ans")

if family.qf_val and family.qf_val < 880:
    pct = "10" if village.qf_exc else "17"
    reasons.append(f"Éligible quotient familial (-{pct} %)")

if estimate.total <= prefs.budget * 0.95:
    reasons.append(f"Dans votre budget (estimé ~{estimate.total} €)")

# Warnings for missing must-haves (soft warning, not exclusion)
if family.has_baby and not village.bebe_club:
    warnings.append("Pas de club bébé")
```

### Skeleton

```python
# apps/recommender/strategies/content_based.py
from __future__ import annotations

from apps.catalog.models import Village
from apps.recommender.models import RecoWeights


def score_all_villages(family: dict, preferences: dict, *, lightweight_estimate: bool = True) -> list[dict]:
    """
    Returns a list of {village_id, village, score, reasons, warnings, estimatedTotal}
    for ALL 32 villages, sorted by score desc. Never returns empty.
    Spec §4.4 Strategy 1.
    """
    weights = RecoWeights.active()
    out: list[dict] = []

    for v in Village.objects.all():
        est = _lightweight_estimate(family, preferences, v) if lightweight_estimate else _full_estimate(family, preferences, v)
        score = (
            weights["budget_fit"]          * budget_score(est.total, preferences.get("budget", 0)) +
            weights["env_match"]           * env_match(v, preferences) +
            weights["family_fit"]          * family_fit(v, family) +
            weights["season_availability"] * season_availability(v, preferences) +
            weights["extras_match"]        * extras_match(v, preferences) +
            weights["popularity_boost"]    * popularity_boost(v) +
            weights["interaction_boost"]   * interaction_boost(v, preferences.get("sessionId"))
        )
        out.append({
            "village_id": v.id, "village": v, "score": round(score, 3),
            "reasons": _build_reasons(v, family, preferences, est),
            "warnings": _build_warnings(v, family, preferences),
            "estimated_total": est.total,
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out
```

> 💡 `must_have` filters (e.g. `bebeClub`) are **soft**: villages without the feature get
> `score=0.05`, not excluded. This guarantees the waterfall always has results.

## 3. Tier 2 — Relaxed constraints

When Tier 1 yields fewer than 3 results above threshold, drop the budget filter and re-rank.
Mark `relaxedFilters: ['budget']` in the response.

## 4. Tier 3 — Region + season only

Filter by `preferences.envs` (or by `region`) and season availability only:

```python
def tier_3_region_season(family, preferences) -> list[dict]:
    qs = Village.objects.all()
    if preferences.get("envs"):
        qs = qs.filter(env_code__in=preferences["envs"])
    # Filter open villages on the requested dates
    return [_to_payload(v, score=0.4) for v in qs if is_village_ouvert(v.ouverture, preferences["dates"]["debut"])]
```

## 5. Tier 4 — Popularity fallback

```python
# apps/recommender/strategies/popularity.py
from apps.recommender.models import VillagePopularityCache


SEED_RANKING = ["biarritz", "chamonix", "bandol", "lacanau", "saint-cast", "bedoin"]


def popular_villages(limit: int = 6) -> list:
    """Spec §4.4 Strategy 2."""
    qs = (
        VillagePopularityCache.objects
        .select_related("village")
        .order_by("-score")[:limit]
    )
    if qs.exists():
        return [row.village for row in qs]
    return list(Village.objects.filter(id__in=SEED_RANKING))   # Day-1 fallback
```

`VillagePopularityCache` is refreshed by `python manage.py refresh_popularity` (cron 6 h).

## 6. Tier 5 — Hardcoded safety net

Static list, returns even if the DB is **completely empty**:

```python
HARDCODED_FALLBACK = [
    {"id": "biarritz",   "nom": "Biarritz",   "region": "Aquitaine / Landes"},
    {"id": "chamonix",   "nom": "Chamonix",   "region": "Alpes / Savoie"},
    {"id": "bandol",     "nom": "Bandol",     "region": "Méditerranée / PACA"},
    {"id": "lacanau",    "nom": "Lacanau",    "region": "Aquitaine / Landes"},
    {"id": "saint-cast", "nom": "Saint-Cast", "region": "Bretagne / Normandie"},
    {"id": "bedoin",     "nom": "Bédoin",     "region": "Campagne / Provence"},
]
```

## 7. Orchestrator

```python
# apps/recommender/engine.py
from dataclasses import dataclass

from .strategies import content_based, popularity


@dataclass
class RecoResult:
    villages: list[dict]
    strategy: str
    confidence: float
    total_scored: int
    relaxed_filters: list[str]
    fallback_used: bool


def recommend(*, family, preferences, session_id=None, limit=6, explain=False) -> RecoResult:
    """Spec §4 — 5-tier waterfall, always returns ≥ 1 village."""
    relaxed: list[str] = []

    # Tier 1
    scored = content_based.score_all_villages(family, preferences)
    top = [s for s in scored if s["score"] > 0.3]
    if len(top) >= 3:
        return RecoResult(top[:limit], "personalized", _confidence(top, base=0.85),
                          len(scored), relaxed, False)

    # Tier 2 — drop budget
    scored2, dropped = content_based.score_relaxed(family, preferences, drop=["budget"])
    relaxed.extend(dropped)
    if len(scored2) >= 3:
        return RecoResult(scored2[:limit], "relaxed", _confidence(scored2, base=0.6),
                          len(scored2), relaxed, False)

    # Tier 3 — region + season only
    scored3 = content_based.tier_3_region_season(family, preferences)
    if scored3:
        return RecoResult(scored3[:limit], "region_only", 0.4, len(scored3),
                          relaxed + ["budget", "must_have"], False)

    # Tier 4 — popularity
    pop = popularity.popular_villages(limit=limit)
    if pop:
        return RecoResult([_to_payload(v) for v in pop], "popular_fallback", 0.15, len(pop),
                          relaxed + ["budget", "must_have", "envs"], True)

    # Tier 5 — hardcoded
    return RecoResult(HARDCODED_FALLBACK[:limit], "hardcoded_safety_net", 0.05,
                      len(HARDCODED_FALLBACK), relaxed + ["everything"], True)
```

## 8. Similar villages

> Spec §US-4.4. `GET /api/v1/villages/{id}/similar?limit=3`.

Score similarity by shared attributes (region, env_code, ski, formules) + popularity tiebreaker.

```python
def similar_villages(*, village_id: str, limit: int = 3) -> list[dict]:
    target = Village.objects.get(pk=village_id)
    out = []
    for v in Village.objects.exclude(id=village_id):
        score = (
            0.4 * (1.0 if v.region == target.region else 0.0) +
            0.3 * (1.0 if v.env_code == target.env_code else 0.0) +
            0.1 * (1.0 if v.ski == target.ski else 0.0) +
            0.1 * (len(set(v.formules) & set(target.formules)) / max(1, len(target.formules))) +
            0.1 * popularity_boost(v)
        )
        out.append({"village_id": v.id, "village": v, "score": round(score, 3)})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]
```

Always returns ≥ 1 (we just take top-N from all 31 other villages).

## 9. Phase 2+ — SVD collaborative filtering (re-ranker)

Activates when `SimulationLog` + `VillageInteraction` reach the gates:

| Metric                     | Threshold | Check query                                                                   |
|----------------------------|-----------|-------------------------------------------------------------------------------|
| Total simulations          | ≥ 500     | `SimulationLog.objects.count()`                                               |
| Unique sessions            | ≥ 100     | `SimulationLog.objects.values("session_id").distinct().count()`               |
| Sessions with ≥ 2 villages | ≥ 50      | `... .annotate(n=Count("village", distinct=True)).filter(n__gte=2).count()`   |
| Villages with ≥ 10 sims    | ≥ 20      | `... .values("village").annotate(n=Count("id")).filter(n__gte=10).count()`    |

Daily cron sets `cache.set("cf_model_ready", True)`. CF is then a **re-ranker**, not primary:

```python
# Inside engine.recommend(), after Tier 1 (only if cf_model_ready and session has history)
cf_scores = collaborative.predict_for_session(session_id, [s["village_id"] for s in top])
for item in top:
    cf = cf_scores.get(item["village_id"], 2.5) / 5.0   # normalize to 0-1
    item["score"] = item["score"] * 0.7 + cf * 0.3
    if explain:
        item["reasons"].append(f"Affinité collaborative : {cf:.0 %}")
top.sort(key=lambda x: x["score"], reverse=True)
strategy = "personalized_cf"
```

### Implicit-rating matrix

| Behavior                          | Implicit rating (1–5) |
|-----------------------------------|------------------------|
| `view` / `village_view`           | 1.0                    |
| `simulate` (1 sim)                | 2.0                    |
| `simulate` (≥ 2 sims same village)| 2.5                    |
| `result_view`                     | 3.0                    |
| `recap_view` / `bookmark`         | 3.5                    |
| `share_click`                     | 4.0                    |
| `BookingClick` (any source)       | 5.0                    |

Keep the **max** rating per `(session_id, village_id)`.

```python
# apps/recommender/strategies/collaborative.py
import pandas as pd
from django.db.models import Count, Max
from surprise import Dataset, Reader, SVD


def build_interaction_matrix() -> pd.DataFrame:
    """Convert SimulationLog + VillageInteraction + BookingClick → user/item/rating."""
    from apps.pricing.models import SimulationLog, BookingClick
    from apps.recommender.models import VillageInteraction

    rows: list[dict] = []
    for s in SimulationLog.objects.values("session_id", "village_id").annotate(
        sim_count=Count("id"),
    ):
        rating = 2.5 if s["sim_count"] >= 2 else 2.0
        rows.append({"user_id": s["session_id"], "item_id": s["village_id"], "rating": rating})

    for c in BookingClick.objects.values("session_id", "village_id"):
        rows.append({"user_id": c["session_id"], "item_id": c["village_id"], "rating": 5.0})

    boost = {"view": 1.0, "bookmark": 3.5, "rate": 4.0, "click_cta": 4.5}
    for sig in VillageInteraction.objects.filter(kind__in=list(boost)).values("session_id", "village_id", "kind"):
        rows.append({"user_id": sig["session_id"], "item_id": sig["village_id"], "rating": boost[sig["kind"]]})

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.groupby(["user_id", "item_id"])["rating"].max().reset_index()
```

### Training & lifecycle

```python
# apps/recommender/management/commands/train_cf_model.py
def train(df):
    reader = Reader(rating_scale=(1, 5))
    data = Dataset.load_from_df(df[["user_id", "item_id", "rating"]], reader)
    model = SVD(n_factors=10, n_epochs=20, random_state=42)   # n_factors=10 for ~32 items
    model.fit(data.build_full_trainset())
    return model
```

| Event                        | Action                                              | Frequency           |
|------------------------------|-----------------------------------------------------|---------------------|
| `train_cf_model` mgmt cmd    | Retrain SVD from `SimulationLog` + signals         | Daily (cron 03:00)  |
| Storage                      | Pickle in Redis `vtf:reco:cf_model` + joblib backup | Overwritten daily   |
| Model size                   | ~50 KB for 32 items × 500 users                    | Negligible          |
| Cold start (new session)     | CF skipped, content-based only                      | Automatic           |
| Warm session (≥ 2 interactions) | CF re-ranking applied                            | Automatic           |
| Drift detection              | Compare RMSE on hold-out vs last week              | Weekly              |

### A/B test

Deterministic split: `use_cf = hash(session_id) % 2 == 0`. Both groups run the recommender;
only one applies the CF blend. Log `ab_group` in `SimulationLog` and compare:

| Metric                                           | Goal                |
|--------------------------------------------------|---------------------|
| Booking click-through rate (primary)             | ↑ vs control        |
| Unique villages simulated per session            | ↑ (more exploration) |
| Time to first booking click                      | ↓                   |
| Repeat session rate (≤ 30 days)                  | ↑                   |
| RMSE on hold-out                                 | < 1.0 stable        |

## 10. Acceptance criteria (Phase 2, spec §4.5)

| ID       | Criterion                                                                 | Verification                |
|----------|---------------------------------------------------------------------------|------------------------------|
| AC-2.1   | Recommendation endpoint **NEVER** returns empty `villages[]`              | 100 fuzz inputs              |
| AC-2.2   | Each fallback tier activatable via specific input patterns                | Dedicated integration tests  |
| AC-2.3   | Tier 5 (hardcoded) works with empty database                              | Test with truncated tables   |
| AC-2.4   | `explain=true` provides human-readable French reasons                     | Manual QA + snapshot         |
| AC-2.5   | `estimatedTotal` per recommended village within ±5 % of full estimate     | Cross-validation test        |
| AC-2.6   | Interaction tracking < 50 ms (non-blocking)                               | Load test                    |
| AC-2.7   | Popularity cache refreshes every 6 h without downtime                     | Cron + monitoring            |
| AC-2.8   | Scoring weights updatable via admin without deployment                    | Admin endpoint test          |
| AC-2.9   | Response time < 500 ms for recommendation with 6 results (p95)            | Load test                    |
| AC-2.10  | Rate limiting prevents abuse (100 interactions/session/hour)              | Throttle test                |
| AC-2.11  | SVD model auto-activates when thresholds met                              | Feature flag test            |
| AC-2.12  | CF re-ranking blends 70/30 with content-based when active                 | A/B framework                |
| AC-2.13  | `SimulationLog` → implicit rating conversion produces valid 1–5 scale     | Unit test                    |
| AC-2.14  | SVD model retrains daily via cron without downtime                        | Mgmt command test            |

## 11. Session labeling (Phase 2 enrichment)

> Spec §8.1 env vars `OLLAMA_BASE_URL`, `OLLAMA_LABEL_MODEL`, `MISTRAL_API_KEY`,
> `SESSION_LABELING_ENABLED`, `SESSION_LABELING_USE_LLM`.

To boost the `family_fit` and `extras_match` scoring dimensions and to make the analytics
dashboards readable, every session gets one or more **labels** computed in two layers.

### 11.1 Rule-based labels (always on when `SESSION_LABELING_ENABLED=true`)

Deterministic, instant, no external dependency. Computed inside a Django signal on
`SimulationLog.post_save`.

| Label                       | Condition                                                                |
|-----------------------------|--------------------------------------------------------------------------|
| `family:solo_parent`        | `nb_adults == 1 AND nb_children >= 1`                                    |
| `family:large_family`       | `nb_children >= 3`                                                       |
| `family:with_baby`          | any child age ≤ 1                                                        |
| `family:with_teens`         | any child age ≥ 12                                                       |
| `family:couple`             | `nb_adults == 2 AND nb_children == 0`                                    |
| `budget:price_sensitive`    | `qf_val < 880` OR estimated_total close to or above stated budget        |
| `budget:premium`            | `formule == 'PC' AND qf_val >= 1350 AND estimated_total > 3000 €`        |
| `intent:explorer`           | session simulated ≥ 3 different villages                                 |
| `intent:converter`          | session has at least one `BookingClick`                                  |
| `season:summer_seeker`      | all sims in `ete`                                                        |
| `season:ski_seeker`         | all sims with `village.ski == True` in `vs` or `fetes`                   |
| `region:loyal_{region}`     | ≥ 70 % of session's sims target one region                               |

These labels are stored on `VillageInteraction.metadata.labels: list[str]` (or a separate
`SessionLabel(session_id, label, confidence, created_at)` table — TBD per spec §4.4 open
question).

### 11.2 LLM enrichment (opt-in via `SESSION_LABELING_USE_LLM=true`)

For sessions that don't fit the rules cleanly, an LLM produces a free-form label.

**Pipeline:**
1. Cron `label_sessions --use-llm` runs hourly (or async after `BookingClick`).
2. For each unlabeled (or rule-matched-but-low-confidence) session:
   1. Build a compact prompt from `SimulationLog` rows + `VillageInteraction` events.
   2. Call **Ollama** at `OLLAMA_BASE_URL` with `OLLAMA_LABEL_MODEL` (default `mistral`).
   3. If Ollama is unreachable, fall back to **Mistral cloud** (`MISTRAL_API_KEY`).
   4. Parse the JSON response and persist labels.

**Prompt skeleton:**

```
You are a recommendation analyst for a French family vacation operator (VTF).
Given a user session below, output a JSON list of 1-3 labels chosen from this taxonomy:
  [intent:*], [budget:*], [family:*], [season:*], [region:*]
plus optionally one free-form label of the form 'persona:<noun>' (e.g. 'persona:digital_nomad_family').

Session:
- Family: 2 adultes, enfants âgés de 4 et 8 ans, QF=900
- Stays simulated: biarritz (PC, 2026-07-05→07-12, 2847€), lacanau (PC, …), saint-cast (DP, …)
- Booking clicks: 0
- Duration in funnel: 4 min 12 s

Respond with ONLY this JSON shape:
{ "labels": ["..."] }
```

**Why local LLMs (Ollama) first?** Cost (free), privacy (no PII leaves the host), latency
(< 200 ms on a CPU for `mistral`/`phi3`). Cloud Mistral is the fallback when the local
model is unreachable.

### 11.3 How labels feed the recommender

Labels enter the scoring loop in two places:

1. **Direct boost**: certain labels override or weight specific dimensions —
   e.g. `family:with_baby` forces `village.bebe_club` boost from `+0.3` to `+0.5`.
2. **Cohort lookup** (Phase 2+): the popularity ranking can be pre-computed
   per-label (`popularity[family:large_family]`) so that fallback Tier 4 is segmented.

## 12. Weight tuning (`tune_reco_weights`)

> Spec §8.2 mgmt command, monthly schedule.

The 7 weights in `RecoWeights.payload` are tunable without redeploy, but how do we know
the right values? Once we have ≥ 1000 `BookingClick` rows, a monthly grid search optimizes
them against booking CTR.

**Algorithm:**
```python
# apps/recommender/management/commands/tune_reco_weights.py
GRID = {
    "budget_fit":          [0.20, 0.25, 0.30, 0.35],
    "env_match":           [0.20, 0.25, 0.30],
    "family_fit":          [0.15, 0.20, 0.25],
    "season_availability": [0.10, 0.15, 0.20],
    "extras_match":        [0.05, 0.10, 0.15],
    "popularity_boost":    [0.05, 0.10],
    "interaction_boost":   [0.05, 0.10],
}


def evaluate(weights: dict, sample: list[SimulationLog]) -> float:
    """Return CTR (BookingClick.count / sample.count) when scoring with these weights."""
    ...


def search() -> dict:
    best, best_ctr = None, 0.0
    for combo in itertools.product(*GRID.values()):
        cand = dict(zip(GRID.keys(), combo))
        if abs(sum(cand.values()) - 1.0) > 0.01:    # weights must sum to ~1.0
            continue
        ctr = evaluate(cand, recent_sample)
        if ctr > best_ctr:
            best, best_ctr = cand, ctr
    return best
```

The winning weights are written to a **new `RecoWeights` row** with `is_active=False`,
notified via Slack, and a human flips `is_active=True` after a sanity review (no auto-deploy).

## 13. Risks

| Risk                                              | Mitigation                                                      |
|---------------------------------------------------|-----------------------------------------------------------------|
| Cold start (small catalog, 32 items)              | `n_factors=10`; never use SVD as primary, always blend with CB  |
| Sparse matrix early on                            | Threshold gates + fallback to content-based                     |
| Anonymous sessions (no cross-device)              | Acceptable; we recommend within a session, not across logins    |
| Booking clicks lag behind simulations             | Treat `clicked_booking` retroactively in next training          |
| Privacy: session ID = user ID for CF              | Already anonymous; rotate session ID after 30 days inactivity   |
| Empty `villages[]` regression                     | Fuzz test in CI (AC-2.1) — 100 random inputs must all return ≥1 |
