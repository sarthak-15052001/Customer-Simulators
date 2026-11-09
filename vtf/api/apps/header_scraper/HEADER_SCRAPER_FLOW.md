# Header Scraper Flow

This document explains how the VTF homepage header banner scraper works: the Celery flow, the scraper tiers, the two database tables, and how the public/admin APIs use the scraped data.

## What This Scraper Does

The `header_scraper` app keeps the small top announcement banner from the VTF website in sync with our simulator API.

It scrapes two VTF homepages:

| Language | Source URL | Stored language |
| --- | --- | --- |
| French | `https://www.vtf-vacances.com/fr_FR/` | `FR` |
| English | `https://www.vtf-vacances.com/en_GB/` | `GB` |

The scraper extracts only the top announcement/banner content, converts the banner HTML into simple ordered segments, and publishes the latest active banner through:

```text
GET /api/v5/header-banner?lang=FR
GET /api/v5/header-banner?lang=GB
```

`ES` and `NL` simulator languages are mapped to the French banner. `EN` is mapped to `GB`.

## Main Files

| File | Purpose |
| --- | --- |
| `apps/header_scraper/tasks.py` | Celery tasks that run the scrape asynchronously |
| `apps/header_scraper/services/scrape.py` | Tiered scraping: HTTP, Playwright, LLM fallback |
| `apps/header_scraper/services/parse.py` | Converts banner HTML into API-safe segments |
| `apps/header_scraper/services/sync.py` | Saves the result, compares hashes, writes snapshots |
| `apps/header_scraper/models.py` | Defines the two database tables |
| `apps/header_scraper/views.py` | Public banner API and staff/admin scrape APIs |
| `apps/header_scraper/admin.py` | Django admin display and "scrape now" button |

## Pen-Style Flowchart

```text
  .-------------------------------------------------------------.
  |                     START HEADER SCRAPE                     |
  '-------------------------------------------------------------'
                                |
                                v
                 .-------------------------------.
                 | Trigger comes from staff/admin |
                 | API, Django admin, or Celery   |
                 '-------------------------------'
                                |
                                v
        .-----------------------------------------------.
        | Celery task selected                           |
        |                                               |
        | All languages: task_scrape_header_banner       |
        | One language:  task_scrape_header_banner_language |
        '-----------------------------------------------'
                                |
                                v
                 .-------------------------------.
                 | sync_all_languages() or       |
                 | sync_language(language)       |
                 '-------------------------------'
                                |
                                v
        .------------------------------------------------.
        | Validate language                              |
        | FR and GB are scrape languages                 |
        | API aliases: EN -> GB, ES/NL -> FR             |
        '------------------------------------------------'
                                |
                                v
              .-----------------------------------.
              | scrape_header_banner_html(lang)  |
              '-----------------------------------'
                                |
             .------------------+------------------.
             |                                     |
             v                                     |
  .----------------------.                         |
  | Tier 1: HTTP scrape  |                         |
  | requests GET page    |                         |
  | regex selector parse |                         |
  '----------------------'                         |
             |                                     |
      ok? ---+--- yes ----------------------------'
             |
             no
             v
  .----------------------------.
  | Tier 2: Playwright scrape  |
  | open Chromium              |
  | dismiss cookies            |
  | locate banner selectors    |
  '----------------------------'
             |
      ok? ---+--- yes ----------------------------.
             |                                    |
             no                                   |
             v                                    |
  .----------------------------.                  |
  | Tier 3: LLM fallback       |                  |
  | only if enabled            |                  |
  | local LM Studio extracts   |                  |
  | banner_html from page HTML |                  |
  '----------------------------'                  |
             |                                    |
      ok? ---+--- yes ----------------------------'
             |
             no
             v
  .--------------------------------------.
  | Write HeaderBannerSnapshot           |
  | status = fetch_failed                |
  | keep old HeaderBanner unchanged      |
  '--------------------------------------'
             |
             v
           END


  If any tier succeeds:

  .--------------------------------------.
  | parse_banner_html(banner_html)       |
  | -> text/link/br segments             |
  '--------------------------------------'
             |
             v
  .--------------------------------------.
  | Parsed zero segments?                |
  '--------------------------------------'
             |
       yes --+--> HeaderBannerSnapshot
             |    status = parse_failed
             |    keep old HeaderBanner unchanged
             |
             no
             v
  .--------------------------------------.
  | Build content hash from segments     |
  '--------------------------------------'
             |
             v
  .--------------------------------------.
  | Same hash as active HeaderBanner?    |
  '--------------------------------------'
             |
       yes --+--> HeaderBannerSnapshot
             |    status = unchanged
             |    no publish update
             |
             no
             v
  .--------------------------------------.
  | update_or_create HeaderBanner        |
  | write HeaderBannerSnapshot           |
  | status = success                     |
  '--------------------------------------'
             |
             v
           END
```

## Celery Flow

There are two Celery tasks.

| Task | Used when | What it does |
| --- | --- | --- |
| `apps.header_scraper.tasks.task_scrape_header_banner` | No language is passed | Scrapes both `FR` and `GB` by calling `sync_all_languages()` |
| `apps.header_scraper.tasks.task_scrape_header_banner_language` | A specific language is passed | Scrapes only that language by calling `sync_language(language)` |

Both tasks:

- are bound Celery tasks
- retry up to `2` times
- wait `60` seconds between retries
- return a dictionary summary of the scrape result

Example result shape:

```json
{
  "results": [
    {
      "language": "FR",
      "status": "success",
      "content_hash": "...",
      "plain_text": "...",
      "banner_id": 1
    },
    {
      "language": "GB",
      "status": "unchanged",
      "content_hash": "...",
      "plain_text": "..."
    }
  ],
  "ok": true
}
```

## How A Scrape Is Triggered

| Entry point | Route / place | Behavior |
| --- | --- | --- |
| Public API read | `GET /api/v5/header-banner?lang=FR` | Reads the latest active `HeaderBanner`; does not scrape |
| Staff scrape API | `POST /api/v5/admin/header-scraper/scrape` | Queues Celery scrape task |
| Staff job history API | `GET /api/v5/admin/header-scraper/jobs` | Lists recent `HeaderBannerSnapshot` rows |
| Django admin button | `HeaderBanner` admin `scrape-now/` | Queues Celery scrape; if broker is unavailable, runs inline |

Staff scrape body:

```json
{
  "language": "FR"
}
```

If `language` is blank or omitted, it scrapes both `FR` and `GB`.

## Scraper Tiers

The scraper uses a fallback ladder. The next tier runs only when the previous tier fails.

### Tier 1: HTTP

Function:

```text
scrape_header_banner_html_http(language)
```

Flow:

1. Validate the language.
2. Fetch the VTF homepage with `requests`.
3. Remove the language switcher from the HTML.
4. Search for known topbar/banner selectors.
5. Return `banner_html` if found.

This is the fastest and simplest tier.

### Tier 2: Playwright

Function:

```text
scrape_header_banner_html_playwright(language)
```

Flow:

1. Open the VTF homepage in headless Chromium.
2. Wait for the DOM and network to settle.
3. Best-effort dismiss cookie banners.
4. Try the same banner selector cascade in the browser DOM.
5. Return the selected node HTML.

This tier helps when the banner is changed or rendered differently after JavaScript runs.

### Tier 3: LLM Fallback

Function:

```text
scrape_header_banner_html_llm(language, page_html=http_result.page_html)
```

Flow:

1. Runs only after HTTP and Playwright fail.
2. Runs only when `LLM_FALLBACK_ENABLED` is true.
3. Sends a limited page HTML excerpt to local LM Studio.
4. Asks for strict JSON with one key: `banner_html`.
5. Validates the returned HTML through the normal parser.
6. Returns the HTML only if it produces valid banner segments.

Settings used:

| Setting | Default / meaning |
| --- | --- |
| `LLM_FALLBACK_ENABLED` | `false`; must be enabled to use this tier |
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` |
| `LMSTUDIO_MODEL` | `luth-lfm2-350m` |
| `LLM_MAX_RETRIES` | `2` |

The LLM fallback does not publish directly. It only extracts candidate `banner_html`; the normal parser and sync flow still decide whether the result is valid.

## Parsing Flow

After a tier returns `banner_html`, `sync_language()` parses it:

```text
parse_banner_html(html, base_url=source_url)
```

The parser creates ordered API segments:

| Segment type | Meaning | Example |
| --- | --- | --- |
| `text` | Normal banner text | `{ "type": "text", "value": "Early booking offer " }` |
| `link` | Clickable text with resolved URL | `{ "type": "link", "text": "See offer", "href": "https://..." }` |
| `br` | Line break | `{ "type": "br" }` |

Important parser rules:

- language switcher content is skipped
- relative links are resolved against the VTF homepage URL
- `javascript:` and hash-only links are ignored
- adjacent text nodes are merged
- whitespace is normalized
- empty segments are removed

The same segments are flattened into `plain_text` for admin display, searching, and hashes.

## The Two Tables

The scraper uses exactly two tables.

### 1. `HeaderBanner`

This is the currently published banner table.

| Field | How it is used |
| --- | --- |
| `language` | Unique language row: `FR` or `GB` |
| `segments` | API-ready ordered text/link/br content |
| `plain_text` | Flattened text for admin/search/debugging |
| `source_url` | VTF homepage used for this language |
| `content_hash` | Hash of normalized segments; used to skip unchanged publishes |
| `is_active` | Public API only serves active rows |
| `scraped_at` | Time the current content was scraped/published |
| `created_at`, `updated_at` | Normal model timestamps |

How it is used:

- The public endpoint reads this table.
- There is only one row per language because `language` is unique.
- On a changed scrape, this row is updated through `update_or_create()`.
- On scrape failure, this row is not touched, so the old banner stays live.

### 2. `HeaderBannerSnapshot`

This is the scrape history table.

| Field | How it is used |
| --- | --- |
| `language` | Language attempted |
| `status` | `success`, `unchanged`, `parse_failed`, or `fetch_failed` |
| `content_hash` | Hash when parsing succeeded |
| `plain_text` | Parsed text when parsing succeeded |
| `segments` | Parsed segments when parsing succeeded |
| `source_url` | Source page attempted |
| `error` | Error message for failed attempts |
| `scraped_at` | Attempt timestamp |

How it is used:

- Every scrape attempt writes a snapshot.
- Staff can inspect recent jobs through `GET /api/v5/admin/header-scraper/jobs`.
- Django admin can filter by language and status.
- Only the latest `50` snapshots per language are kept.

## Status Meanings

| Status | Written when | Does `HeaderBanner` change? |
| --- | --- | --- |
| `success` | Scrape succeeded, parsed segments exist, and content hash changed | Yes |
| `unchanged` | Scrape succeeded, parsed segments exist, hash equals current active banner | No |
| `parse_failed` | A tier returned HTML, but parser produced zero segments | No |
| `fetch_failed` | All scraper tiers failed, or language was unsupported | No |

## Earlier vs Current Usage

Earlier usage was simple: the frontend needed a banner, and the backend served whatever static/current banner data existed.

Current usage is safer:

| Earlier idea | Current implementation |
| --- | --- |
| One current banner value | `HeaderBanner` stores one published row per language |
| No reliable scrape audit | `HeaderBannerSnapshot` stores every attempt |
| Manual update when VTF changes | Staff/admin can queue Celery scrape |
| A failure could risk losing current data | Failures only create snapshots; current active banner remains unchanged |
| Direct HTML would be risky for frontend | HTML is normalized into `text`, `link`, and `br` segments |

## End-To-End Example

1. Staff calls:

```text
POST /api/v5/admin/header-scraper/scrape
```

2. The API queues:

```text
task_scrape_header_banner.delay()
```

3. Celery calls:

```text
sync_all_languages()
```

4. For `FR`, the scraper tries:

```text
HTTP -> Playwright -> LLM fallback
```

5. If HTTP succeeds, the later tiers are skipped.

6. The returned HTML is parsed into segments.

7. A content hash is calculated.

8. If the hash is new:

```text
HeaderBanner          updated
HeaderBannerSnapshot  created with status=success
```

9. If the hash is the same:

```text
HeaderBanner          unchanged
HeaderBannerSnapshot  created with status=unchanged
```

10. The frontend later calls:

```text
GET /api/v5/header-banner?lang=FR
```

11. The API returns the active `HeaderBanner` segments.

## Why The Flow Is Safe

- The public API reads only the published `HeaderBanner` table.
- Failed scrapes never delete or overwrite the active banner.
- Snapshots preserve history and errors for staff review.
- Hash comparison avoids unnecessary writes.
- The LLM tier is optional and still validated by the deterministic parser.
- The frontend receives structured segments instead of raw page HTML.
