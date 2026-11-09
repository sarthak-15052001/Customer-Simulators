# 03 — Django data models

> One model per concept. Reuse `JSONField` aggressively for blob-shaped data that
> evolves as a unit (e.g. `tarifs`).

## `apps/catalog/models.py`

### Choices

```python
from django.db import models


class Region(models.TextChoices):
    BRETAGNE_NORMANDIE = "Bretagne / Normandie"
    AQUITAINE_LANDES = "Aquitaine / Landes"
    MEDITERRANEE_PACA = "Méditerranée / PACA"
    ALPES_SAVOIE = "Alpes / Savoie"
    ALPES_DU_SUD = "Alpes du Sud"
    MASSIF_CENTRAL_JURA = "Massif Central / Jura"
    CAMPAGNE_PROVENCE = "Campagne / Provence"
    OCCITANIE_PYRENEES = "Occitanie / Pyrénées"


class Saison(models.TextChoices):
    HS = "hs", "Hors saison"
    VS = "vs", "Vacances scolaires"
    ETE = "ete", "Été"
    FETES = "fetes", "Fêtes"


class Formule(models.TextChoices):
    PC = "PC", "Pension complète"
    DP = "DP", "Demi-pension"
    LOC = "LOC", "Location"


class EnvCode(models.TextChoices):
    SEA = "sea", "Bord de mer"
    MOUNTAIN = "mountain", "Montagne"
    FOREST = "forest", "Nature/forêt"
    COUNTRYSIDE = "countryside", "Campagne"
    SUN = "sun", "Soleil/Méditerranée"
```

### `Village`

```python
class Village(models.Model):
    """
    A VTF holiday resort. 32 entries today (May 2026).
    Source: vtf/front/src/mocks/vtfStay.mock.json
    """
    id = models.SlugField(primary_key=True, max_length=64)
    nom = models.CharField(max_length=128)
    nom2 = models.CharField(max_length=128, blank=True, default="")
    region = models.CharField(max_length=64, choices=Region.choices)

    # Environment (kept dual to ease migration: emoji for legacy, code for API consumers)
    env_emoji = models.CharField(max_length=8)             # 🌊 ⛰️ 🌲 🌻 ☀️
    env_code = models.CharField(max_length=16, choices=EnvCode.choices)

    formules = models.JSONField()                          # ['PC','DP','LOC']
    has_loc = models.BooleanField()
    ski = models.BooleanField()
    ouverture = models.CharField(max_length=256, blank=True, default="")
    tarifs = models.JSONField()                            # { 'PC': {hs,vs,ete,fetes}, 'LOC': ... }

    # Optional flags (drive highlights + tarif rules)
    bebe_club = models.BooleanField(default=False)
    forfait_rm = models.BooleanField(default=False)
    qf_exc = models.BooleanField(default=False)
    enf_solo_half = models.BooleanField(default=False)

    # VTF booking redirect
    vtf_department = models.CharField(max_length=64, blank=True, default="")
    vtf_city = models.CharField(max_length=64, blank=True, default="")
    vtf_slug = models.CharField(max_length=128, blank=True, default="")
    vtf_url_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["region", "nom"]
        indexes = [
            models.Index(fields=["region"]),
            models.Index(fields=["env_code"]),
            models.Index(fields=["ski"]),
        ]

    def __str__(self) -> str:
        return self.nom
```

### `Attraction`

```python
class Attraction(models.Model):
    """
    Nearby landmarks (Mont-Blanc, Calanques, etc.) for a village.
    Source: vtfStay.mock.json:attractionsProches (originally keyed by `nom`,
    re-keyed by `village_id` on load).
    """
    village = models.ForeignKey(Village, on_delete=models.CASCADE, related_name="attractions")
    nom = models.CharField(max_length=128)
    type = models.CharField(max_length=128)
    icon = models.CharField(max_length=8)
    km = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["km"]
```

### `Activity`

```python
class Activity(models.Model):
    """
    Free or paid activity around a region (not bound to a single village).
    Source: vtfExtras.mock.json:actGratuit / activitesPayantes
    """
    KIND_FREE = "free"
    KIND_PAID = "paid"
    KIND_CHOICES = [(KIND_FREE, "Gratuite"), (KIND_PAID, "Payante")]

    code = models.CharField(max_length=64, unique=True)         # ex: "paid:al:surf"
    region = models.CharField(max_length=64, choices=Region.choices)
    kind = models.CharField(max_length=4, choices=KIND_CHOICES)
    nom = models.CharField(max_length=128)
    type = models.CharField(max_length=8)                       # emoji
    price_adult = models.PositiveSmallIntegerField(default=0)
    price_child = models.PositiveSmallIntegerField(default=0)
    saisons = models.JSONField(default=list)                    # ['hs','vs','ete','fetes']

    class Meta:
        ordering = ["region", "kind", "nom"]
        indexes = [
            models.Index(fields=["region", "kind"]),
        ]
```

### `Animation` (VTF-organized activities, regionless)

```python
class Animation(models.Model):
    """
    Source: vtfExtras.mock.json:vtfAnimations (4 fixed entries).
    """
    nom = models.CharField(max_length=128)
    note = models.CharField(max_length=256)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]
```

### `VillageInfra` & `VillageClubsEte` (per-village extras)

```python
class VillageInfra(models.Model):
    """
    Per-village infrastructure & seasonal animation copy.
    Source: vtfExtras.mock.json:vtfInfra (sparse — only `lacanau` today).
    """
    village = models.OneToOneField(Village, on_delete=models.CASCADE, related_name="infra")
    infra = models.JSONField(default=list)                      # ['🏊 Outdoor swimming pool', ...]
    anim_ete = models.JSONField(default=list)
    anim_hiver = models.JSONField(default=list)
    anim_hs = models.JSONField(default=list)
    extras_ete = models.TextField(blank=True, default="")
    extras_hiver = models.TextField(blank=True, default="")


class VillageClubsEte(models.Model):
    """
    Source: vtfExtras.mock.json:vtfClubsEte
    """
    village = models.OneToOneField(Village, on_delete=models.CASCADE, related_name="clubs")
    paques = models.JSONField(default=dict)                     # { bb, mini, maxi, ado }
    ete = models.JSONField(default=dict)
    toussaint = models.JSONField(default=dict)
```

### `PricingRules` (singleton)

```python
class PricingRules(models.Model):
    """
    Tarif rules used by stay_estimate. One active row at a time.
    Source: vtfPricingRules.mock.json
    """
    updated_at = models.DateField()
    payload = models.JSONField()                                # full mock payload
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"], condition=models.Q(is_active=True),
                name="unique_active_pricing_rules",
            ),
        ]
        ordering = ["-created_at"]

    @classmethod
    def active(cls) -> dict:
        return cls.objects.filter(is_active=True).values_list("payload", flat=True).first()
```

### `Meal`, `FuelOption`, `Promo` (currently hardcoded in TS — moved to fixtures)

```python
class Meal(models.Model):
    """
    Source: vtf/front/src/data/vtfResto.ts (hardcoded)
    """
    code = models.CharField(max_length=16, primary_key=True)    # 'pique','snack','bistrot','gastro'
    label = models.CharField(max_length=64)
    price_adult = models.PositiveSmallIntegerField()
    price_child = models.PositiveSmallIntegerField()
    order = models.PositiveSmallIntegerField(default=0)


class FuelOption(models.Model):
    """
    Source: vtf/front/src/data/vtfTransport.ts:VTF_FUELS
    """
    key = models.CharField(max_length=16, primary_key=True)     # 'essence','diesel','electrique'
    label = models.CharField(max_length=32)
    cost_per_km = models.DecimalField(max_digits=4, decimal_places=2)


class Promo(models.Model):
    """
    Catalog of named promos. Eligibility computed at request time by
    apps.pricing.services.promos.available_sejour_promos().
    Source: vtf/front/src/data/vtfPromos.ts:SEJOUR_PROMO_CATALOG
    """
    key = models.CharField(max_length=16, primary_key=True)     # 'premiere','derniere','jeudi','pack'
    icon = models.CharField(max_length=8)
    label = models.CharField(max_length=64)
    description = models.CharField(max_length=256)
    tag = models.CharField(max_length=16)
    rate = models.DecimalField(max_digits=4, decimal_places=2)  # 0.0–1.0
    kind = models.CharField(max_length=8, default="auto")
```

## `apps/pricing/models.py`

### `SimulationLog` (Phase 1 data foundation)

```python
class SimulationLog(models.Model):
    """
    Every /estimate/stay call is logged with full context.
    PRIMARY data source for Phase 2 recommendations & Phase 2+ SVD.
    """
    id = models.BigAutoField(primary_key=True)
    session_id = models.CharField(max_length=64, db_index=True)

    # ─── What they searched ───
    village = models.ForeignKey("catalog.Village", on_delete=models.SET_NULL, null=True)
    region = models.CharField(max_length=64)
    formule = models.CharField(max_length=4)
    saison_key = models.CharField(max_length=8)
    date_debut = models.DateField()
    date_fin = models.DateField()
    nuits = models.SmallIntegerField()

    # ─── Who they are ───
    nb_adults = models.SmallIntegerField()
    nb_children = models.SmallIntegerField()
    children_ages = models.JSONField(default=list)              # [4, 8, 12]
    qf_val = models.IntegerField(null=True)
    qf_badge = models.CharField(max_length=8, blank=True, default="")
    is_solo_parent = models.BooleanField(default=False)
    is_maxi_family = models.BooleanField(default=False)

    # ─── What they got ───
    estimated_total = models.IntegerField()
    per_person_per_day = models.IntegerField()
    discount_rate = models.FloatField()
    promos_applied = models.JSONField(default=list)             # ['qf_r1','premiere']
    transport_mode = models.CharField(max_length=16, blank=True, default="")
    transport_cost = models.IntegerField(default=0)
    activities_cost = models.IntegerField(default=0)
    resto_cost = models.IntegerField(default=0)

    # ─── Hotel comparison ───
    hotel_estimate = models.IntegerField(default=0)
    hotel_savings = models.IntegerField(default=0)
    savings_pct = models.FloatField(default=0)

    # ─── Behavior signals ───
    clicked_booking = models.BooleanField(default=False)        # set by booking-redirect view
    booking_click_at = models.DateTimeField(null=True, blank=True)
    time_on_result_ms = models.IntegerField(null=True, blank=True)

    # ─── Meta ───
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=256, blank=True, default="")

    # ─── Phase 2+ optional context ───
    referrer = models.CharField(max_length=256, blank=True, default="")
    utm_source = models.CharField(max_length=64, blank=True, default="")
    device_type = models.CharField(max_length=16, blank=True, default="")  # 'mobile'|'desktop'|'tablet'
    step_timings = models.JSONField(default=dict)               # {family: ms, sejour: ms, ...}

    class Meta:
        indexes = [
            models.Index(fields=["session_id", "created_at"]),
            models.Index(fields=["village", "saison_key"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]
```

### `BookingRedirectToken`

```python
class BookingRedirectToken(models.Model):
    """
    Signed-token bridge between a simulation result and the VTF booking page.
    Created by POST /api/v1/villages/{id}/booking-link.
    Consumed by GET /api/v1/go/{token} which 302s to target_url and logs BookingClick.
    Spec §US-2.8.
    """
    token = models.CharField(max_length=128, primary_key=True)            # HMAC-SHA256 signed
    village = models.ForeignKey("catalog.Village", on_delete=models.CASCADE)
    session_id = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField()                                          # family, dates, context
    target_url = models.URLField(max_length=512)                          # pre-built VTF URL
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()                                   # default created_at + 72h
    click_count = models.IntegerField(default=0)                          # incremented per redirect

    class Meta:
        indexes = [models.Index(fields=["expires_at"])]
```

### `BookingClick`

```python
class BookingClick(models.Model):
    """
    One row per click on a "Réserver sur VTF" link. Strongest implicit signal
    for the recommender. Created by GET /go/{token} (async via on_commit).
    Spec §US-2.8.
    """
    id = models.BigAutoField(primary_key=True)
    token = models.CharField(max_length=128, db_index=True)               # FK to BookingRedirectToken (denormalized)
    session_id = models.CharField(max_length=64, db_index=True)
    village = models.ForeignKey("catalog.Village", on_delete=models.CASCADE)

    # Source context: where in the funnel did this click originate?
    SOURCE_CHOICES = [
        ("estimate", "From /estimate/stay result"),
        ("recommendation", "From /recommend/villages"),
        ("similar", "From /villages/{id}/similar"),
        ("detail", "From village detail page"),
        ("recap", "From recap page"),
    ]
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES)

    # Family snapshot
    family_adults = models.SmallIntegerField()
    family_children = models.JSONField()                                  # [{"age": 2}, {"age": 7}]

    # Stay snapshot
    date_debut = models.DateField()
    date_fin = models.DateField()
    saison_key = models.CharField(max_length=8)
    formule = models.CharField(max_length=4)

    # Estimate context (nullable when not coming from a fresh estimate)
    estimated_total = models.IntegerField(null=True, blank=True)
    promos_applied = models.JSONField(default=list)                       # ["qf_r1", "premiere_minute"]

    # Recommendation context (nullable when source != 'recommendation')
    reco_strategy = models.CharField(max_length=32, blank=True, default="")
    reco_score = models.FloatField(null=True, blank=True)
    reco_rank = models.SmallIntegerField(null=True, blank=True)

    # Privacy-safe trace
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=256, blank=True, default="")

    clicked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_repeat = models.BooleanField(default=False)                        # subsequent clicks on same token

    class Meta:
        indexes = [
            models.Index(fields=["session_id", "clicked_at"]),
            models.Index(fields=["village", "source"]),
            models.Index(fields=["clicked_at"]),
        ]
```

## `apps/recommender/models.py` (Phase 2)

> Spec §4.2.

### `VillageInteraction`

```python
class VillageInteraction(models.Model):
    """
    Lightweight signals from the frontend: view, simulate, bookmark, rate, click_cta.
    Drives popularity ranking and is the implicit-ratings source for SVD.

    High-volume table. Consider partitioning / TTL once we exceed 10M rows.
    """
    KIND_CHOICES = [
        ("view", "View"),
        ("simulate", "Simulate"),
        ("bookmark", "Bookmark"),
        ("rate", "Rate (1–5)"),
        ("click_cta", "Click CTA"),
    ]
    id = models.BigAutoField(primary_key=True)
    session_id = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    village = models.ForeignKey("catalog.Village", on_delete=models.CASCADE)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    value = models.FloatField(default=1.0)                                # 1.0 implicit; 1–5 for `rate`
    metadata = models.JSONField(null=True, blank=True)                    # family snapshot, estimate, etc.
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["session_id", "kind"]),
            models.Index(fields=["village", "kind", "created_at"]),
            models.Index(fields=["created_at"]),
        ]
```

### `RecoWeights` (singleton, admin-tunable without redeploy)

```python
class RecoWeights(models.Model):
    """
    Tunable scoring weights for the content-based recommender.
    Singleton via the same is_active pattern as PricingRules.
    Spec §4.2.
    """
    id = models.AutoField(primary_key=True)
    payload = models.JSONField()
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"], condition=models.Q(is_active=True),
                name="unique_active_reco_weights",
            ),
        ]

    @classmethod
    def active(cls) -> dict:
        return cls.objects.filter(is_active=True).values_list("payload", flat=True).first() or {
            "budget_fit": 0.30,
            "env_match": 0.25,
            "family_fit": 0.20,
            "season_availability": 0.15,
            "extras_match": 0.10,
            "popularity_boost": 0.05,
            "interaction_boost": 0.05,
        }
```

### `VillagePopularityCache`

```python
class VillagePopularityCache(models.Model):
    """
    Pre-computed popularity score per village.
    Refreshed by `python manage.py refresh_popularity` (cron every 6 h).
    Used as Tier 4 fallback in the recommender waterfall.
    Spec §4.2.
    """
    village = models.OneToOneField("catalog.Village", on_delete=models.CASCADE, primary_key=True)
    views_30d = models.IntegerField(default=0)
    simulations_30d = models.IntegerField(default=0)
    bookmarks_30d = models.IntegerField(default=0)
    score = models.FloatField(default=0.0)                                # composite popularity
    updated_at = models.DateTimeField(auto_now=True)
```

## `apps/scraper/models.py` (Phase 3)

> Spec §5.2.

### `ScrapingJob`

```python
class ScrapingJob(models.Model):
    """
    One scraping run targeting a village or a region.
    Created by POST /api/v1/admin/scraper/activities (async).
    """
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    id = models.CharField(max_length=64, primary_key=True)         # 'scrape-{target}-{ts}'
    target_type = models.CharField(max_length=16)                  # 'village' | 'region'
    target_id = models.CharField(max_length=64)                    # village_id or region key
    sources = models.JSONField()                                   # ['tripadvisor', 'google_places', 'ot_local']
    radius_km = models.SmallIntegerField(default=30)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="queued")
    result_summary = models.JSONField(null=True, blank=True)
    triggered_by = models.CharField(max_length=128)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### `ScrapingCandidate`

```python
class ScrapingCandidate(models.Model):
    """
    Pre-validation staging row. Activities discovered by scraping land here;
    a human reviews and either imports them or rejects.
    Spec §5.2 / US-5.5.
    """
    STATUS_CHOICES = [
        ("new", "New"),
        ("imported", "Imported"),
        ("rejected", "Rejected"),
        ("deferred", "Deferred"),
    ]
    id = models.CharField(max_length=64, primary_key=True)         # 'cand-{uuid}'
    job = models.ForeignKey(ScrapingJob, on_delete=models.CASCADE, related_name="candidates")
    village = models.ForeignKey("catalog.Village", on_delete=models.SET_NULL, null=True, blank=True)
    region = models.CharField(max_length=64)
    source = models.CharField(max_length=32)                       # 'tripadvisor' | 'google_places' | 'ot_local'
    source_url = models.URLField(max_length=512)
    source_id = models.CharField(max_length=128)                   # external ID for dedup
    nom = models.CharField(max_length=128)
    type_emoji = models.CharField(max_length=8)
    price_adult = models.SmallIntegerField(null=True, blank=True)
    price_child = models.SmallIntegerField(null=True, blank=True)
    distance_km = models.FloatField()
    rating = models.FloatField(null=True, blank=True)
    review_count = models.IntegerField(default=0)
    saisons = models.JSONField(default=list)                       # ['hs', 'vs', 'ete', 'fetes']
    matched_activity_code = models.CharField(max_length=64, blank=True, default="")
    match_confidence = models.FloatField(default=0.0)              # 0–1
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="new")
    reviewed_by = models.CharField(max_length=128, blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    edits = models.JSONField(null=True, blank=True)                # staff edits before import

    class Meta:
        indexes = [
            models.Index(fields=["status", "region"]),
            models.Index(fields=["job", "status"]),
        ]
```

### `PriceChangeAlert`

```python
class PriceChangeAlert(models.Model):
    """
    Raised when re-scraping detects > 10 % delta on price_adult or price_child
    of an existing Activity. Spec §US-5.7.
    """
    STATUS_CHOICES = [
        ("pending", "Pending review"),
        ("approved", "Approved"),
        ("dismissed", "Dismissed"),
    ]
    id = models.AutoField(primary_key=True)
    activity = models.ForeignKey("catalog.Activity", on_delete=models.CASCADE)
    field = models.CharField(max_length=16)                        # 'price_adult' | 'price_child'
    old_value = models.SmallIntegerField()
    new_value = models.SmallIntegerField()
    source = models.CharField(max_length=32)
    scraped_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
```

### `ScrapingImportLog` (auditing imports)

```python
class ScrapingImportLog(models.Model):
    """Audit trail of what was imported / rejected / deferred and by whom."""
    id = models.BigAutoField(primary_key=True)
    job = models.ForeignKey(ScrapingJob, on_delete=models.CASCADE)
    candidate = models.ForeignKey(ScrapingCandidate, on_delete=models.CASCADE)
    action = models.CharField(max_length=16)                       # 'import' | 'reject' | 'defer'
    activity = models.ForeignKey("catalog.Activity", on_delete=models.SET_NULL, null=True, blank=True)
    edits = models.JSONField(null=True, blank=True)
    actor = models.CharField(max_length=128)
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
```

## `apps/cache_orchestrator/models.py` (Phase 3)

> Spec §5.1.

### `CacheRebuildLog`

```python
class CacheRebuildLog(models.Model):
    """
    Audit log of every cache rebuild — manual, signal-driven, or cron.
    Surfaced via GET /api/v1/health and the admin dashboard.
    """
    SCOPE_CHOICES = [
        ("all", "Everything"),
        ("catalog", "Villages, regions, activities, animations, meals, fuels"),
        ("pricing", "Pricing rules, season calendar, promo catalog"),
        ("recommendations", "Popularity cache, CF model"),
        ("booking_urls", "Pre-built VTF target URLs"),
        # Granular scopes use a colon: 'villages:biarritz' / 'regions:Aquitaine / Landes'
    ]
    id = models.AutoField(primary_key=True)
    scope = models.CharField(max_length=64)                        # see SCOPE_CHOICES + granular
    keys_invalidated = models.IntegerField(default=0)
    keys_rebuilt = models.IntegerField(default=0)
    duration_ms = models.IntegerField(default=0)
    triggered_by = models.CharField(max_length=128)                # 'admin@…' | 'system:signal' | 'system:cron'
    reason = models.TextField(blank=True, default="")              # human-readable
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
```

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
