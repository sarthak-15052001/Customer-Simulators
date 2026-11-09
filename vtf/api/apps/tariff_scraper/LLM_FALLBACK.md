# Tariff Scraper — LLM Fallback

Client-facing guide: how the **AI / LLM fallback** works inside `apps/tariff_scraper`.

**In one sentence:** the normal scraper stays primary; if it cannot extract any priced tariffs, a small **local** AI (via LM Studio) reads the VTF grille HTML as a last resort — producing the **same fields** as the scraper, never inventing age groups, supplements, or commercial discounts.

---

## Dual-season villages (summer + winter URL)

For 12 villages with confirmed live winter product pages (`karellis`,
`montricher-albanne`, `la-plagne`, `le-sauze`, `arvieux`, `savines`,
`saint-sauves`, `metabief`, `soultzeren`, `font-durle`, `areches`,
`chamonix` — see `DUAL_SEASON_VILLAGE_IDS` in `village_urls.py`), a scrape
job runs the whole flow below **twice per village**: once against the
`/summer/` URL, once against the `/winter/` URL. Each run goes through
Tier 1 → Tier 4 (including LLM fallback) completely independently — a
summer success never skips or short-circuits the winter run. The two
seasons' bands are merged before `build_tarifs_from_scrape`, so one village
still ends up with **one** pending `TariffApproval`; each proposed band and
`PriceSnapshot` row carries a `scrape_source` of `summer` or `winter` (the
URL path scraped — not a grille season like `ete`/`hs`/`vs`/`fetes`) so
reviewers can tell which page a price came from. Every other village keeps
today's single-URL, single-pass behaviour unchanged.

## Why this exists

VTF village pages sometimes change layout (markers missing, messy HTML, colspan quirks). When all deterministic grille tiers return **zero priced bands**, the business still needs a chance to recover tariffs without waiting for a code change.

LLM fallback is that **safety net** — not a replacement for scraping.

| Principle | Meaning |
|-----------|---------|
| Scraping first | Healthy villages never call the AI |
| Same fields only | PC adult, DP derived from PC, LOC unit prices, dates — identical to the scraper |
| Local model only | `luth-lfm2-350m` via LM Studio on `localhost` — no cloud GPU required |
| Staff approval | LLM bands still go through `TariffApproval` like any other scrape |
| Safe failures | LLM errors are logged; they cannot break a successful scrape |

---

## High-level flow (for the client)

Pen-style flow (read top → bottom):

```text
  +------------------------------+
  | START: scrape one village    |
  +---------------+--------------+
                  |
                  v
  +------------------------------+
  | Tier 1: HTTP grille parse    |
  +---------------+--------------+
                  |
        +---------+---------+
        |                   |
        v                   v
  +------------+     +----------------------+
  | Prices OK  |     | Zero priced bands    |
  | PC adult,  |     +----------+-----------+
  | derived DP,|                |
  | or LOC     |                v
  +-----+------+     +----------------------+
        |            | Tier 2: Playwright   |
        |            | grille parse         |
        |            +----------+-----------+
        |                       |
        |             +---------+---------+
        |             |                   |
        |             v                   v
        |       +------------+     +----------------------+
        |       | Prices OK  |     | Zero priced bands    |
        |       +-----+------+     +----------+-----------+
        |             |                       |
        |             |                       v
        |             |            +----------------------+
        |             |            | Tier 3: Booking      |
        |             |            | widget only if no    |
        |             |            | grille prices exist  |
        |             |            +----------+-----------+
        |             |                       |
        |             |             +---------+---------+
        |             |             |                   |
        |             |             v                   v
        |             |       +------------+     +----------------------+
        |             |       | Prices OK  |     | Zero priced bands    |
        |             |       +-----+------+     +----------+-----------+
        |             |             |                       |
        |             |             |                       v
        |             |             |            +----------------------+
        |             |             |            | LLM fallback enabled?|
        |             |             |            +----------+-----------+
        |             |             |                       |
        |             |             |             +---------+---------+
        |             |             |             |                   |
        |             |             |             v                   v
        |             |             |       +------------+     +----------------------+
        |             |             |       | NO: fail   |     | YES: Step 6 LLM     |
        |             |             |       | Step 7     |     | copy prices only    |
        |             |             |       +-----+------+     +----------+-----------+
        |             |             |             |                       |
        |             |             |             |                       v
        |             |             |             |       +----------------------+
        |             |             |             |       | Map PC adult + LOC   |
        |             |             |             |       | derive DP in code    |
        |             |             |             |       +----------+-----------+
        |             |             |             |                  |
        |             |             |             |        +---------+---------+
        |             |             |             |        |                   |
        |             |             |             v        v                   v
        |             |             |       +-------------+          +------------------+
        |             |             |       | FAIL (RED)  |          | Prices OK        |
        |             |             |       +------+------+          +--------+---------+
        |             |             |              |                          |
        v             v             v              v                          v
  +----------------------------------------------------------------+   +----------------+
  | SUCCESS: build snapshots + pending TariffApproval               |   | FAIL: Step 7   |
  | Staff approve before live prices                                |   | Discord RED    |
  +----------------------------------------------------------------+   +----------------+
```

**Legend**

- **GREEN path** → priced bands found → approval  
- **YELLOW path** → AI recovery (Step 6), if enabled  
- **RED path** → nothing extracted  

---

## When the LLM runs (and when it does not)

```text
  +========================================+     +========================================+
  |     LLM is NEVER called when...        |     |     LLM runs ONLY when ALL of...       |
  +========================================+     +========================================+
  |                                        |     |                                        |
  |  (1) HTTP grille already returned      |     |  (1) HTTP grille gave ZERO priced      |
  |      any priced PC adult / derived     |     |      bands                             |
  |      DP / LOC bands                    |     |                                        |
  |                                        |     |                                        |
  |  (2) Playwright grille recovered       |     |  (2) AND Playwright grille gave ZERO   |
  |      priced bands                      |     |      priced bands                      |
  |                                        |     |                                        |
  |  (3) Booking widget recovered          |     |  (3) AND booking widget gave ZERO      |
  |      priced bands                      |     |      priced bands                      |
  |  (4) LLM_FALLBACK_ENABLED = false      |     |  (4) AND LLM_FALLBACK_ENABLED = true   |
  |                                        |     |                                        |
  |                                        |     |  (5) AND village page HTML is          |
  |                                        |     |      available                         |
  |                                        |     |                                        |
  +========================================+     +========================================+
```

Triggered from:

```text
  scraper.py  →  scrape_village()  →  Step 6 (LLM Fallback)
       |
       v
  llm_fallback.py  →  parse_grille_with_llm()
```

---

## Inside the LLM fallback (detail)

Once Step 6 starts:

```text
  Village page HTML
         |
         +---------------------------+
         |                           |
         v                           v
  +------------------+      +------------------+
  | 1. Python chunker|      | 2. Footnotes     |
  | chunk_grille_html|      | extract_footnotes|
  +--------+---------+      +--------+---------+
           |                         |
           v                         v
  +------------------+      +------------------+
  | Row payloads:    |      | ½-pension remise |
  | dates + cleaned  |      | % only           |
  | price cells      |      | (no supplements) |
  +--------+---------+      +--------+---------+
           |                         |
           v                         |
  +------------------+               |
  | 3. Per row:      |               |
  | extract_row_prices               |
  | (LM Studio)      |               |
  +--------+---------+               |
           |                         |
           v                         |
  +------------------+               |
  | Prices match the |               |
  | cell text?       |               |
  +--------+---------+               |
           |                         |
     +-----+-----+                   |
     |           |                   |
    YES         NO / LLM down        |
     |           |                   |
     |           v                   |
     |    +------------------+       |
     |    | Retry (max       |       |
     |    | LLM_MAX_RETRIES) |       |
     |    +--------+---------+       |
     |             |                 |
     |      still bad?               |
     |             |                 |
     |             v                 |
     |    +------------------+       |
     |    | Regex fallback   |       |
     |    | on same cells    |       |
     |    +--------+---------+       |
     |             |                 |
     +------+------+                 |
            |                        |
            v                        |
  +------------------------------------------+
  | 4. Map to RawPriceBand                   |
  |    llm_bands_to_raw_price_bands          |
  |    PC + LOC + DP derived from PC (code)  |
  +--------------------+---------------------+
                       |   (uses remise -----+)
                       v
  +------------------------------------------+
  | Output bands                             |
  | source_page = "llm_fallback"              |
  +--------------------+---------------------+
                       |
                       v
  +------------------------------------------+
  | Same as normal scrape:                   |
  | tarif_builder → pending TariffApproval   |
  +------------------------------------------+
```

### Step-by-step (what each piece does)

| # | Name | Who does the work | What happens |
|---|------|-------------------|--------------|
| 1 | **Chunker** | Python (`chunk_grille_html`) | Finds grille tables, expands colspan on price cells, converts `Gratuit` → `0`, strips €, parses **dates in Python** (LLM must not invent dates) |
| 2 | **Footnotes** | Python (`extract_footnotes`) | Reads **demi-pension remise** only (e.g. 15%). Never supplements or commercial discounts |
| 3 | **Price copy** | Local LLM + checks | LLM’s only job: copy adult (PC) or unit (LOC) numbers from pre-cleaned cells. Response is validated against the cell text (anti-hallucination). On failure → retry → **regex fallback** |
| 4 | **Map bands** | Python (`llm_bands_to_raw_price_bands`) | Builds `RawPriceBand` with `source_page="llm_fallback"`. **DP is derived from PC in code** (remise math), not asked from the LLM |

---

## What the AI is allowed to do vs not

```text
  +====================================+     +====================================+
  |           ALLOWED                  |     |        NEVER ALLOWED               |
  +====================================+     +====================================+
  |                                    |     |                                    |
  |  * Copy adult weekly PC price      |     |  * Age-group / child prices        |
  |  * Copy LOC unit column prices     |     |  * Supplements or promo discounts  |
  |  * Return JSON number arrays       |     |  * Invent dates or seasons         |
  |                                    |     |  * Write live prices without       |
  |                                    |     |    staff approval                  |
  |                                    |     |  * Call cloud APIs / GPU farms     |
  |                                    |     |                                    |
  +====================================+     +====================================+
```

### Field mapping (1:1 with the scraper)

| Output field | Comes from |
|--------------|------------|
| **PC** (adult weekly) | `Adultes` column; age columns ignored |
| **DP** | Derived from PC via ½-pension remise (code math) |
| **LOC** | One band per unit column |
| **date_start / date_end** | Python chunker (`parse_vtf_period_cell`) |
| **nb_adults** | `1` on grille PC/DP (same as scraper) |
| **source_page** | Always `llm_fallback` (so staff can see origin) |

---

## Example walkthrough (client story)

**Village:** `lacanau`  
**Situation:** VTF changed the grille HTML; HTTP grille, Playwright grille, and booking widget all find no prices.

```text
  Tier 1 HTTP grille  --->  0 priced bands
       |
       v
  Tier 2 Playwright grille  --->  0 priced bands
       |
       v
  Tier 3 booking widget  --->  0 priced bands
       |
       v
  LLM_FALLBACK_ENABLED=true  --->  Step 6 starts
       |
       v
  Python chunks rows (real dates + cleaned cells e.g. 637)
       |
       v
  LM Studio (luth-lfm2-350m): "copy adult price → [637]"
       |
       v
  Code checks 637 exists in the cell (reject invented numbers)
       |
       v
  Build PC adult + derived DP + LOC units  (source_page = llm_fallback)
       |
       v
  tarif_builder → pending TariffApproval  →  staff approve
       |
       v
  Discord: GREEN success, or fallback-recovery warning if configured
```

If LM Studio is down or returns junk, regex tries the same cells; if still empty → Step 7 validation fails → RED alert (see [`ALERTS.md`](ALERTS.md)).

---

## Configuration

Set in `.env` (see also `.env.example`):

```env
# Master switch — default false in settings; enable for fallback
LLM_FALLBACK_ENABLED=true

# Local LM Studio OpenAI-compatible API
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODEL=luth-lfm2-350m

# Retries before regex fallback per row
LLM_MAX_RETRIES=2
```

| Variable | Default | Role |
|----------|---------|------|
| `LLM_FALLBACK_ENABLED` | `false` | Must be `true` for Step 6 to run |
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` | Local only |
| `LMSTUDIO_MODEL` | `luth-lfm2-350m` | Small ~350M model |
| `LLM_MAX_RETRIES` | `2` | LLM attempts before regex |

**Prerequisite:** LM Studio running locally with the model loaded. No cloud key is required for this path.

---

## Code map

| Piece | File / symbol |
|-------|----------------|
| Trigger (only if all scrape tiers return zero priced bands) | `services/scraper.py` → `scrape_village()` Step 6 |
| Entry point | `services/llm_fallback.py` → `parse_grille_with_llm()` |
| Chunker | `chunk_grille_html()` |
| Remise footnotes | `extract_footnotes()` |
| LLM + retry + regex | `extract_row_prices()` / `_call_lmstudio()` |
| Map to bands | `llm_bands_to_raw_price_bands()` |
| Approval staging | `services/tarif_builder.py` → `build_tarifs_from_scrape()` |
| Source constant | models: `SOURCE_LLM = "llm_fallback"` |
| Tests | `test_llm_fallback.py` (mocked LM Studio; success path must not call LLM) |

---

## Safety checklist (locked for the client)

1. Scraping stays primary and must keep working.  
2. AI runs **only** when HTTP grille, Playwright grille, and booking widget all yield zero priced bands (and the switch is on).  
3. Same output fields as the scraper — never age tiers / supplements / discounts.  
4. Dates and DP math stay in **Python**, not the model.  
5. Prices are checked against HTML cells before acceptance.  
6. Nothing goes live without **TariffApproval**.  
7. LLM exceptions are caught in `scrape_village`; they do not crash a good scrape.  
8. No requirement for cloud APIs or dedicated GPU for this MVP path.

---

## Related docs

- Discord alerts (green / yellow / red + step trail): [`ALERTS.md`](ALERTS.md)  
- Implementation module: `services/llm_fallback.py`  
