# Phase 2 — Celery, Beat schedule & management commands

This document explains the **three Phase 2 background jobs**, how they connect to **Celery Worker** and **Celery Beat**, schedules, and the **SVD + pandas** training pipeline.

**Flowcharts in this file**

| # | Diagram |
|---|---------|
| 1 | [Production setup — Worker + Beat + API](#flowchart-1--production-setup-worker--beat--api) |
| 2 | [Daily Beat schedule timeline](#flowchart-2--daily-schedule-beat-timeline) |
| 3 | [After each simulation (signal)](#flowchart-3--on-demand-after-each-simulation) |
| 4 | [`train_cf_model` — SVD + pandas](#flowchart-4--train_cf_model-svd--pandas) |
| 5 | [`refresh_popularity` — every 6h](#flowchart-5--refresh_popularity-every-6-hours) |
| 6 | [`check_cf_readiness` — daily 02:50](#flowchart-6--check_cf_readiness-daily-0250) |

> Flowcharts below are plain ASCII — render in any viewer, terminal, or editor with no plugins needed.

---

## Overview

| Job | Management command | Celery task | Schedule |
|-----|-------------------|-------------|----------|
| Popularity cache | `refresh_popularity` | `task_refresh_popularity` | **Every 6 hours** (minute 0) |
| CF readiness check | `check_cf_readiness` | `task_check_cf_readiness` | **Daily 02:50** |
| SVD training | `train_cf_model` | `task_train_cf_model` | **Daily 03:00** |

Schedule is defined in `config/settings/base.py` → `CELERY_BEAT_SCHEDULE`.

Additionally, after each new `SimulationLog` row, a lightweight async task may run `check_cf_readiness` so the `cf_model_ready` flag updates without waiting for 02:50.

---

## Flowchart 1 — Production setup (Worker + Beat + API)

Three processes run on the server (no Docker required). Celery Beat sends tasks to the broker; the Worker executes them.

```text
Production server
        |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
Django / Gunicorn    Celery Worker         Celery Beat
HTTP API port 8000   celery worker         celery beat
        |                   |                   |
        |                   |     every 6h / daily cron
        |                   |                   |
        v                   v                   v
POST /estimate/stay  executes tasks      Message broker
-> SimulationLog DB        ^              (Redis)
        |                  |                   |
        | post_save         +-------------------+
        | signal            |
        +------------------>+
                            |
              +-------------+-------------+
              |             |             |
              v             v             v
  task_refresh_      task_check_     task_train_
  popularity         cf_readiness    cf_model
              |             |             |
              v             v             v
  VillagePopularity   cf_model_ready   vtf:reco:
  Cache               flag in cache    cf_model
```

---

## Flowchart 2 — Daily schedule (Beat timeline)

What runs automatically each day (server local time).

```text
Every 6 hours: 00:00, 06:00, 12:00, 18:00
-------------------------------------------------
Beat fires
    |
    v
task_refresh_popularity
    |
    v
Aggregate VillageInteraction last 30 days
    |
    v
score = views x 1 + sims x 3 + bookmarks x 5
    |
    v
Update VillagePopularityCache


Daily 02:50
-------------------------------------------------
Beat fires
    |
    v
task_check_cf_readiness
    |
    v
+-------------------------------+
|  Thresholds met?              |
|  500 sims, 100 sessions...    |
+-------------------------------+
      |               |
     yes              no
      |               |
      v               v
cf_model_ready    cf_model_ready
= true            = false


Daily 03:00
-------------------------------------------------
Beat fires
    |
    v
+----------------------+
|  cf_model_ready?     |
+----------------------+
      |           |
     yes          no
      |           |
      v           v
task_train_   Skip training
cf_model      unless --force
pandas +
Surprise SVD
      |
      v
cache vtf:reco:cf_model
TTL 25 hours
```

---

## Flowchart 3 — On-demand: after each simulation

Runs asynchronously when a user completes `/estimate/stay` (does not block the HTTP response).

```text
User POST /api/v1/estimate/stay
              |
              v
Calculate budget + save SimulationLog
              |
              +---------------------------+
              |                           |
              v                           v
     HTTP 200 response            post_save signal fires
     (returned immediately)               |
                                          v
                              +---------------------------+
                              |  cf_model_ready           |
                              |  already true?            |
                              +---------------------------+
                                    |           |
                                   yes          no
                                    |           |
                                    v           v
                               Do nothing   Enqueue task_check_
                                            cf_readiness_after_
                                            estimate
                                                |
                                                v
                                         Worker runs
                                         check_cf_readiness
                                         logic
                                                |
                                                v
                                         Update cf_model_ready
                                         flag in cache
```

---

## Celery Worker & Beat — commands to run

Set Django settings first (production example):

```bash
export DJANGO_SETTINGS_MODULE=config.settings.prod
cd /path/to/vtf/api
source venv/bin/activate
```

### Terminal 1 — Worker (executes tasks)

```bash
celery -A config.celery_app worker --loglevel=info --concurrency=2
```

- `-A config.celery_app` — Celery app module (`config/celery_app.py`)
- `worker` — consume tasks from the broker
- `--concurrency=2` — two parallel task processes (adjust for CPU)

### Terminal 2 — Beat (scheduler)

```bash
celery -A config.celery_app beat --loglevel=info
```

Uses `django_celery_beat.schedulers:DatabaseScheduler` (schedule also in `CELERY_BEAT_SCHEDULE` in settings).

### Dev shortcut (single process — local only)

```bash
celery -A config.celery_app worker --beat --loglevel=info --concurrency=2
```

### One-time setup

```bash
python manage.py migrate django_celery_beat
```

### Production environment variables

```bash
CELERY_BROKER_URL=redis://your-host:6379/0
CELERY_RESULT_BACKEND=redis://your-host:6379/1
```

See commented notes in `config/settings/prod.py`.  
**Do not** use the SQLite broker default from `base.py` in production.

### Verify tasks are registered

```bash
celery -A config.celery_app inspect registered
```

Expected task names:

- `apps.recommender.tasks.task_refresh_popularity`
- `apps.recommender.tasks.task_check_cf_readiness`
- `apps.recommender.tasks.task_train_cf_model`
- `apps.recommender.tasks.task_check_cf_readiness_after_estimate`

---

## Schedule detail (from `base.py`)

| Beat key | Cron | Local time | Task |
|----------|------|------------|------|
| `refresh-popularity` | `0 */6 * * *` | 00:00, 06:00, 12:00, 18:00 | Refresh popularity cache |
| `check-cf-readiness` | `50 2 * * *` | 02:50 daily | Set `cf_model_ready` flag |
| `train-cf-model` | `0 3 * * *` | 03:00 daily | Train SVD (after readiness check) |

**Why 02:50 then 03:00?**  
Readiness must run **before** training so `train_cf_model` sees an up-to-date `cf_model_ready` flag.

---

## Command 1 — `refresh_popularity`

### Manual run

```bash
python manage.py refresh_popularity
python manage.py refresh_popularity --days=30   # default lookback
```

### What it does (step by step)

1. Take interactions from the last **N days** (default **30**).
2. Group by `village_id` + `kind`.
3. Count `view`, `simulate`, `bookmark`.
4. Compute composite score:
   ```
   score = views×1 + simulations×3 + bookmarks×5
   ```
5. **Upsert** `VillagePopularityCache` per village.
6. Ensure every village has a cache row (zeros if no activity).

### What it feeds

- **Waterfall Tier 4** — `popular_villages()`
- **Content-based** — `popularity_boost` dimension (normalized score / 100)

### Celery equivalent

`task_refresh_popularity` — same logic, retries up to 3 times on failure.

### Timing

- **Every 6 hours** via Beat
- Typical run: seconds (depends on interaction volume)

---

## Command 2 — `check_cf_readiness`

### Manual run

```bash
python manage.py check_cf_readiness
```

### Thresholds (default)

| Metric | Minimum |
|--------|---------|
| Total `SimulationLog` rows | **500** (`RECO_MIN_CF_INTERACTIONS`) |
| Unique `session_id` | **100** |
| Sessions with ≥2 different villages | **50** |
| Villages with ≥10 simulations each | **20** villages |

### What it does

1. Query `SimulationLog` aggregates.
2. Print pass/fail per threshold.
3. Set Django cache key:
   ```python
   cache.set("cf_model_ready", True/False, timeout=86400)  # 24h
   ```

### What it feeds

- `collaborative.has_enough_data()` — gates CF re-rank on live recommendations
- `train_cf_model` — skips training if flag is `False` (unless `--force`)

### Celery equivalent

- `task_check_cf_readiness` — daily 02:50
- `task_check_cf_readiness_after_estimate` — triggered after each new simulation (only if flag not already `True`)

### Timing

- **Daily 02:50**
- Fast (few DB counts)

---

## Command 3 — `train_cf_model`

### Manual run

```bash
python manage.py train_cf_model
python manage.py train_cf_model --force   # ignore cf_model_ready flag
```

### Dependencies

```bash
pip install pandas scikit-surprise
```

Already listed in `requirements.txt`.

### Flowchart 4 — `train_cf_model` (SVD + pandas)

Full step-by-step for `python manage.py train_cf_model` / `task_train_cf_model`.

```text
Start train_cf_model
daily 03:00 or manual
        |
        v
+---------------------------+
|  cf_model_ready           |
|  OR --force flag?         |
+---------------------------+
        |           |
       yes          no
        |           |
        v           v
Collect rows     Skip training
_collect_        log warning
interaction_     run check_cf_
rows()           readiness first
        |
        +---------------------------+
        |                           |
        v                           v
SimulationLog               VillageInteraction
-> ratings                  -> ratings
2.0 / 2.5 / 5.0             view 1.0, bookmark 3.5
        |                           |
        +------------+--------------+
                     |
                     v
        Merge max rating per session + village
                     |
                     v
        +---------------------------+
        |  pandas + surprise        |
        |  installed?               |
        +---------------------------+
                |           |
               yes          no
                |           |
                v           v
        pd.DataFrame     Abort
        user_id,         log error
        item_id,         pip install pandas
        rating           scikit-surprise
                |
                v
        +---------------------------+
        |  matrix empty?            |
        +---------------------------+
                |           |
               yes          no
                |           |
                v           v
           Abort        surprise Dataset
           keep old     load_from_df
           model                |
                                v
                        SVD fit
                        n_factors=10
                        n_epochs=20
                                |
                                v
                        cache.set vtf:reco:cf_model
                        TTL 25 hours
                                |
                                v
                        Done - CF re-rank active
                        on next recommend call
```

---

### Flowchart 5 — `refresh_popularity` (every 6 hours)

```text
Start refresh_popularity
every 6h: 00:00, 06:00, 12:00, 18:00
        |
        v
Load VillageInteraction
last 30 days (default)
        |
        v
Group by village_id + kind
count views, simulate, bookmark
        |
        v
score = views x 1 + simulations x 3 + bookmarks x 5
        |
        v
Upsert VillagePopularityCache
per village
        |
        v
Ensure all 32 villages
have a cache row (zeros if no activity)
        |
        v
Done - Tier 4 waterfall uses updated scores
```

---

### Flowchart 6 — `check_cf_readiness` (daily 02:50)

```text
Start check_cf_readiness
daily 02:50
        |
        v
Count SimulationLog rows
        |
        v
Count unique sessions
        |
        v
Count multi-village sessions
        |
        v
Count villages with >= 10 sims
        |
        v
+---------------------------------------------+
|  All thresholds met?                        |
|  500 sims, 100 sessions,                    |
|  50 multi-village, 20 villages              |
+---------------------------------------------+
        |                       |
       yes                      no
        |                       |
        v                       v
cache cf_model_ready        cache cf_model_ready
= true                      = false
CF can activate             content-based only
        |                       |
        +----------+------------+
                   |
                   v
                 Done
```

#### Step 1 — Build implicit rating matrix

`_collect_interaction_rows()` in `train_cf_model.py`:

| Source | Rule |
|--------|------|
| `SimulationLog` | 2.0 base; 2.5 if ≥2 sims; 5.0 if `clicked_booking` |
| `VillageInteraction` | `view`→1.0, `simulate`→2.0, `bookmark`→3.5, `rate`→3.0, `click_cta`→5.0 |
| Dedup | One row per `(session_id, village_id)` — **max** rating wins |

Output columns: `user_id`, `item_id`, `rating` (1.0–5.0).

#### Step 2 — pandas DataFrame

```python
import pandas as pd
df = pd.DataFrame(rows, columns=["user_id", "item_id", "rating"])
```

If pandas is missing, a minimal `MiniDataFrame` is used (tests only; training needs real pandas).

#### Step 3 — Surprise SVD

```python
from surprise import Dataset, Reader, SVD

reader = Reader(rating_scale=(1, 5))
data = Dataset.load_from_df(df[["user_id", "item_id", "rating"]], reader)
trainset = data.build_full_trainset()
model = SVD(n_factors=10, n_epochs=20, random_state=42)
model.fit(trainset)
```

- **10 factors** — appropriate for ~32 villages  
- **20 epochs** — training iterations  

#### Step 4 — Cache model

```python
cache.set("vtf:reco:cf_model", model, timeout=60 * 60 * 25)  # 25 hours
```

Live API loads this in `collaborative._get_or_train_model()` and predicts per session.

### What it feeds

- **Recommendation API** — CF re-rank on Tier 1 (70/30 blend) when `cf_model_ready` and session has history

### Celery equivalent

`task_train_cf_model` — daily 03:00, 10-minute hard time limit, 1 retry

### Timing

- **Daily 03:00**
- Duration: seconds to a few minutes (depends on matrix size)

---

## How Worker + Beat interact (timeline example)

| Time | Beat | Worker runs |
|------|------|-------------|
| 02:50 | Enqueue `check_cf_readiness` | Count sims → set `cf_model_ready` |
| 03:00 | Enqueue `train_cf_model` | Build matrix → train SVD → cache model |
| 06:00 | Enqueue `refresh_popularity` | Update `VillagePopularityCache` |
| 12:00 | Enqueue `refresh_popularity` | … |
| 18:00 | Enqueue `refresh_popularity` | … |
| 00:00 | Enqueue `refresh_popularity` | … |

Any time user calls `POST /estimate/stay` → new `SimulationLog` → optional async `check_cf_readiness` if flag not yet true.

---

## Alternative: system cron (no Celery)

If the client does not run Worker/Beat, use the same commands in crontab:

```cron
0 */6 * * *  cd /app/vtf/api && python manage.py refresh_popularity
50 2 * * *   cd /app/vtf/api && python manage.py check_cf_readiness
0 3 * * *    cd /app/vtf/api && python manage.py train_cf_model
```

See `scripts/cron-phase2.example`.

---

## Optional fourth command — `cleanup_interactions`

Not on Celery Beat by default.

```bash
python manage.py cleanup_interactions --days=90
python manage.py cleanup_interactions --days=90 --dry-run
```

Deletes old `VillageInteraction` rows to control table size. Recommended **weekly** via cron (e.g. Sunday 04:00).

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Popularity never updates | Is Beat + Worker running? Or cron for `refresh_popularity`? |
| CF never applies | Run `check_cf_readiness` — are thresholds met? |
| Training skipped | `cf_model_ready` false — need more `SimulationLog` data |
| Training errors | `pip install pandas scikit-surprise` on server |
| Model lost after restart | Use **Redis** cache backend in production, not locmem |
| Tasks not found | `celery -A config.celery_app inspect registered` |

---

## File reference

| File | Role |
|------|------|
| `config/celery_app.py` | Celery application entry |
| `config/settings/base.py` | `CELERY_*` + `CELERY_BEAT_SCHEDULE` |
| `config/settings/prod.py` | Commented production Redis hints |
| `apps/recommender/tasks.py` | Celery task wrappers |
| `apps/recommender/signals.py` | Post-save on `SimulationLog` |
| `apps/recommender/management/commands/*.py` | CLI implementations |

---

## Related documentation

- [PHASE2_API_ENDPOINTS.md](./PHASE2_API_ENDPOINTS.md) — HTTP API reference
- [PHASE2_RECOMMENDATION_ENGINE.md](./PHASE2_RECOMMENDATION_ENGINE.md) — Waterfall & CF usage in recommendations
