# 08 — Cache orchestrator + scraping (Phase 3 — 3 weeks)

> Spec source: §5.1 (cache) + §5.2 (scraping). **Duration: 3 weeks** (per §5).
>
> Phase 3 is when the catalog stops being static. This doc describes the two systems
> that keep it fresh: Redis cache invalidation and an activity-discovery scraping pipeline.
> See `09-implementation-roadmap.md` Phase 3 for the week-by-week plan.

## 1. Cache orchestrator

### Goals

- One service responsible for all cache key lifecycle (`apps/cache_orchestrator/`).
- Auto-rebuild on data changes (Django signals).
- Manual rebuild via admin endpoint and management command.
- Audit log of every rebuild.

### Admin endpoint (US-5.1)

```
POST /api/v1/admin/cache/rebuild
Auth: Staff (Django session or token)
Body: { "scope": "all" | "catalog" | "pricing" | "villages:{id}" | "regions:{key}" | "recommendations" | "booking_urls", "reason": "..." }
```

Response:

```json
{
  "status": "completed",
  "scope": "all",
  "keysInvalidated": 847,
  "keysRebuilt": 847,
  "durationMs": 1230,
  "triggeredBy": "admin@house-of-communication.fr",
  "reason": "New pricing rules uploaded for summer 2027",
  "timestamp": "2026-09-15T14:32:00Z"
}
```

Architecture flow:

```
POST /admin/cache/rebuild { scope: "catalog" }
  │
  ▼
CacheOrchestrator.rebuild(scope)
  │
  ├─→ 1. Invalidate: delete all keys matching scope pattern
  │      redis.delete(*redis.keys("vtf:catalog:*"))
  │
  ├─→ 2. Warm: pre-populate critical endpoints
  │      ├─ GET /villages (list)
  │      ├─ GET /villages/{id} (each of 32)
  │      ├─ GET /regions (list)
  │      ├─ GET /regions/{r}/activities (each of 8)
  │      ├─ GET /pricing-rules
  │      └─ GET /seasons
  │
  ├─→ 3. Log: CacheRebuildLog entry
  │
  └─→ 4. Notify: webhook / Slack (optional, env-gated)
```

### Scope catalog

| Scope                     | What it clears & rebuilds                            | Typical trigger                                  |
|---------------------------|------------------------------------------------------|--------------------------------------------------|
| `all`                     | Everything below                                     | Major data update                                |
| `catalog`                 | Villages, regions, activities, animations, meals, fuels | New village added / village data changed     |
| `pricing`                 | Pricing rules, season calendar, promo catalog        | Pricing rules updated                            |
| `villages:{id}`           | Single village detail + attractions + highlights     | Village-specific correction                      |
| `regions:{key}`           | Single region + its activities                       | Regional activity update                         |
| `recommendations`         | Popularity cache, CF model cache                     | Interaction data reset                           |
| `booking_urls`            | All pre-built VTF target URLs                        | VTF website URL structure changed                |

### Cache key naming convention (spec §5.1)

```
vtf:catalog:villages:list                     → GET /villages
vtf:catalog:villages:{id}:detail              → GET /villages/{id}
vtf:catalog:villages:{id}:attractions         → GET /villages/{id}/attractions
vtf:catalog:regions:list                      → GET /regions
vtf:catalog:regions:{key}:activities          → GET /regions/{key}/activities
vtf:catalog:pricing_rules                     → GET /pricing-rules
vtf:catalog:seasons                           → GET /seasons
vtf:catalog:meals                             → GET /meals
vtf:catalog:fuels                             → GET /fuels
vtf:catalog:promos_catalog                    → GET /promos/catalog
vtf:reco:popularity:{village_id}              → popularity score
vtf:reco:cf_model                             → serialized SVD model
vtf:booking:token:{token}                     → redirect token payload
```

### Key registry (`apps/cache_orchestrator/key_registry.py`)

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CacheKey:
    pattern: str
    ttl_seconds: int
    description: str


REGISTRY: dict[str, CacheKey] = {
    # Catalog (slow-changing)
    "vtf:catalog:villages:list":             CacheKey("vtf:catalog:villages:list",        86400, "All villages list"),
    "vtf:catalog:villages:{id}:detail":      CacheKey("vtf:catalog:villages:*:detail",    86400, "Single village + relations"),
    "vtf:catalog:regions:list":              CacheKey("vtf:catalog:regions:list",        604800, "Regions list"),
    "vtf:catalog:regions:{key}:activities":  CacheKey("vtf:catalog:regions:*:activities", 86400, "Activities by region"),
    "vtf:catalog:pricing_rules":             CacheKey("vtf:catalog:pricing_rules",        86400, "Active pricing rules"),
    "vtf:catalog:seasons":                   CacheKey("vtf:catalog:seasons",             604800, "Season calendar"),
    "vtf:catalog:meals":                     CacheKey("vtf:catalog:meals",               604800, "Meals reference"),
    "vtf:catalog:fuels":                     CacheKey("vtf:catalog:fuels",               604800, "Fuels reference"),
    "vtf:catalog:promos_catalog":            CacheKey("vtf:catalog:promos_catalog",      604800, "Promo catalog"),

    # Recommender
    "vtf:reco:popularity:{id}":              CacheKey("vtf:reco:popularity:*",            21600, "Per-village popularity"),
    "vtf:reco:cf_model":                     CacheKey("vtf:reco:cf_model",               172800, "Trained SVD model"),

    # Booking
    "vtf:booking:token:{token}":             CacheKey("vtf:booking:token:*",             259200, "Redirect token payload (72h)"),
}
```

### Trigger sources

| Trigger                 | Scope                  | Method                                                  |
|-------------------------|------------------------|---------------------------------------------------------|
| `PricingRules.save()`   | `catalog`              | `post_save` signal → `CacheOrchestrator.rebuild('catalog')` |
| `Village.save()`        | `catalog`              | idem                                                    |
| `Activity.save()`       | `catalog`              | idem                                                    |
| Daily 03:30 cron        | `reco`                 | `python manage.py rebuild_cache reco`                   |
| Admin endpoint          | `catalog|reco|booking|all` | `POST /api/v1/admin/cache/rebuild`                  |
| Manual                  | any                    | `python manage.py rebuild_cache <scope>`                |

### Service

```python
# apps/cache_orchestrator/service.py
import time
from django.core.cache import cache

from .key_registry import REGISTRY
from .models import CacheRebuildLog


SCOPE_PATTERNS = {
    "catalog":  ["vtf:catalog:*"],
    "reco":     ["vtf:reco:*"],
    "booking":  ["vtf:booking:*"],
    "all":      ["vtf:*"],
}


class CacheOrchestrator:
    @staticmethod
    def rebuild(scope: str, *, triggered_by: str = "manual") -> CacheRebuildLog:
        log = CacheRebuildLog.objects.create(scope=scope, triggered_by=triggered_by)
        try:
            keys_invalidated = 0
            for pattern in SCOPE_PATTERNS.get(scope, []):
                keys_invalidated += cache.delete_pattern(pattern)
            log.keys_invalidated = keys_invalidated
            log.finished_at = time.time()
        except Exception as e:
            log.error = str(e)[:1024]
            raise
        finally:
            log.save()
        return log
```

> `cache.delete_pattern` requires `django-redis` (Redis backend). Use `redis-py` directly
> if you're on a different backend.

### Signal-driven invalidation

```python
# apps/catalog/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.catalog.models import Activity, PricingRules, Village
from apps.cache_orchestrator.service import CacheOrchestrator


@receiver(post_save, sender=Village)
@receiver(post_save, sender=Activity)
@receiver(post_save, sender=PricingRules)
def _invalidate_catalog(sender, **kwargs):
    CacheOrchestrator.rebuild("catalog", triggered_by=f"signal:{sender.__name__}.save")
```

### Admin endpoint

```python
# apps/cache_orchestrator/views.py
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .service import CacheOrchestrator


class RebuildCacheView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        scope = request.data.get("scope", "all")
        log = CacheOrchestrator.rebuild(scope, triggered_by=f"admin:{request.user.username}")
        return Response({"keysInvalidated": log.keys_invalidated, "logId": log.id})
```

## 2. Scraping pipeline

### Goals

- Discover new paid activities around each region (Google Places, TripAdvisor, OT local).
- Land scraped records in a **staging table** (`ScrapingCandidate`).
- Provide a UI for staff to review + promote into `apps.catalog.Activity`.
- Detect price changes on existing activities → `PriceChangeAlert`.

### Adapter ABC

```python
# apps/scraper/adapters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ScrapedActivity:
    nom: str
    type: str
    region: str
    price_adult: int | None = None
    price_child: int | None = None
    raw_payload: dict | None = None


class ActivitySourceAdapter(ABC):
    name: str

    @abstractmethod
    def scrape(self, *, region: str, village_id: str | None = None) -> list[ScrapedActivity]: ...
```

Concrete adapters: `GooglePlacesAdapter`, `TripAdvisorAdapter`, `OtLocalAdapter`.

### Dedup engine

```python
# apps/scraper/dedup.py
from rapidfuzz import fuzz

from apps.catalog.models import Activity


def find_duplicate(candidate: ScrapedActivity, *, threshold: int = 85) -> Activity | None:
    """Returns existing Activity if fuzzy name match + same region + similar price."""
    qs = Activity.objects.filter(region=candidate.region)
    for act in qs:
        score = fuzz.token_sort_ratio(candidate.nom, act.nom)
        if score >= threshold:
            # Optional: also check price proximity within ±20%
            return act
    return None
```

### Pipeline

```python
# apps/scraper/management/commands/scrape_activities.py
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.scraper.adapters import GooglePlacesAdapter, TripAdvisorAdapter, OtLocalAdapter
from apps.scraper.dedup import find_duplicate
from apps.scraper.models import ScrapingJob, ScrapingCandidate, PriceChangeAlert
from apps.catalog.models import Activity


ADAPTERS = [GooglePlacesAdapter(), TripAdvisorAdapter(), OtLocalAdapter()]


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--region", required=True)

    def handle(self, *args, region: str, **opts):
        for adapter in ADAPTERS:
            job = ScrapingJob.objects.create(source=adapter.name, region=region)
            try:
                candidates = adapter.scrape(region=region)
                for c in candidates:
                    dup = find_duplicate(c)
                    cand = ScrapingCandidate.objects.create(
                        job=job, nom=c.nom, type=c.type, region=c.region,
                        price_adult=c.price_adult, price_child=c.price_child,
                        raw_payload=c.raw_payload or {},
                        duplicate_of=dup,
                    )
                    # Detect price changes on duplicates
                    if dup and c.price_adult is not None and dup.price_adult and c.price_adult != dup.price_adult:
                        PriceChangeAlert.objects.create(
                            activity=dup, field="price_adult",
                            old_value=dup.price_adult, new_value=c.price_adult,
                        )
                job.candidates_found = len(candidates)
            except Exception as e:
                job.error = str(e)[:2048]
                raise
            finally:
                job.finished_at = timezone.now()
                job.save()
```

### Review UI (admin endpoint)

```python
# apps/scraper/views.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.catalog.models import Activity
from .models import ScrapingCandidate
from .serializers import ScrapingCandidateSerializer


class ScrapingCandidateViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = ScrapingCandidate.objects.filter(reviewed_at__isnull=True)
    serializer_class = ScrapingCandidateSerializer

    @action(detail=True, methods=["post"])
    def promote(self, request, pk=None):
        cand = self.get_object()
        if cand.duplicate_of:
            # Update prices in place
            if cand.price_adult is not None:
                cand.duplicate_of.price_adult = cand.price_adult
            if cand.price_child is not None:
                cand.duplicate_of.price_child = cand.price_child
            cand.duplicate_of.save()
            cand.promoted_to = cand.duplicate_of
        else:
            new_act = Activity.objects.create(
                code=f"scraped:{cand.region[:3]}:{cand.id}",
                region=cand.region, kind=Activity.KIND_PAID,
                nom=cand.nom, type=cand.type,
                price_adult=cand.price_adult or 0, price_child=cand.price_child or 0,
                saisons=["hs", "vs", "ete", "fetes"],
            )
            cand.promoted_to = new_act
        cand.reviewed_at = timezone.now()
        cand.reviewed_by = request.user.username
        cand.save()
        return Response({"promotedTo": cand.promoted_to.code})
```

## 3. Phase 3 dataflow diagram

```
Phase 3 additions
─────────────────

┌─────────────────────┐
│ Cache Orchestrator  │
│                     │
│ Redis key patterns: │
│  vtf:catalog:*      │ ◄── auto-rebuild on PricingRules.save()
│  vtf:reco:*         │ ◄── auto-rebuild on popularity refresh
│  vtf:booking:*      │ ◄── auto-rebuild on VTF URL change
│                     │
│ Triggers:           │
│  • Admin endpoint   │
│  • Django signals   │
│  • Management cmd   │
└─────────────────────┘

┌─────────────────────┐    ┌──────────────────┐
│ Scraping Engine     │───▶│ ScrapingCandidate│
│                     │    │ (staging table)  │
│ Adapters:           │    └────────┬─────────┘
│  • Google Places    │             │ human review
│  • TripAdvisor      │             ▼
│  • OT local         │    ┌──────────────────┐
│                     │    │ Activity         │
│ Dedup engine:       │    │ (catalog)        │──▶ cache rebuild
│  • fuzzy name match │    └──────────────────┘
│  • geo proximity    │
│  • price similarity │    ┌──────────────────┐
└─────────────────────┘    │ PriceChangeAlert │──▶ staff notification
                           └──────────────────┘
```

## 4. Cache health monitoring

`GET /api/v1/health` (spec §US-5.3) includes cache stats:

```json
{
  "status": "ok",
  "version": "1.2.0",
  "dataVersion": "2026-09-15",
  "cache": {
    "backend": "redis",
    "connected": true,
    "totalKeys": 847,
    "memoryUsedMb": 12.4,
    "hitRatePercent": 94.2,
    "lastRebuild": "2026-09-15T14:32:00Z",
    "lastRebuildScope": "all",
    "oldestKeyAgeSec": 3420
  }
}
```

## 5. Scraping admin endpoints (spec §5.2)

| Method | Path                                            | Purpose                                                |
|--------|-------------------------------------------------|--------------------------------------------------------|
| `POST` | `/api/v1/admin/scraper/activities`              | Trigger a job (target village or region)               |
| `GET`  | `/api/v1/admin/scraper/jobs/{jobId}`            | Poll job status + candidates                           |
| `POST` | `/api/v1/admin/scraper/import`                  | Approve / reject / edit candidates                     |
| `GET`  | `/api/v1/admin/scraper/price-updates`           | List `PriceChangeAlert` rows pending review            |

### Trigger request

```json
{
  "target": "village",
  "villageId": "biarritz",
  "sources": ["tripadvisor", "google_places", "ot_local"],
  "radiusKm": 30,
  "maxResults": 20,
  "autoImport": false
}
```

### Trigger response (async)

```json
{
  "jobId": "scrape-biarritz-20260915-143200",
  "status": "queued",
  "estimatedDurationSec": 45,
  "pollUrl": "/api/v1/admin/scraper/jobs/scrape-biarritz-20260915-143200"
}
```

### Job result (poll or webhook)

```json
{
  "jobId": "scrape-biarritz-20260915-143200",
  "status": "completed",
  "village": "biarritz",
  "sources": {
    "tripadvisor":   { "found": 22, "new": 5, "duplicates": 17 },
    "google_places": { "found": 34, "new": 8, "errors": 0 },
    "ot_local":      { "found": 12, "new": 3, "errors": 1 }
  },
  "candidates": [
    {
      "candidateId": "cand-001",
      "nom": "Aquarium de Biarritz",
      "type": "parc",
      "source": "tripadvisor",
      "sourceUrl": "https://tripadvisor.com/...",
      "priceAdult": 17,
      "priceChild": 11,
      "distanceKm": 2.5,
      "rating": 4.3,
      "reviewCount": 1842,
      "matchedExisting": "paid:al:aquarium-biarritz",
      "status": "existing_match",
      "confidence": 0.95
    }
  ],
  "summary": { "totalNew": 12, "totalUpdated": 6, "totalDuplicates": 28, "readyForReview": 12 }
}
```

### Import request

```json
{
  "jobId": "scrape-biarritz-20260915-143200",
  "actions": [
    { "candidateId": "cand-002", "action": "import", "edits": { "nom": "École de surf …" } },
    { "candidateId": "cand-003", "action": "reject", "reason": "Permanently closed" },
    { "candidateId": "cand-004", "action": "import" },
    { "candidateId": "cand-005", "action": "defer" }
  ]
}
```

On import, the system:
1. Creates `Activity` rows with generated `code` (`scraped:{region3}:{slug}`).
2. Sets `saisons` from source data (default: all seasons).
3. Triggers `CacheOrchestrator.rebuild(scope="regions:{region}")`.
4. Logs every action in `ScrapingImportLog`.

## 6. Source adapter ABC (spec §5.2)

```python
# apps/scraper/adapters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ScrapedActivity:
    source: str
    source_id: str
    source_url: str
    nom: str
    type_hint: str                        # 'museum' | 'sport' | 'nature' | 'park' | ...
    price_adult: int | None
    price_child: int | None
    latitude: float
    longitude: float
    rating: float | None
    review_count: int
    description: str
    image_url: str | None


class ActivitySourceAdapter(ABC):
    """Base class for all scraping adapters."""
    name: str

    @abstractmethod
    def search_near(
        self, *, lat: float, lng: float, radius_km: int, max_results: int
    ) -> list[ScrapedActivity]: ...

    @abstractmethod
    def get_details(self, source_id: str) -> ScrapedActivity | None: ...
```

Concrete adapters: `GooglePlacesAdapter`, `TripAdvisorAdapter`, `OfficeTourismeAdapter`.

## 7. Dedup & match confidence (spec §5.2)

```python
def match_confidence(candidate: ScrapedActivity, existing: Activity) -> float:
    score = 0.0
    # Name similarity (0–0.4)
    name_sim = SequenceMatcher(None, normalize(candidate.nom), normalize(existing.nom)).ratio()
    score += name_sim * 0.4
    # Geo proximity (0–0.3)  — 0.3 at 0 km, 0 at 5 km
    if candidate.latitude and getattr(existing, "latitude", None):
        dist_km = haversine(candidate.latitude, candidate.longitude, existing.latitude, existing.longitude)
        score += max(0.0, 0.3 - dist_km * 0.06)
    # Price match (0–0.2)
    if candidate.price_adult and existing.price_adult:
        ratio = min(candidate.price_adult, existing.price_adult) / max(candidate.price_adult, existing.price_adult)
        score += ratio * 0.2
    # Type match (0–0.1)
    if candidate.type_hint == existing.type:
        score += 0.1
    return score
```

> Auto-import is gated on `match_confidence > 0.9` AND `autoImport=true` in the trigger
> request (spec AC-3.10). Otherwise candidates land in staging for human review.

## 8. Price-change detection (spec §US-5.7)

When re-scraping an existing activity (matched via `source_id` or fuzzy):

```python
def detect_price_changes(existing: Activity, scraped: ScrapedActivity) -> list[PriceChangeAlert]:
    alerts = []
    for field in ("price_adult", "price_child"):
        old = getattr(existing, field) or 0
        new = getattr(scraped, field) or 0
        if old and new and abs(new - old) / old > 0.10:        # > 10 % delta
            alerts.append(PriceChangeAlert.objects.create(
                activity=existing, field=field, old_value=old, new_value=new,
                source=scraped.source, scraped_at=timezone.now(), status="pending",
            ))
    return alerts
```

Notification format (Slack / email):

```
⚠ Price change detected:
   Activity: Aquarium de Biarritz (paid:al:aquarium-biarritz)
   Adult: 17€ → 19€ (+12 %)
   Child: 11€ → 13€ (+18 %)
   Source: tripadvisor (scraped 2026-10-01)
   Action required: Approve or dismiss at /admin/scraper/price-updates/
```

## 9. Acceptance criteria (Phase 3, spec §5.3)

| ID       | Criterion                                                                   |
|----------|-----------------------------------------------------------------------------|
| AC-3.1   | `POST /admin/cache/rebuild` clears and warms all keys for given scope       |
| AC-3.2   | Full cache rebuild < 5 s for 32 villages                                    |
| AC-3.3   | Zero stale reads during rebuild (atomic key swap)                           |
| AC-3.4   | `load_vtf_mocks` auto-triggers `scope=all` rebuild                          |
| AC-3.5   | `PricingRules.save()` auto-triggers `scope=pricing` rebuild                 |
| AC-3.6   | Health endpoint reports cache stats                                         |
| AC-3.7   | Scraping job completes < 60 s per village (all sources)                     |
| AC-3.8   | Deduplication correctly matches existing activities (> 90 % precision)      |
| AC-3.9   | New candidates stored with `status=new`, not auto-imported                  |
| AC-3.10  | `autoImport=true` only for high-confidence matches (> 0.9)                  |
| AC-3.11  | Price-change detection flags differences > 10 %                             |
| AC-3.12  | Import triggers targeted cache rebuild for affected region                  |
| AC-3.13  | Monthly cron scrapes all 32 villages without rate-limit issues              |
| AC-3.14  | Source adapters gracefully handle API errors / rate limits                  |

## 10. Open questions

| Question                                                  | Default answer                                  |
|-----------------------------------------------------------|-------------------------------------------------|
| Where do API keys (Google, TripAdvisor) live?             | `config/settings/prod.py` → env vars (`GOOGLE_PLACES_API_KEY`, `TRIPADVISOR_API_KEY`) |
| What's the scrape cadence?                                | Monthly cron per region; on-demand via admin    |
| What if the API quota is exceeded?                        | Fail soft: log and skip, alert via Sentry       |
| Should we auto-promote candidates with high confidence?   | Only if `autoImport=true` AND confidence > 0.9  |
| Retention of `ScrapingCandidate`?                         | 90 days after promotion or rejection            |
| Use Claude API to classify activity type?                 | Yes (Phase 3+) — `ANTHROPIC_API_KEY` env var, see spec §8.1 |
