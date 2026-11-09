# 06 — Phase 1 data collection strategy

> Spec source: §3.1 (US-1.x), §3.2 (`SimulationLog`), §US-2.8 (`BookingClick`), §US-3.1 (`VillageInteraction`).
>
> **Principle:** Phase 1 has no recommendation engine yet, but every user interaction
> should be captured to fuel Phase 2 (content-based) and Phase 2+ (Surprise SVD).
> The more data Phase 1 collects, the better Phase 2 recommendations will be on day one.

## What Phase 1 captures

| Source                                           | Table                  | Volume estimate (per user session) |
|--------------------------------------------------|------------------------|-------------------------------------|
| Every `POST /estimate/stay` call                 | `SimulationLog`        | 1–5 rows                            |
| Every `GET /go/{token}` (booking redirect)       | `BookingClick`         | 0–2 rows (most users don't click)   |
| Frontend signals (`view`, `step_complete`, etc.) | `VillageInteraction`   | 5–20 rows                           |

## What we capture (and why)

### `SimulationLog` — primary table

Created on **every** `/estimate/stay` call. Captures:

| Bucket            | Fields                                                    | Used by                                |
|-------------------|-----------------------------------------------------------|----------------------------------------|
| **What they searched** | `village`, `region`, `formule`, `saison_key`, `date_debut`, `date_fin`, `nuits` | Content-based scoring, popularity      |
| **Who they are**       | `nb_adults`, `nb_children`, `children_ages`, `qf_val`, `qf_badge`, `is_solo_parent`, `is_maxi_family` | User profile, segmentation             |
| **What they got**      | `estimated_total`, `per_person_per_day`, `discount_rate`, `promos_applied`, `transport_mode`, `transport_cost`, `activities_cost`, `resto_cost` | Tarif analytics, A/B tests           |
| **Hotel comparison**   | `hotel_estimate`, `hotel_savings`, `savings_pct`          | Marketing copy, "you save X%" widget   |
| **Behavior signals**   | `clicked_booking`, `booking_click_at`, `time_on_result_ms` | Conversion weighting, SVD ratings     |
| **Meta**               | `session_id`, `created_at`, `ip_hash` (sha256), `user_agent` (truncated 256ch) | Sessionization, GDPR-safe analytics |
| **Optional context**   | `referrer`, `utm_source`, `device_type`, `step_timings`   | Acquisition analytics, engagement      |

Full model: see `03-data-models.md`.

### `BookingClick` — conversion signal

Created on every `GET /api/v1/go/{token}` (the token-redirect endpoint, see
`11-booking-redirect.md`). Strongest implicit signal for SVD (rating = 5.0).

The flow:
1. Frontend renders results → token minted via `POST /villages/{id}/booking-link` (or
   inlined inside `/estimate/stay` and `/recommend/villages` responses).
2. User clicks "Réserver sur VTF" → browser GETs `/api/v1/go/{token}`.
3. Token verified → 302 to VTF booking page.
4. `BookingClick` row written async (`transaction.on_commit`) with full reco context
   (`source`, `recoStrategy`, `recoScore`, `recoRank`).

Carries enough metadata to attribute the click to the simulation/recommendation that
produced it — this is what powers the conversion analytics in `11-booking-redirect.md` §5.

### `VillageInteraction` — lightweight signals

Captured via `POST /api/v1/signals` (no calculation, just INSERT).

| Signal             | When                                  | Payload                                                      |
|--------------------|---------------------------------------|--------------------------------------------------------------|
| `session_start`    | App load                              | `{ sessionId, referrer, utmSource }`                         |
| `village_view`     | User selects a village in dropdown    | `{ sessionId, villageId, stepNumber }`                       |
| `step_complete`    | User advances a step                  | `{ sessionId, step: 'family|sejour|extras|transport|promos', durationMs }` |
| `result_view`      | Results page rendered                 | `{ sessionId, villageId, total, timeToResultMs }`            |
| `result_dwell`     | User leaves results page              | `{ sessionId, villageId, dwellTimeMs, scrollDepthPct }`      |
| `recap_view`       | Recap page opened                     | `{ sessionId, villageId }`                                   |
| `share_click`      | User clicks share/PDF                 | `{ sessionId, villageId, shareMethod: 'pdf|share_api|copy' }`|
| `compare_villages` | User changes village mid-flow         | `{ sessionId, fromVillageId, toVillageId }`                  |

Each signal becomes one `VillageInteraction` row. Cost per request: ~5ms (single INSERT).

## Logging integration (zero-cost for the user)

Logging is **inside** the existing estimate view, in a `transaction.on_commit` callback so
the calculation responds even if the log fails:

```python
# apps/pricing/views.py
from django.db import transaction
import hashlib

from apps.pricing.models import SimulationLog


def get_client_ip(request) -> str:
    return request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0].strip()


class EstimateStayView(APIView):
    def post(self, request):
        ser = EstimateStayInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        village = Village.objects.values().get(pk=data["villageId"])
        rules = PricingRules.active()

        est = stay_estimate.estimate_sejour_total(
            family=data["family"], sejour=data["sejour"],
            village=village, pricing_rules=rules,
        )
        if est is None:
            return Response({"detail": "estimation impossible"}, status=400)

        # Log async (post-commit, non-blocking)
        meta = data.get("_meta", {}) or {}
        transaction.on_commit(lambda: SimulationLog.objects.create(
            session_id=request.headers.get("X-Session-ID", "") or meta.get("sessionId", ""),
            village_id=data["villageId"],
            region=village["region"],
            formule=data["sejour"]["formule"],
            saison_key=est.saison_key,
            date_debut=data["sejour"]["dateDebut"],
            date_fin=data["sejour"]["dateFin"],
            nuits=est.nuits,
            nb_adults=data["family"]["adultes"],
            nb_children=len(data["family"]["enfants"]),
            children_ages=[c["age"] for c in data["family"]["enfants"]],
            qf_val=data["family"].get("qfVal"),
            qf_badge=_qf_badge_kind(data["family"].get("qfVal")),
            is_solo_parent=(data["family"]["adultes"] == 1 and len(data["family"]["enfants"]) >= 1),
            is_maxi_family=bool(data["family"].get("maxiFamily")),
            estimated_total=est.total,
            per_person_per_day=(est.per_person // est.nuits) if est.nuits else 0,
            discount_rate=est.discount_rate,
            promos_applied=_collect_promos(data["sejour"].get("promos", {})),
            transport_mode=(data["sejour"].get("transport") or {}).get("mode", ""),
            transport_cost=est.transport_total,
            activities_cost=est.activities_total,
            resto_cost=est.resto_total,
            hotel_estimate=est.hotel_estimate,
            hotel_savings=est.hotel_savings,
            savings_pct=est.savings_pct,
            ip_hash=hashlib.sha256(get_client_ip(request).encode()).hexdigest(),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:256],
            referrer=meta.get("referrer", "")[:256],
            utm_source=meta.get("utmSource", "")[:64],
            device_type=meta.get("deviceType", "")[:16],
            step_timings=meta.get("stepTimings", {}),
        ))

        return Response(asdict(est))
```

## Frontend instrumentation (recommended)

Add a tiny `api/signals.ts` helper in `vtf/front/src/`:

```ts
const SIGNAL_URL = `${import.meta.env.VITE_API_URL}/api/v1/signals`

let sessionId = sessionStorage.getItem('sid') || crypto.randomUUID()
sessionStorage.setItem('sid', sessionId)

export function emitSignal(kind: string, payload: Record<string, unknown> = {}) {
  // Use sendBeacon when available (works during page unload)
  const body = JSON.stringify({ kind, sessionId, payload })
  if (navigator.sendBeacon) {
    navigator.sendBeacon(SIGNAL_URL, new Blob([body], { type: 'application/json' }))
  } else {
    fetch(SIGNAL_URL, { method: 'POST', body, headers: { 'Content-Type': 'application/json' }, keepalive: true })
  }
}
```

Wire-up examples:

```ts
// On app load
emitSignal('session_start', {
  referrer: document.referrer,
  utmSource: new URLSearchParams(location.search).get('utm_source'),
})

// On village select
emitSignal('village_view', { villageId, stepNumber: 2 })

// On step complete
emitSignal('step_complete', { step: 'sejour', durationMs: Date.now() - stepStartedAt })

// On result page unload
useEffect(() => {
  const start = Date.now()
  return () => {
    emitSignal('result_dwell', {
      villageId,
      dwellTimeMs: Date.now() - start,
      scrollDepthPct: getMaxScrollPct(),
    })
  }
}, [villageId])
```

## Mapping: signals → SVD ratings

When the SVD model is trained later, we convert these signals to implicit ratings:

| Signal                          | Implicit rating (1–5) |
|---------------------------------|-----------------------|
| `village_view` (selected only)  | 1.0                   |
| `/estimate/stay` (1 simulation) | 2.0                   |
| `/estimate/stay` (≥ 2 sims)     | 2.5                   |
| `result_view`                   | 3.0                   |
| `recap_view`                    | 3.5                   |
| `share_click`                   | 4.0                   |
| `bookmark`                      | 4.0                   |
| `clicked_booking` (BookingClick)| 5.0                   |

We keep the **max** rating per (session, village). See `07-svd-roadmap.md` for the matrix
construction code.

## Session labeling (Phase 2 enrichment)

Once a session has produced rows in the three tables above, an hourly cron
(`label_sessions [--use-llm]`) computes **labels** that classify the family + intent
(e.g. `family:with_baby`, `intent:converter`, `budget:price_sensitive`). These labels feed:

- The recommender scoring loop (boost certain dimensions per label)
- The popularity ranking (segmented per cohort)
- Analytics dashboards (readable session profiles)

Two layers:
1. **Rule-based** (default, deterministic, no external dep) — `SESSION_LABELING_ENABLED=true`
2. **LLM-enriched** (Ollama local first, Mistral cloud fallback) — `SESSION_LABELING_USE_LLM=true`

Full taxonomy and pipeline: see `07-recommendation-engine.md` §11.

## What feeds what (Phase 1 → Phase 2)

```
SimulationLog ──────────────────────┬──→ Content-based scoring (Tier 1)
  (every POST /estimate/stay)       │     (family profile → village attributes)
                                    │
VillageInteraction ─────────────────┼──→ Popularity ranking (Tier 4)
  (view, simulate, bookmark, …)     │     (VillagePopularityCache, refreshed every 6 h)
                                    │
BookingClick ───────────────────────┼──→ Conversion weighting (rating 5.0 in SVD)
  (every GET /go/{token})           │     (recommend villages that convert)
                                    │
                                    └──→ SVD collaborative filtering (Phase 2+)
                                          (session × village implicit rating matrix)
```

Every field in `SimulationLog`, `BookingClick`, and `VillageInteraction` has a **specific
consumer** in Phase 2. Nothing is logged "just in case" — each field maps to a scoring
dimension or an analytics query (see `11-booking-redirect.md` §5 for the BookingClick
analytics catalog, and `07-recommendation-engine.md` §2 for the scoring dimensions).

## GDPR considerations

| Field          | Treatment                                                      |
|----------------|----------------------------------------------------------------|
| IP             | Stored as sha256 hash with daily salt (`SECRET_IP_SALT`)        |
| User-Agent     | Truncated to 256 chars, kept as-is (no PII)                     |
| Session ID     | Random UUID generated client-side, no link to identity          |
| Referrer       | Truncated to 256 chars                                          |
| `utm_source`   | Free text, truncated to 64 chars                                |
| Retention      | 90 days hot (Postgres), 1 year cold (S3 + monthly aggregates)   |
| Right to erase | `DELETE FROM simulation_log WHERE ip_hash = ?` (rare; never asked because of anonymization, but supported) |

Add a privacy banner to the frontend once data collection is live.
