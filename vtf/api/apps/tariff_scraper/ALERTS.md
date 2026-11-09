# Tariff Scraper — Discord Alerts

How scrape alerts work in `apps/tariff_scraper`, and what the client sees in Discord.

---

## Overview

After every village scrape (Celery task `task_scrape_village_tariffs`), the app sends a **Discord embed** so the team knows:

1. Whether the village succeeded or failed  
2. **Which pipeline step** failed  
3. **Which file / function** produced the error  
4. **Why** it failed  

Channel: Discord only (`DISCORD_WEBHOOK`).  
No email / Slack / frontend toast for tariff scrape alerts.

**Dual-season villages:** for the 12 villages scraped from both a
`/summer/` and a `/winter/` URL, step error messages may carry a
`[summer]` / `[winter]` prefix so it's clear which page produced the
error. The village still gets one alert overall — it only fails when
**neither** season produced usable priced bands.

---

## Colour scheme

| Colour | Hex | When |
|--------|-----|------|
| 🟢 **Green** | `#57F287` | Village scraped successfully (priced bands + approval staged) |
| 🟡 **Yellow** | `#FEE75C` | Partial / parse issues, **or** success with step warnings (fallback recovered) |
| 🔴 **Red** | `#ED4245` | Hard failure: HTTP blocked, layout/zero prices, crash |

Batch summary:

- All OK → 🟢 Green  
- Some failed (&lt; 50%) → 🟡 Yellow  
- Majority failed **or** any format change → 🔴 Red  

---

## Pipeline steps (error origin)

Errors are tagged as:

```text
Step N (Label) | file.py → function() | reason detail
```

| Step | Label | Source |
|------|--------|--------|
| 1 | HTTP Fetch | `scraper.py → scrape_price_grid_http()` |
| 2 | HTML Grid Parse | `scraper.py → scrape_price_grid_http()` |
| 3 | Browser Launch | `scraper.py → scrape_village()` |
| 4 | Playwright Grid Parse | `scraper.py → scrape_price_grid()` |
| 5 | Widget Scrape | `scraper.py → scrape_booking_widget()` |
| 6 | LLM Fallback | `llm_fallback.py → parse_grille_with_llm()` |
| 7 | Validation | `scraper.py → scrape_village()` |
| 8 | Tariff Builder | `tarif_builder.py → build_tarifs_from_scrape()` |
| 0 | Task Crash | `tasks.py → task_scrape_village_tariffs()` |

---

## When alerts fire

Flow in `tasks.py` after `scrape_village` + `build_tarifs_from_scrape`:

```text
ok = priced_bands > 0
     AND bands_proposed > 0
     AND approval_id is set
     AND no build_errors
```

| Outcome | Alert(s) |
|---------|----------|
| `ok=False` + format change | `notify_format_change` + `notify_scrape_failure` + DB `FormatChangeLog` |
| `ok=False` (hard failure) | `notify_scrape_failure` |
| `ok=True` + format change | `notify_format_change` + log |
| `ok=True` (clean or with warnings) | `notify_scrape_success` → 🟢 or 🟡 |
| Unhandled exception | 🔴 crash alert + `FormatChangeLog` (`hard_failure`) |
| All villages finished (chord) | `notify_batch_summary` |

Success alerts are **ON by default** (`TARIFF_SCRAPER_NOTIFY_SUCCESS=true`).

---

## Code map

| Piece | Location |
|-------|----------|
| Discord post + colour classify + step formatting | `services/alerts.py` |
| Alert dispatch after scrape | `tasks.py` → `task_scrape_village_tariffs` |
| Batch chord callback | `tasks.py` → `task_batch_summary_callback` |
| Step-tagged scrape errors | `services/scraper.py` (Steps 1–7) |
| Step-tagged builder errors | `services/tarif_builder.py` (Step 8) |
| Dry-run fake alerts API | `views.py` → `DryRunAlertView` |
| Settings | `DISCORD_WEBHOOK`, `TARIFF_SCRAPER_NOTIFY_SUCCESS` |

If `DISCORD_WEBHOOK` is empty, alerts are skipped silently (no crash).

---

## Env (optional)

```env
# Required to actually post to Discord
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...

# Green/yellow success pings (default: true)
TARIFF_SCRAPER_NOTIFY_SUCCESS=true
```

Dry-run without a real scrape:

`POST /api/v4/tariff-scraper/dry-run-alert/`  
Scenarios: `success`, `hard_failure`, `zero_prices`, `parse_failure`, `marker_missing`, `partial`, `batch_summary`.

---

## Sample Discord output (what the client sees)

These are the embed contents built by the alert code (same text Discord would show).

### 1) 🟢 Green — village scraped OK

```text
Colour: GREEN (#57F287)
Title: ✅ Scrape OK — lacanau

Village: lacanau
URL: https://www.vtf-vacances.com/fr_FR/summer/village-vacances/lacanau/
Priced bands: 12
Bands proposed: 10
Approval ID: 142
Bands scraped: 12

Result:
Village scraped successfully. Priced bands staged for approval.
```

### 2) 🟡 Yellow — OK, but a step warned (fallback recovered)

```text
Colour: YELLOW (#FEE75C)
Title: 🟡 Scrape OK (with warnings) — bandol

Village: bandol
Priced bands: 12 | Bands proposed: 10 | Approval ID: 142

Result:
Village scraped successfully (priced bands + approval staged),
but some earlier pipeline steps reported errors.
Fallback path recovered the data.

Step warnings (recovered):
**Step 1 (HTTP Fetch)**
📍 `scraper.py → scrape_price_grid_http()`
❌ HTTP 403 Forbidden — Cloudflare blocked the request
```

### 3) 🔴 Red — hard HTTP failure

```text
Colour: RED (#ED4245)
Title: 🚨 Scrape FAILED — agde

Reason (step + code):
Step 1 (HTTP Fetch)
Code: `scraper.py → scrape_price_grid_http()`
Reason: HTTP 404 Client Error: Not Found

Errors by Step (where it failed):
**Step 1 (HTTP Fetch)**
📍 `scraper.py → scrape_price_grid_http()`
❌ HTTP 404 Client Error: Not Found
```

### 4) 🔴 Red — layout / zero prices (full step trail)

```text
Colour: RED (#ED4245)
Title: 🔴 Zero prices extracted — alpe-dhuez

Reason (step + code):
Step 7 (Validation)
Code: `scraper.py → scrape_village()`
Reason: No priced tariff bands extracted from any source
        (grille, widget, or LLM). Total bands scraped: 0.
        Nothing will be written to VillageTarif.

Errors by Step (where it failed):
**Step 2 (HTML Grid Parse)**
📍 `scraper.py → scrape_price_grid_http()`
❌ Page loaded (html_len=48000) but no price grid markers found
   (grille tarifaire, pension complète, etc.).
   The VTF page layout may have changed.

**Step 4 (Playwright Grid Parse)**
📍 `scraper.py → scrape_price_grid()`
❌ Page rendered but no price table found in DOM.

**Step 5 (Widget Scrape)**
📍 `scraper.py → scrape_booking_widget()`
❌ Booking widget not found on page.

**Step 7 (Validation)**
📍 `scraper.py → scrape_village()`
❌ No priced tariff bands extracted from any source
   (grille, widget, or LLM). Total bands scraped: 0.
   Nothing will be written to VillageTarif.
```

This is the client-facing format: **which step → which file/function → why**.

### 5) 🟡 Yellow — partial scrape

```text
Colour: YELLOW (#FEE75C)
Title: 🟡 Partial scrape — metabief

Reason (step + code):
Step 8 (Tariff Builder)
Code: `tarif_builder.py → build_tarifs_from_scrape()`
Reason: Skipped 7 bands: no parseable dates

Errors by Step:
**Step 8 (Tariff Builder)**
📍 `tarif_builder.py → build_tarifs_from_scrape()`
❌ Skipped 7 bands: no parseable dates
```

### 6) Batch summary (after all villages)

```text
Title: ⚠️ Batch scrape — 3/32 villages FAILED
Total: 32 | OK: 29 | Failed: 3

Failed villages (step + reason):
**agde** — Step 1 (HTTP Fetch): HTTP 404 Client Error: Not Found
**alpe-dhuez** — Step 7 (Validation): No priced tariff bands extracted...
**metabief** — Step 8 (Tariff Builder): Skipped 7 bands: no parseable dates
```

When all villages succeed:

```text
Colour: GREEN (#57F287)
Title: ✅ Batch scrape complete — 32/32 OK
Total villages: 32 | OK: 32 | Failed: 0
```

---

## Failure classification (short)

| Situation | Colour | Typical title |
|-----------|--------|----------------|
| Step 1 only, 0 bands | 🔴 | Scrape FAILED |
| Page ran, 0 prices | 🔴 | Zero prices extracted |
| Unhandled exception | 🔴 | Scrape CRASHED |
| Bands scraped, none proposed | 🟡 | Bands scraped but none proposed |
| Some data + errors | 🟡 | Partial scrape |
| Clean success | 🟢 | Scrape OK |
| Success + non-fatal step errors | 🟡 | Scrape OK (with warnings) |

Reason text always prefers the **primary** failing step (usually Step 7 or Step 8), plus `Code:` and `Reason:`.

---

## Related

- Format-change audit: model `FormatChangeLog`, API `GET /api/v4/tariff-scraper/format-changes/`
- Hybrid scrape path (HTTP → Playwright → LLM): see [`LLM_FALLBACK.md`](LLM_FALLBACK.md)
