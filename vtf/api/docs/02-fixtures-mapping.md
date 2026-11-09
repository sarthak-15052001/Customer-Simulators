# 02 — Fixtures & VTF URL mapping

> **Why this matters:** when a user clicks "book" on the simulator, we redirect them to
> the canonical VTF page. We need a stable mapping from our `village_id` to the VTF URL.

## URL template

```
https://www.vtf-vacances.com/fr_FR/{season}/village-vacances/{department}/{city}/{slug}
```

| Token        | Source                                | Example         |
|--------------|---------------------------------------|-----------------|
| `season`     | computed from `dateDebut`             | `ete-2026`      |
| `department` | static, `Village.vtf_department`      | `gironde`       |
| `city`       | static, `Village.vtf_city`            | `lacanau`       |
| `slug`       | static, `Village.vtf_slug`            | `la-forestiere` |

## Status legend

- ✅ **Verified** — URL hits a 200 on the live VTF site.
- 🔍 **Inferred** — slug derived from VTF naming conventions; **must be verified** before
  Phase 1 deploy via `python manage.py verify_vtf_urls`.

## Mapping (32 villages, grouped by region)

### Bretagne / Normandie

| `id`         | VTF Name           | `vtf_department` | `vtf_city`            | `vtf_slug`         | Status |
|--------------|--------------------|------------------|-----------------------|--------------------|--------|
| `saint-cast` | Hôtel des Bains*** | cotes-d-armor    | saint-cast-le-guildo  | hotel-des-bains    | 🔍     |
| `blainville` | Les Tourelles***   | manche           | blainville-sur-mer    | les-tourelles      | 🔍     |
| `riec`       | Ker Belen***       | finistere        | riec-sur-belon        | ker-belen          | 🔍     |

### Aquitaine / Landes

| `id`          | VTF Name              | `vtf_department`     | `vtf_city`    | `vtf_slug`             | Status |
|---------------|-----------------------|----------------------|---------------|------------------------|--------|
| `biarritz`    | Domaine de Françon*** | pyrenees-atlantiques | biarritz      | le-domaine-de-francon  | ✅     |
| `lacanau`     | La Forestière**       | gironde              | lacanau       | la-forestiere          | 🔍     |
| `carcans`     | Les Bruyères**        | gironde              | carcans       | les-bruyeres           | 🔍     |
| `biscarrosse` | La Jaougue Soule***   | landes               | biscarrosse   | la-jaougue-soule       | 🔍     |

### Méditerranée / PACA

| `id`            | VTF Name              | `vtf_department` | `vtf_city`     | `vtf_slug`            | Status |
|-----------------|-----------------------|------------------|----------------|-----------------------|--------|
| `bandol`        | Le Mas de Taoumé***   | var              | bandol         | le-mas-de-taoume      | 🔍     |
| `sainte-maxime` | Golfe de Saint-Tropez | var              | sainte-maxime  | golfe-de-saint-tropez | 🔍     |
| `saint-aygulf`  | Les Lauriers Roses*** | var              | frejus         | les-lauriers-roses    | 🔍     |
| `agde`          | Le Domaine d'Agde***  | herault          | agde           | le-domaine-d-agde     | ✅     |

### Alpes / Savoie

| `id`          | VTF Name             | `vtf_department` | `vtf_city`           | `vtf_slug`           | Status |
|---------------|----------------------|------------------|----------------------|----------------------|--------|
| `chamonix`    | Les Econtres***      | haute-savoie     | chamonix             | les-econtres         | 🔍     |
| `alpe-dhuez`  | Le Balcon de l'Alpe  | isere            | alpe-d-huez          | le-balcon-de-l-alpe  | 🔍     |
| `doucy`       | Le Valmorel***       | savoie           | doucy-valmorel       | le-valmorel          | 🔍     |
| `karellis`    | Les Karellis***      | savoie           | les-karellis         | les-karellis         | 🔍     |
| `la-plagne`   | Dou de la Ramaz***   | savoie           | la-plagne-montalbert | dou-de-la-ramaz      | 🔍     |
| `montgenevre` | Le Grand Hôtel***    | hautes-alpes     | montgenevre          | le-grand-hotel       | 🔍     |

### Alpes du Sud

| `id`        | VTF Name              | `vtf_department`        | `vtf_city`     | `vtf_slug`           | Status |
|-------------|-----------------------|-------------------------|----------------|----------------------|--------|
| `le-sauze`  | Les Balcons du Sauze  | alpes-de-haute-provence | le-sauze       | les-balcons-du-sauze | 🔍     |
| `praloup`   | L'Ouka***             | alpes-de-haute-provence | uvernet-fours  | l-ouka               | 🔍     |
| `arvieux`   | L'Izoard***           | hautes-alpes            | arvieux        | l-izoard             | 🔍     |
| `savines`   | Le Pigneroux**        | hautes-alpes            | savines-le-lac | le-pigneroux         | 🔍     |

### Massif Central / Jura / Vosges

| `id`           | VTF Name           | `vtf_department` | `vtf_city`              | `vtf_slug`        | Status |
|----------------|--------------------|------------------|-------------------------|-------------------|--------|
| `saint-sauves` | Domaine des Puys   | puy-de-dome      | saint-sauves-d-auvergne | domaine-des-puys  | 🔍     |
| `metabief`     | Le Bief Rouge**    | doubs            | metabief                | le-bief-rouge     | 🔍     |
| `soultzeren`   | Les Fougères***    | haut-rhin        | soultzeren              | les-fougeres      | 🔍     |
| `font-durle`   | Font d'Urle***     | drome            | bouvante                | font-urle         | ✅     |

### Campagne / Provence / Ardèche

| `id`         | VTF Name                  | `vtf_department`        | `vtf_city`  | `vtf_slug`                | Status |
|--------------|---------------------------|-------------------------|-------------|---------------------------|--------|
| `bedoin`     | Le Mont Serein***         | vaucluse                | bedoin      | le-mont-serein            | 🔍     |
| `cereste`    | Domaine du Grand Luberon  | alpes-de-haute-provence | cereste     | domaine-du-grand-luberon  | 🔍     |
| `singleyrac` | Domaine du Peyrichoux***  | dordogne                | singleyrac  | domaine-du-peyrichoux     | 🔍     |
| `joyeuse`    | Les Sources***            | ardeche                 | joyeuse     | les-sources               | 🔍     |

> **Coverage gap:** the table above lists ~28 villages. The frontend mock has 32 entries
> (`areches`, `vernet`, `talloires`, `montricher-albanne` are present but the VTF URL was
> not provided in the addendum). When implementing, generate slugs from `nom` and verify.

## JSON fixture (`apps/catalog/fixtures/vtf_url_mapping.json`)

```json
{
  "vtf_url_mapping": {
    "saint-cast":     { "slug": "hotel-des-bains",          "dept": "cotes-d-armor",          "city": "saint-cast-le-guildo" },
    "blainville":     { "slug": "les-tourelles",            "dept": "manche",                 "city": "blainville-sur-mer" },
    "riec":           { "slug": "ker-belen",                "dept": "finistere",              "city": "riec-sur-belon" },
    "biarritz":       { "slug": "le-domaine-de-francon",    "dept": "pyrenees-atlantiques",   "city": "biarritz" },
    "lacanau":        { "slug": "la-forestiere",            "dept": "gironde",                "city": "lacanau" },
    "carcans":        { "slug": "les-bruyeres",             "dept": "gironde",                "city": "carcans" },
    "biscarrosse":    { "slug": "la-jaougue-soule",         "dept": "landes",                 "city": "biscarrosse" },
    "bandol":         { "slug": "le-mas-de-taoume",         "dept": "var",                    "city": "bandol" },
    "sainte-maxime":  { "slug": "golfe-de-saint-tropez",    "dept": "var",                    "city": "sainte-maxime" },
    "saint-aygulf":   { "slug": "les-lauriers-roses",       "dept": "var",                    "city": "frejus" },
    "agde":           { "slug": "le-domaine-d-agde",        "dept": "herault",                "city": "agde" },
    "chamonix":       { "slug": "les-econtres",             "dept": "haute-savoie",           "city": "chamonix" },
    "alpe-dhuez":     { "slug": "le-balcon-de-l-alpe",      "dept": "isere",                  "city": "alpe-d-huez" },
    "doucy":          { "slug": "le-valmorel",              "dept": "savoie",                 "city": "doucy-valmorel" },
    "karellis":       { "slug": "les-karellis",             "dept": "savoie",                 "city": "les-karellis" },
    "la-plagne":      { "slug": "dou-de-la-ramaz",          "dept": "savoie",                 "city": "la-plagne-montalbert" },
    "montgenevre":    { "slug": "le-grand-hotel",           "dept": "hautes-alpes",           "city": "montgenevre" },
    "le-sauze":       { "slug": "les-balcons-du-sauze",     "dept": "alpes-de-haute-provence","city": "le-sauze" },
    "praloup":        { "slug": "l-ouka",                   "dept": "alpes-de-haute-provence","city": "uvernet-fours" },
    "arvieux":        { "slug": "l-izoard",                 "dept": "hautes-alpes",           "city": "arvieux" },
    "savines":        { "slug": "le-pigneroux",             "dept": "hautes-alpes",           "city": "savines-le-lac" },
    "saint-sauves":   { "slug": "domaine-des-puys",         "dept": "puy-de-dome",            "city": "saint-sauves-d-auvergne" },
    "metabief":       { "slug": "le-bief-rouge",            "dept": "doubs",                  "city": "metabief" },
    "soultzeren":     { "slug": "les-fougeres",             "dept": "haut-rhin",              "city": "soultzeren" },
    "font-durle":     { "slug": "font-urle",                "dept": "drome",                  "city": "bouvante" },
    "bedoin":         { "slug": "le-mont-serein",           "dept": "vaucluse",               "city": "bedoin" },
    "cereste":        { "slug": "domaine-du-grand-luberon", "dept": "alpes-de-haute-provence","city": "cereste" },
    "singleyrac":     { "slug": "domaine-du-peyrichoux",    "dept": "dordogne",               "city": "singleyrac" },
    "joyeuse":        { "slug": "les-sources",              "dept": "ardeche",                "city": "joyeuse" }
  }
}
```

## Verification command

`apps/catalog/management/commands/verify_vtf_urls.py`

```python
import requests
from django.core.management.base import BaseCommand
from apps.catalog.models import Village


class Command(BaseCommand):
    help = "Hits each constructed VTF URL and reports 4xx/5xx."

    def handle(self, *args, **opts):
        ok, ko = [], []
        for v in Village.objects.all():
            url = (
                f"https://www.vtf-vacances.com/fr_FR/ete-2026/village-vacances/"
                f"{v.vtf_department}/{v.vtf_city}/{v.vtf_slug}"
            )
            try:
                r = requests.head(url, allow_redirects=True, timeout=10)
                (ok if r.status_code == 200 else ko).append((v.id, url, r.status_code))
            except Exception as e:
                ko.append((v.id, url, str(e)))

        self.stdout.write(f"OK: {len(ok)} | KO: {len(ko)}")
        for vid, url, code in ko:
            self.stderr.write(f"  ✗ {vid}: {code} — {url}")
```

Run before each deploy:
```bash
python manage.py verify_vtf_urls
```

## VTF URL builder — full spec

> Spec source: §3.4 `booking_url.py` and US-2.8.

The frontend never sees the raw VTF URL. Every "Réserver sur VTF" click goes through a
**signed-token redirect** so we can log conversion intent. See `11-booking-redirect.md`
for the token mechanics; this section just documents how the URL is built.

### URL template

```
https://www.vtf-vacances.com/fr_FR/{season}/village-vacances/{department}/{city}/{slug}
  ?search_engine[startedAt]={dateDebut}
  &search_engine[endedAt]={dateFin}
  &search_engine[nbPersons]={total}
  &search_engine[nbAdults]={adults}
  &search_engine[nbBabies]={age_0_1}
  &search_engine[nbChildren3]={age_2_5}
  &search_engine[nbChildren1]={age_6_11}
  &search_engine[nbChildren2]={age_12_17}
```

| URL segment           | Source                                            | Example (Agde)            |
|-----------------------|---------------------------------------------------|---------------------------|
| `{season}`            | `saison_to_url_segment(saison_key, dateDebut)`    | `summer` / `winter`       |
| `{department}`        | `Village.vtf_department`                          | `herault`                 |
| `{city}`              | `Village.vtf_city`                                | `agde`                    |
| `{slug}`              | `Village.vtf_slug`                                | `le-domaine-d-agde`       |

### Season segment mapping

```python
SAISON_TO_URL_SEGMENT = {
    "ete":   "summer",
    "fetes": "winter",
    "vs":    "winter",   # Feb ski = winter, Easter / Toussaint = contextual
    "hs":    "summer",   # default fallback
}


def saison_to_url_segment(saison_key: str, date_debut: str) -> str:
    """Spec §3.4. Switch to 'winter' for Jan/Feb/Mar/Oct/Nov/Dec when ambiguous."""
    month = int(date_debut[5:7])
    if saison_key in ("vs", "hs"):
        return "winter" if month in (1, 2, 3, 10, 11, 12) else "summer"
    return SAISON_TO_URL_SEGMENT.get(saison_key, "summer")
```

### Child age bucketing

VTF's site uses **4 brackets** (not age in years). The payload sends counts per bracket.

```python
def bucket_children(enfants: list[dict]) -> dict:
    """Maps each child's age to the correct search_engine param. Spec §3.4."""
    buckets = {"nbBabies": 0, "nbChildren3": 0, "nbChildren1": 0, "nbChildren2": 0}
    for child in enfants:
        age = child["age"]
        if   age <= 1:  buckets["nbBabies"]    += 1   # 0–1
        elif age <= 5:  buckets["nbChildren3"] += 1   # 2–5
        elif age <= 11: buckets["nbChildren1"] += 1   # 6–11
        else:           buckets["nbChildren2"] += 1   # 12–17
    return buckets
```

| Param key                       | Age range | Description       |
|---------------------------------|-----------|-------------------|
| `search_engine[nbBabies]`       | 0–1       | Baby              |
| `search_engine[nbChildren3]`    | 2–5       | Toddler           |
| `search_engine[nbChildren1]`    | 6–11      | Child             |
| `search_engine[nbChildren2]`    | 12–17     | Teen              |

### Override mechanism

If a village has a non-standard URL, `Village.vtf_base_url` (`URLField`, blank by
default) overrides the composed path. The builder uses `vtf_base_url` if set,
otherwise composes from `vtf_department/vtf_city/vtf_slug`.

### Builder service

```python
# apps/pricing/services/booking_url.py — see 04-services.md for full version
from urllib.parse import urlencode


def build_vtf_booking_url(*, village, family: dict, dates: dict, saison_key: str) -> str:
    base = village.vtf_base_url or (
        f"https://www.vtf-vacances.com/fr_FR/"
        f"{saison_to_url_segment(saison_key, dates['debut'])}/village-vacances/"
        f"{village.vtf_department}/{village.vtf_city}/{village.vtf_slug}"
    )
    buckets = bucket_children(family["enfants"])
    nb_persons = family["adultes"] + len(family["enfants"])
    qs = urlencode({
        "search_engine[startedAt]": dates["debut"],
        "search_engine[endedAt]":   dates["fin"],
        "search_engine[nbPersons]": nb_persons,
        "search_engine[nbAdults]":  family["adultes"],
        **{f"search_engine[{k}]": v for k, v in buckets.items()},
    })
    return f"{base}?{qs}"
```

### Token-based redirect endpoint (where this URL is consumed)

| Method | Path                                          | Returns                                                    |
|--------|-----------------------------------------------|------------------------------------------------------------|
| `POST` | `/api/v1/villages/{id}/booking-link`          | `{ token, redirectUrl, targetUrl, params, expiresAt }`     |
| `GET`  | `/api/v1/go/{token}`                          | `302 Location: <vtf_url>` + logs `BookingClick`            |

The signed token (HMAC-SHA-256, **not** JWT) carries `village_id`, `session_id`,
`created_at`, `payload_hash`. Full payload server-side in `BookingRedirectToken`. TTL
72 h (configurable). Expired/tampered tokens redirect to the village's generic VTF page —
**never a 404 or dead end**. See `11-booking-redirect.md`.

### Acceptance criteria (Phase 1)

| ID       | Criterion                                                                 |
|----------|---------------------------------------------------------------------------|
| AC-1.12  | All 32 villages have `vtf_slug`, `vtf_department`, `vtf_city` populated   |
| AC-1.13  | Booking redirect logs a `BookingClick` with `source` + reco context       |
| (US-2.8) | Token generation < 10 ms; redirect response < 50 ms (DB write is async)   |
| (US-2.8) | Repeat clicks tracked with `is_repeat=True`, don't inflate unique counts  |
| (US-2.8) | IP is hashed (sha256), no PII stored beyond `session_id`                  |
