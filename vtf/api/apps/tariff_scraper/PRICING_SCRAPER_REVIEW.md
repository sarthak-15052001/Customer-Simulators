# VTF Tariff Scraper — Review of PS-01…PS-09 against current code

**Reviewed:** 2026-07-24, branch `claude/vtf-tariff-scraper-review-kwi3o3` (HEAD `6fc242b`)
**Scope:** `vtf/api/apps/tariff_scraper/services/scraper.py`, with `tarif_builder.py`,
`llm_fallback.py`, `tasks.py`, `approval.py`, `tarif_query.py`, `models.py` read for context.
**Method:** every defect in the remediation brief was verified *empirically* — the brief's
acceptance inputs were run against the current parser functions (pure in-memory, no network,
no browser, run date 2026-07-24). No fixes have been applied; this document records what is
actually broken before remediation starts.

> Note: the brief says the target file is `apps/tariff_scraper/services/scraper.py`; in this
> repository the path is `vtf/api/apps/tariff_scraper/services/scraper.py`.

## Verdict

**All nine defects are real and present at HEAD.** Every acceptance-table failure case in the
brief reproduces exactly as described. In addition, the review found **two date-parsing defects
not covered by the brief** (F-01, F-02 below) of the same "silently wrong, no error" class —
one of which produces bands dated 2001–2012. The brief's fixes as specified will **not** cover
them unless PS-01's scope is extended.

| ID | Claim | Status | Key evidence (scraper.py) |
|----|-------|--------|---------------------------|
| PS-01 | Cross-year bands shifted a full year | **Confirmed** | 273–274, 287–288; same class in `_parse_date_range` 227–241 |
| PS-02 | PC adult column can resolve to child price | **Confirmed** | 377 vs 406–411; false `unit_type` at 386→442 |
| PS-03 | Promo rule not enforced on grille path | **Confirmed** | 684–689, 695–703 (rule exists only on widget path, 643–647) |
| PS-04 | "Not offered" ≡ "parse failed" | **Confirmed** | 431, 448–449 bare `continue`; `is_available=True` hardcoded 441/464/492; no notes field 128–134 |
| PS-05 | Derived DP indistinguishable from scraped | **Confirmed** | 78, 324–335, 469–495; `RawPriceBand` has no derivation field 114–125 |
| PS-06 | Partial success stops the cascade | **Confirmed** | 1012–1013, 1034, 1047 — single boolean across formules |
| PS-07 | Unit strings parse as prices | **Confirmed** | 171–190 (first digit run wins, 183) |
| PS-08 | Genuine 0 € ≡ parse failure | **Confirmed** | 187 `val if val > 0 else None` + truthiness at every caller |
| PS-09 | Widget occupancy assumed, never read | **Confirmed** | 69, 637, 664, 674 |

Also confirmed:

- **The "previous attempt at PS-02" is HEAD.** Commit `17f6ce7` (2026-07-21) added
  `_is_adult_column_header` and `pc_unit_type = pc_headers[pc_adult_col_i]` — a label read
  from the same unvalidated index that produces the wrong price, so it asserts "Adultes" on a
  band that may carry the child price. The index misalignment itself was not touched. The
  brief's warning is accurate.
- **All four guardrail-protected workarounds exist and are commented** (DP nightly rounding
  475–483; `allowed_methods` copy 734–736; `apparent_encoding` avoidance 747–750; tight
  `_WIDGET_READY` selectors 515–521). None of the PS fixes require touching them.
- **There are no tests at all today** — `tests.py` is the empty Django stub. The brief's test
  suite is greenfield. `pytest`/`pytest-django` are in `requirements.txt`; `freezegun` is
  **not** (add it, or use the monkeypatched-helper option the brief allows).

---

## Empirical results per defect

### PS-01 — Cross-year date bands (confirmed)

`parse_vtf_period_cell` run on the brief's acceptance inputs (run date frozen 2026-07-24):

| Input | Current output | Expected |
|---|---|---|
| `"27/12 au 3/01/26"` | **(2026-12-27, 2027-01-03)** | (2025-12-27, 2026-01-03) |
| `"11/04 au 2/05/26"` | (2026-04-11, 2026-05-02) ✓ | same |
| `"2/05 au 4/07, 29/08 au 3/10/26"` | both ranges ✓ | same |
| `"4 au 11/07, 22 au 29/08/26"` | both ranges ✓ | same |
| `"31/12 au 7/01/27"` | **(2027-12-31, 2028-01-07)** | (2026-12-31, 2027-01-07) |

Mechanism exactly as the brief describes: `y1` inherits `y2` when absent (scraper.py:274),
then the `end < start` guard (287–288) "repairs" the inversion by pushing **end** forward a
year instead of pulling **start** back. Well-formed, plausible, a full year late, no error.

The second copy in `_parse_date_range` is also live — it is reachable for dash/à-separated
labels that `parse_vtf_period_cell` cannot parse (widget labels go through it, 603/610):
`"27/12 - 03/01/26"` → (2026-12-27, 2027-01-03), same one-year shift.

### PS-02 — PC adult column misalignment (confirmed)

`parse_grille_table` on the brief's worked example:

| Layout | Current output |
|---|---|
| Header `[PC, Période, Adultes, Enfants 2-11]`, row `[Basse, 11/04 au 2/05/26, 469 €, 329 €]` | **price 329, `unit_type='Adultes'`** — child price with a scraped label asserting it is the adult rate |
| Header `[PC, Adultes, Enfants]` (no period col) | price 469 — correct **by coincidence** |
| Header `[PC, Période, Adultes, ""]` (empty spacer) | **price 329** — the `if c.strip()` filter compounds the drift |

Root cause verified: `pc_headers` built from the **header** row minus col 0 with empties
dropped (377), the adult index computed there (378–384), then applied to `price_cells` built
from the **data** row minus cols 0–1 (406–408). Two different index spaces.

The LOC branch carries the identical latent assumption (375, 447–454). Verified: a LOC grille
whose header includes a `Période` column emits `price=469, unit_type='Période'` and
`price=569, unit_type='Studio 4 pers.'` — every unit label shifted one column. With the
comment's assumed layout (no period column in header) it aligns only by construction.

### PS-03 — Promo rule not enforced on the grille path (confirmed)

`parse_bands_from_html` on a PC grille whose price cell contains both prices:

| Cell HTML | Current parsed price |
|---|---|
| `<del>469 €</del><span>399 €</span>` | 469 (right, by source-order luck) |
| `<span>399 €</span><del>469 €</del>` | **399 — the promo price** |

`_cell_text_from_html` (684–689) flattens both numbers into one string; `_parse_price` takes
the first digit run. The struck-price rule exists only in `_read_widget_state` (643–647).

### PS-04 — "Not offered" vs "parse failed" (confirmed)

A LOC grille whose price cells are all `"—"` yields `[]` — zero bands, zero notes, zero
errors — byte-identical to a village with no LOC at all. Unparseable cells hit bare
`continue` (431, 448–449); `is_available=True` is hardcoded on every grille band (441, 464,
492); `VillageScrapeResult` has only `bands / errors / format_change` — no notes channel.

### PS-05 — Derived DP indistinguishable from scraped DP (confirmed)

With page text `"Demi-pension possible sur demande"` (no stated percentage), the current code
emits `DP price=399 source_page='price_grid'` next to `PC price=469 source_page='price_grid'`.
The DP number was **invented** from `DEFAULT_DP_REMISE = 0.15` (Lacanau's figure, 78, 333–334)
applied to any village, and nothing marks it. `RawPriceBand` has no `derivation` field.

### PS-06 — Partial success stops the cascade (confirmed)

With the HTTP tier stubbed to return **PC bands only** (no LOC), `scrape_village` was executed
end-to-end: Playwright grid calls = 0, widget calls = 0, errors = `[]`, LOC silently absent.
`has_any` (1012) is a single boolean across all formules, exactly as the brief says.

### PS-07 — Unit strings parse as prices (confirmed)

| Input | Current `_parse_price` |
|---|---|
| `"6 pers."` | **6** |
| `"7 nuits"` | **7** |
| `"Studio 4 pers. 469 €"` | **4** (not even 469) |
| `"1 234,00 €"` / `"469"` / `"469 &euro;"` / `"1 234 €"` | 1234.00 / 469 / 469 / 1234 ✓ |

Note `"Studio 4 pers. 469 €"` → 4: the first digit run wins, so a merged unit+price cell
produces a price of 4 €. The documented French formats all still parse correctly.

### PS-08 — Genuine 0 € ≡ parse failure (confirmed)

`_parse_price("0 €")` → `None` (187). Truthiness sites the fix must convert, verified present:
PC guard + fallback loop (421–431), LOC `if not price` (448–449), DP guard (473), `has_any`
(1012, 1039–1041), both `priced` comprehensions (1059–1062, 1091–1094), widget
`if regular_price: break` (658–659) and `if not regular_price` (661). **Two sites beyond the
brief's list also need the same treatment:** `FormatChangeInfo.priced_bands` (798–801) and
`tasks.py:111–115` (`priced_bands` summary count). `llm_fallback.py` has its own
`d if d > 0 else None` copies (366, 378) — see F-03.

### PS-09 — Widget occupancy assumed (confirmed)

`_read_widget_state` run against a stub page that visibly reports **3 adults** with a 938 €
total: emitted band has `per_adult=469.00, nb_adults=2`. True per-adult is 312.67. The
occupancy selector is never read (69, 637, 664, 674).

---

## Additional findings (not in the brief)

### F-01 — Year-hint regex reads the end *month* as the year → bands dated 2001–2012 (P1, fold into PS-01)

`parse_vtf_period_cell` pulls its cell-level default year with
`re.search(r"/(\d{2,4})\s*$", text)` (258–259). On a **year-less** cell, that regex matches
the final date's *month*. Verified:

| Input | Current output |
|---|---|
| `"11/04 au 2/05"` | **(2005-04-11, 2005-05-02)** |
| `"4 au 11/07"` | **(2007-07-04, 2007-07-11)** |
| `"27/12 au 3/01"` | **(2001-12-27, 2002-01-03)** |

These bands have valid dates and prices, so `tarif_builder` will happily snapshot and propose
them; `get_active_tarif`'s date filter then never matches a real stay, so the formule is
*silently missing* — the exact failure class this remediation exists to kill. The PS-01 fix
as specified (the `m1 > m2` rule) does **not** touch this. Recommendation: within the PS-01
commit, require the year hint to be a full `d/m/y` fragment
(`\d{1,2}/\d{1,2}/(\d{2,4})\s*$`), and treat "no year anywhere in the cell" explicitly
(today's-year default plus roll-forward, or skip with a parse note). Add year-less cells to
the acceptance tests.

### F-02 — The year-less roll-forward branch is dead code (P3, fold into PS-01)

The guard at 290: `if end < date.today() and not re.search(r"/\d{2,4}", part)`. Every part
that matched either range regex necessarily contains `d/m` with a slash, so
`not re.search(...)` is always False and the roll-forward never fires. Together with F-01
this means year-less past bands are never repaired. Whatever the PS-01 rework decides for
year-less cells, this branch should either become reachable or be removed.

### F-03 — `llm_fallback.py` carries its own copies of four defect classes (report-only, tier 4)

The brief scopes fixes to `scraper.py`, but note the LLM tier independently re-implements:

- **PS-02 class:** PC adult price = *first* price cell (`_cells_for_llm`, llm_fallback.py:274–281)
  and "first valid price" (502–507); `chunk_grille_html` also drops empty cells (189–190).
- **PS-03 class:** the chunker flattens cell HTML before the LLM sees it (185–188), so a promo
  cell sends both numbers with no strike information.
- **PS-05 class:** `DEFAULT_DP_REMISE` fallback with no stated/assumed distinction (524–526)
  — `source_page="llm_fallback"` marks the tier, not the derivation.
- **PS-08 class:** `d if d > 0 else None` (366, 378).

Fixing `scraper.py` does **not** fix tier 4. Either extend the fixes there in a follow-up
or accept that LLM-tier bands keep these behaviours (they at least carry
`source_page="llm_fallback"` for routing).

### F-04 — HTTP table parser ignores `colspan` and truncates nested tables (P3, follow-up note per guardrail 3)

`extract_tables_from_html` (695–707) matches `<table…>…</table>` non-greedily (nested tables
truncate the outer one) and expands no `colspan` — only the Playwright tertiary path does
(909–939). A grille using a colspan'd header cell shifts every price column on the *primary*
path. PS-02's right-alignment + misalignment assertion will at least turn this from silent
into loud. Keep as a follow-up for the eventual real-parser swap; do not fix in this pass.

---

## Implementation notes for the fixer (ambiguities to resolve first)

1. **PS-02 acceptance row 4 is inconsistent with PS-02 rule 3 as written.** Header
   `["Pension complète","Période"]` with data `["Basse","…","469 €","329 €"]`: rule 3 fires on
   `len(raw_headers) < len(price_cells)` → 2 < 2 is **False**, yet the acceptance table expects
   `change_type="header_misalignment"`. Right-alignment would hand back
   `["Pension complète","Période"]` as the price headers (no adult column → rule 4's parse
   note, a different outcome). Decide the misalignment predicate before coding — e.g. flag
   when the right-aligned header window would overlap the title/period columns
   (`len(raw_headers) - len(price_cells) < expected_leading_cols`), or compare against the
   full data-row length. Get this agreed, or the acceptance suite cannot pass as written.
2. **PS-03 acceptance case 3 needs the cell's own attributes.** `extract_tables_from_html`
   currently passes only the cell's *inner* HTML (`c.group(1)`, 699–701) to
   `_cell_text_from_html`, so `<td class="prix-barre">469 €</td>` is invisible to any
   struck-fragment inspection. The fix must capture the full cell tag (group 0 / attributes),
   not just retarget the inner-HTML string.
3. **PS-05/PS-04 fields need a persistence decision.** `RawPriceBand.derivation` and
   `parse_notes` live only in memory. `PriceSnapshot` (models.py:47–94) has no `derivation`
   column and `TariffApproval.proposed_bands` rows carry no such key — without a small
   migration + `tarif_builder` change, traceability dies at the DB boundary and the review
   routing the brief wants (`derivation != "scraped"` → review) has nothing to read. At
   minimum, report this in the PR as required follow-up; ideally include the migration.
4. **PS-08 changes escalation semantics deliberately.** Once `Decimal("0")` counts as priced,
   a page of genuine zeros no longer trips the `zero_prices` format-change path or the LLM
   tier (1059–1063, 1113–1128) — that is the intended behaviour, but `tarif_builder` currently
   lumps 0 into `skipped_no_price` (tarif_builder.py:93, 160), so zeros still won't reach
   proposals until the builder decides what 0 means. State that in the PR.
5. **PS-06's `expected_formules` caller lives in `tasks.py`.** `task_scrape_village_tariffs`
   calls `scrape_village(village_id, url)` (tasks.py:108) and has access to the catalog
   `Village` record — that is where the village's known formules should be passed from.
6. **Freeze the clock.** Multiple paths branch on `date.today()` (227–241, 256–259, 290–292).
   `freezegun` is not in `requirements.txt`; add it or monkeypatch a clock helper. Today's
   suite would pass in July and behave differently in January exactly as the brief warns.

## Data already written — impact statement

Both PS-01 and PS-02 produce plausible values with no error, so **existing `PriceSnapshot`,
`TariffApproval.proposed_bands`, `VillageTarif` rows, `Village.tarifs` season patches, and the
`villages.json` fixture (synced on approve, approval.py:186–187) may all contain wrong values
that are not identifiable by inspection**:

- **PS-01:** every ski village's New Year band is stored one year late (e.g. 2026-12-27 →
  2027-01-03 instead of 2025-12-27 → 2026-01-03). Because `get_active_tarif` matches by date
  (tarif_query.py:34–40), a Christmas-2026 stay **will** match that mis-dated band and quote
  last season's New Year price — an actively wrong customer quote, not just a missing one.
- **PS-02:** any village whose PC header carries a period column (or spacer cells) has the
  child rate stored as the adult rate, labeled `unit_type="Adultes"`.

The only remedy is a full re-scrape with the fixed parser and a diff against existing rows —
affected rows cannot be found by querying. Season buckets in `Village.tarifs` keyed off
`saison_key(date_start)` compound PS-01: a year-shifted start can land the price in the wrong
season bucket ("fetes" vs "hs"), and `build_season_tarifs_patch` keeps the *first* band seen
per season for PC/DP, so ordering hides it.

## Suggested adjustments to the work order (no reordering needed)

- Extend **PS-01** to include F-01 (year-hint regex) and F-02 (dead roll-forward) — same
  function, same class, same acceptance table; fixing PS-01 without F-01 leaves year-less
  cells producing 2001–2012 bands and a false sense that date parsing is now safe.
- Extend **PS-08**'s checklist with the two extra truthiness sites above
  (`FormatChangeInfo.priced_bands`, `tasks.py` summary count).
- Resolve ambiguity (1) with the brief's author before starting PS-02.
