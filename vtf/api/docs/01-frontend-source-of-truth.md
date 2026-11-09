# 01 — Frontend = Source of truth

> Every business rule the API needs to encode **already exists** in `vtf/front/`.
> When in doubt, read the TS. Don't invent.

## Mocks (data to load)

| File                                          | Fixture target                          | Notes                                   |
|-----------------------------------------------|-----------------------------------------|-----------------------------------------|
| `../front/src/mocks/vtfStay.mock.json`        | `apps/catalog/fixtures/villages.json`   | 32 villages + `attractionsProches`      |
| `../front/src/mocks/vtfExtras.mock.json`      | `apps/catalog/fixtures/activities.json` | Free + paid + animations + infra + clubs |
| `../front/src/mocks/vtfPricingRules.mock.json`| `apps/catalog/fixtures/pricing_rules.json` | Singleton (one active row at a time) |

## Data layer (typed re-exports of mocks)

| File                                | What it exports                                 |
|-------------------------------------|-------------------------------------------------|
| `../front/src/data/vtfStay.ts`      | `VtfVillage`, `VtfAttraction`, `VTF_VILLAGES`, `VTF_ATTRACTIONS_PROCHES` |
| `../front/src/data/vtfExtras.ts`    | `FreeActivity`, `PaidActivity`, `ACT_GRATUIT`, `ACTIVITES`, `VTF_ANIMATIONS`, `VTF_INFRA`, `VTF_CLUBS_ETE` |
| `../front/src/data/vtfPromos.ts`    | `PromoChoice`, `SEJOUR_PROMO_CATALOG`, `PROMO_NONE` (hardcoded, not in mock) |
| `../front/src/data/vtfResto.ts`     | `RestoMeal`, `VTF_RESTO_MEALS` (hardcoded, not in mock) |
| `../front/src/data/vtfTransport.ts` | `FuelOption`, `VTF_FUELS`, `VTF_TRANSPORT_DEFAULTS` (hardcoded) |

> ⚠️ The 3 last files (`vtfPromos.ts`, `vtfResto.ts`, `vtfTransport.ts`) are **hardcoded
> in TypeScript**, not in JSON mocks. To migrate them, either:
> - Move them to JSON fixtures (`apps/catalog/fixtures/`), then have the frontend fetch
>   them from `/api/v1/{promos,meals,fuels}`, **or**
> - Hardcode them in Django settings/services (acceptable: small, change rarely).
>
> Recommendation: move to fixtures for consistency with the rest of the catalog.

## Utils (logic to port)

| File                                        | Key exports (port these)                                                | Target Python module                       |
|---------------------------------------------|-------------------------------------------------------------------------|--------------------------------------------|
| `../front/src/utils/stayEstimate.ts`        | `estimateSejourTotal`, `estimateSejourWithComparison`, `SejourEstimate` | `apps/pricing/services/stay_estimate.py`   |
| `../front/src/utils/viewDetails.ts`         | `getHotelNightRate`, `estimateHotelTotal`, `calculateHotelSavings`      | `apps/pricing/services/hotel.py`           |
| `../front/src/utils/stayTab.ts`             | `addDaysIso`, `diffNuits`, `dateToSaisonIdx`, `isVillageOuvert`, `getHighlights`, `parseOuverture` | `apps/pricing/services/calendar.py` + `apps/catalog/services/highlights.py` |
| `../front/src/utils/familyTab.ts`           | `childDiscountFraction`, `QF_SEUIL_BAS`, `QF_SEUIL_HAUT`                | `apps/pricing/services/family.py`          |
| `../front/src/utils/qfCalc.ts`              | `calcQfFromIncomeParts`                                                 | `apps/pricing/services/qf.py`              |
| `../front/src/utils/promosTab.ts`           | `availableSejourPromos`, `promoKeyFromRate`                             | `apps/pricing/services/promos.py`          |
| `../front/src/utils/restoTab.ts`            | `restoTotalAmount`, `familyMealUnitPrice`                               | `apps/pricing/services/resto.py`           |
| `../front/src/utils/transportTab.ts`        | `carCostBreakdown`, `trainTotal`, `fuelCostPerKm`                       | `apps/pricing/services/transport.py`       |
| `../front/src/utils/extrasTab.ts`           | `saisonKeyFromSejour`                                                   | `apps/pricing/services/calendar.py`        |
| `../front/src/utils/planningTab.ts`         | `getStayDays`                                                           | `apps/pricing/services/calendar.py`        |

## Utils that must **not** be ported (UI-only)

- `getQfBadgeKind` — UI badge state
- `euro`, `euroCompact`, `formatEuroEn` — formatting
- `seasonLabelFromFunnelKey` — i18n labels
- `FAMILY_TAB_LIMITS`, `DEFAULT_NEW_CHILD_AGE`, `FAMILY_AGE_OPTIONS` — UI constraints
- `emptyDaySlots`, `countPlanningItems` — UI state
- `patchPromos` — state mutation helper
- `CAF_ATTESTATION_URL` — UI link

## Types (state shape, used to derive serializers)

| File                                  | Types                                  | Use in DRF                          |
|---------------------------------------|----------------------------------------|-------------------------------------|
| `../front/src/types/familyTab.ts`     | `Enfant`, `FamilyState`, `QfBadgeKind` | `FamilySerializer`                  |
| `../front/src/types/stayTab.ts`       | `SejourState`, `PlanningItem`          | `SejourSerializer`                  |
| `../front/src/types/restoTab.ts`      | `RestoTabProps`                        | (UI props — ignore)                 |
| `../front/src/types/transportTab.ts`  | `TransportTabProps`                    | (UI props — ignore)                 |
| `../front/src/types/extrasTab.ts`     | `ExtrasTabProps`, `ExtraActivitiesState` | `ExtraActivitiesSerializer`       |
| `../front/src/types/promosTab.ts`     | `PromosTabProps`                       | (UI props — ignore)                 |

## Existing audit (already produced)

`../front/docs/api-exports.md` — full audit with:
- Inventory of every export
- 24 candidate REST endpoints
- TypeScript + Zod schemas (1293 lines)
- Initial Django/DRF guide

This file is **canonical** for endpoint signatures. The current `vtf/api/docs/` extends it
with phase planning, fixture mapping, and SVD roadmap.

## Discrepancies & dedup needed before porting

| Issue                                                   | Where                                                              | Fix                              |
|---------------------------------------------------------|--------------------------------------------------------------------|----------------------------------|
| Hotel estimate logic duplicated                         | `viewDetails.ts:16-34` ↔ `stayEstimate.ts:265-275`                 | Pick one, delete the other       |
| `clampInt` defined 3 times                              | `extrasTab.ts`, `restoTab.ts`, `transportTab.ts`                   | Centralize before porting        |
| Attractions keyed by `nom` (string), not `villageId`    | `vtfStay.mock.json:attractionsProches`                             | Re-key on load to `villageId`    |
| `vtfInfra` / `vtfClubsEte` only have `lacanau`          | `vtfExtras.mock.json`                                              | Stub other villages or accept    |
| `env` is an emoji                                       | `vtfStay.mock.json:env`                                            | Add `env_code` enum side-by-side |
| `getHighlights` has FR labels hardcoded                 | `stayTab.ts:85-103`                                                | Move labels to i18n / DRF field  |
| Child discount keys must match age brackets             | `vtfPricingRules.mock.json:childDiscounts`                         | Store `1to2`/`3to5`; API aliases legacy keys for frontend compatibility |
