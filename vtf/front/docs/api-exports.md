# Audit — Données & utilitaires exportables en API

> **Objectif** : recenser tout ce qui, dans `src/mocks/*.json` et `src/utils/*.ts`, peut devenir un endpoint REST stable, et fournir les schémas (TypeScript + Zod) ainsi qu'un guide d'implémentation Django/DRF.
>
> **Branche** : `claude/audit-mocks-api-exports-mM0QT`
> **Périmètre** : 3 mocks JSON + 10 fichiers utils + 5 fichiers data (typage des mocks).

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Inventaire des mocks (`src/mocks/*.json`)](#2-inventaire-des-mocks)
3. [Inventaire des utils (`src/utils/*.ts`)](#3-inventaire-des-utils)
4. [Endpoints REST recommandés](#4-endpoints-rest-recommandés)
5. [Schémas TypeScript prêts à l'emploi](#5-schémas-typescript)
6. [Schémas Zod (validation runtime)](#6-schémas-zod)
7. [Guide d'implémentation Django / DRF](#7-guide-dimplémentation-django--drf)
8. [Recommandations de migration](#8-recommandations-de-migration)

---

## 1. Vue d'ensemble

### Architecture actuelle

```
src/
├── mocks/                    # Données figées (JSON)
│   ├── vtfStay.mock.json     # Catalogue des 32 villages + attractions
│   ├── vtfExtras.mock.json   # Activités, animations, infra, clubs
│   └── vtfPricingRules.mock.json  # Règles tarifaires (coefficients)
├── data/                     # Typage + ré-export des mocks
│   ├── vtfStay.ts            # Types VtfVillage, VtfAttraction
│   ├── vtfExtras.ts          # Types FreeActivity, PaidActivity, etc.
│   ├── vtfPromos.ts          # Catalogue de promos (en dur, hors mock)
│   ├── vtfResto.ts           # Repas hors VTF (en dur, hors mock)
│   └── vtfTransport.ts       # Carburants & defaults (en dur, hors mock)
└── utils/                    # Logique métier
    ├── viewDetails.ts        # Comparaison hôtel classique
    ├── stayEstimate.ts       # ⭐ Estimation séjour complet
    ├── stayTab.ts            # Calendrier, saison, ouverture
    ├── familyTab.ts          # Quotient familial, dégressivité enfants
    ├── qfCalc.ts             # Calcul QF depuis revenus/parts
    ├── promosTab.ts          # Promos disponibles (1ère min, etc.)
    ├── restoTab.ts           # Total restauration
    ├── transportTab.ts       # Coût voiture / train
    ├── extrasTab.ts          # Helpers saison, formatage
    └── planningTab.ts        # Jours du séjour, créneaux
```

### Synthèse "exportable / non exportable"

| Catégorie                 | Exportable tel quel | Wrapper requis | Frontend-only |
|---------------------------|---------------------|----------------|---------------|
| Mocks JSON                | ✅ 3 fichiers        | -              | -             |
| Pure functions (calc)     | ✅ ~15 fonctions     | -              | -             |
| Functions impures (state) | -                   | ✅ Zod input    | -             |
| Helpers UI (`euro`, `seasonLabelFromFunnelKey`) | - | -            | ✅ rester côté front |
| Types                     | -                   | ✅ → DRF/Pydantic | -          |

---

## 2. Inventaire des mocks

### 2.1 `vtfStay.mock.json`

```json
{
  "villages": [ /* 32 entrées */ ],
  "attractionsProches": { "Biarritz": [...], "Bandol": [...], ... }
}
```

**Structure d'un village** (`villages[]`)

| Champ          | Type                                 | Présent partout | Notes                                     |
|----------------|--------------------------------------|-----------------|-------------------------------------------|
| `id`           | string (kebab-case)                  | oui             | Clé primaire                              |
| `nom`          | string                               | oui             |                                           |
| `nom2`         | string?                              | non             | Sous-titre / nom du domaine               |
| `region`       | enum string (8 valeurs)              | oui             | Voir liste ci-dessous                     |
| `env`          | emoji string (🌊 ⛰️ 🌲 🌻 ☀️)        | oui             | À normaliser en `enum` côté API           |
| `formules`     | `('PC' \| 'DP' \| 'LOC')[]`          | oui             |                                           |
| `hasLoc`       | boolean                              | oui             | Redondant avec `formules.includes('LOC')` |
| `ski`          | boolean                              | oui             |                                           |
| `ouverture`    | string (texte libre, à parser)       | non             | Voir `parseOuverture()` ds `stayTab.ts`   |
| `tarifs.PC`    | `{ hs, vs, ete, fetes }` (€)         | oui             | Tarifs par saison                         |
| `tarifs.LOC`   | idem                                 | oui             |                                           |
| `bebeClub`     | boolean?                             | non             | Club bébé dès 4 mois                      |
| `forfaitRM`    | boolean?                             | non             | Forfait remontées mécaniques inclus       |
| `qfExc`        | boolean?                             | non             | Tarif QF exclusif                         |
| `enfSoloHalf`  | boolean?                             | non             | -50% enfant parent solo (été)             |

**Régions** (8 valeurs, à figer en `enum`) :
```
"Bretagne / Normandie", "Aquitaine / Landes", "Méditerranée / PACA",
"Alpes / Savoie", "Alpes du Sud", "Massif Central / Jura",
"Campagne / Provence", "Occitanie / Pyrénées"
```

**Saisons** (4 clés) : `hs` (hors saison) · `vs` (vacances scolaires) · `ete` · `fetes`

**Attractions** (`attractionsProches[<nomVillage>]`) : `{ nom, type, icon, km }[]`

> ⚠️ **Note** : la clé d'attraction est `nom` (string), pas `id`. À nettoyer côté API en `village_id`.

### 2.2 `vtfExtras.mock.json`

| Bloc                | Type                                                     | Cardinalité       |
|---------------------|----------------------------------------------------------|-------------------|
| `actGratuit`        | `Record<region, FreeActivity[]>`                         | 8 régions × 5 act |
| `activitesPayantes` | `Record<region, PaidActivity[]>`                         | 8 régions × 5–14  |
| `vtfAnimations`     | `{ nom, note }[]`                                        | 4 entrées         |
| `vtfInfra`          | `Record<villageId, { infra, anim, extras }>`             | 1 (lacanau)       |
| `vtfClubsEte`       | `Record<villageId, { paques, ete, toussaint }>`          | 1 (lacanau)       |

**`FreeActivity`** : `{ id, nom, type }` — `id` au format `free:<region2>:<slug>`
**`PaidActivity`** : `{ id, nom, type, ad: number, enf: number, saisons: VtfSaisonKey[] }`
- `ad`/`enf` = prix unitaire € adulte/enfant
- `saisons` = saisons d'ouverture

> ⚠️ `vtfInfra` et `vtfClubsEte` sont **incomplets** (seulement `lacanau`). À compléter avant exposition API.

### 2.3 `vtfPricingRules.mock.json`

Ressource singleton (un seul jeu de règles, versionné par `updatedAt`).

| Clé                          | Type                                  | Sémantique                                  |
|------------------------------|---------------------------------------|---------------------------------------------|
| `updatedAt`                  | ISO date                              | Versioning                                  |
| `durationCoefficients`       | `Record<nuits, coef>` (ex: 7 → 1.0)   | Fallback `nuits/7` sinon                    |
| `formulaCoefficients`        | `{ PC: 1.0, DP: 0.82 }`               | LOC traité à part (`= 1`)                   |
| `membership.individual`      | 22                                    | Adhésion solo                               |
| `membership.familyOrCouple`  | 44                                    | Adhésion famille/couple                     |
| `soloSupplementPerNight`     | `{ default: 22, reduced: 11, off: 0 }`| Supplément/nuit si 1 adulte + ≥1 enfant     |
| `quinzaineFuteeRate`         | 0.1                                   | -10% si PC + ≥14 nuits                      |
| `maxiFamilyChildrenRate`     | 0.2                                   | -20% par enfant si maxi-famille (≥3 enf)    |
| `defaults.*`                 | divers                                | Prix par défaut (act, repas, kit, etc.)     |
| `childDiscounts`             | `{ lt1, 1to3_*, 4to5, 6to10, 11to15, ge16 }` | Dégressivité enfant par âge          |

---

## 3. Inventaire des utils

> Pour chaque export : signature, fichier source, nature (pure / impure), utilité côté API.

### 3.1 `viewDetails.ts` (3 exports)

| Export                  | Signature                                                              | Source           | Pure | API ?                          |
|-------------------------|------------------------------------------------------------------------|------------------|------|--------------------------------|
| `getHotelNightRate`     | `(saisonKey) => number`                                                | `viewDetails.ts:7`  | ✅   | Helper interne                 |
| `estimateHotelTotal`    | `(family, estimate) => number`                                         | `viewDetails.ts:16` | ✅   | ✅ `POST /estimate/hotel`      |
| `calculateHotelSavings` | `(family, estimate) => number`                                         | `viewDetails.ts:39` | ✅   | ✅ ou intégré à l'estimation   |

> ⚠️ **Duplication** : la même logique hôtel est inlinée dans `stayEstimate.ts:265-275` (`estimateSejourWithComparison`). À consolider avant exposition.

### 3.2 `stayEstimate.ts` (2 exports + 1 type) ⭐ cœur métier

| Export                          | Signature                                                                           | Source                | Pure | API ?                       |
|---------------------------------|-------------------------------------------------------------------------------------|-----------------------|------|-----------------------------|
| `estimateSejourTotal`           | `({ family, sejour, village }) => SejourEstimate \| null`                           | `stayEstimate.ts:137` | ✅   | ✅ `POST /estimate/stay`    |
| `estimateSejourWithComparison`  | idem + `hotelEstimate`, `hotelSavings`, `savingsPct`                                | `stayEstimate.ts:256` | ✅   | ✅ (variante `?compare=1`)  |
| `type SejourEstimate`           | 16 champs (total, perPerson, totalAdults, ..., savingsPct)                          | `stayEstimate.ts:58`  | -    | Schéma de réponse           |

**Dépendances** :
- mocks : `vtfPricingRules.mock.json`
- data : `ACTIVITES`, `VTF_RESTO_MEALS`, `VTF_TRANSPORT_DEFAULTS`
- utils : `carCostBreakdown`, `trainTotal`, `dateToSaisonIdx`, `diffNuits`, `QF_SEUIL_*`

### 3.3 `stayTab.ts` (5 exports + 2 types + 1 const)

| Export                  | Signature                                                              | Pure | API ?                      |
|-------------------------|------------------------------------------------------------------------|------|----------------------------|
| `addDaysIso`            | `(iso, days) => iso`                                                   | ✅   | Helper                     |
| `diffNuits`             | `(start, end) => number \| null`                                       | ✅   | Helper                     |
| `dateToSaisonIdx`       | `(iso) => 0 \| 1 \| 2 \| 3`                                            | ✅   | ✅ `GET /season?date=...`  |
| `isVillageOuvert`       | `(ouvertureStr, dateStr) => boolean`                                   | ✅   | ✅ filtre `/villages`      |
| `getHighlights`         | `(village) => { icon, txt }[]`                                         | ✅   | ✅ intégré à `/villages/:id`|
| `SEJOUR_SAISON_OPTIONS` | constante                                                              | -    | ✅ `GET /seasons`          |
| `type SejourEnvKey`     | `'mer' \| 'montagne' \| 'campagne' \| 'ski' \| 'fond'`                 | -    | enum API                   |

> 💡 **`getHighlights`** : contient des libellés français en dur (`'Bord de mer / plage'`...). À i18n-iser avant exposition API multilingue.

### 3.4 `familyTab.ts` (3 fonctions + 5 constantes + 1 type)

| Export                       | Type                                                       | Pure | API ?            |
|------------------------------|------------------------------------------------------------|------|------------------|
| `clamp`                      | `(n, min, max) => number`                                  | ✅   | utilitaire       |
| `childDiscountFraction`      | `(age) => number` (0–1)                                    | ✅   | ✅ `GET /pricing/child-discount` |
| `getQfBadgeKind`             | `(qfVal) => QfBadgeKind`                                   | ✅   | UI-only          |
| `CAF_ATTESTATION_URL`        | const                                                      | -    | -                |
| `QF_SEUIL_BAS` / `QF_SEUIL_HAUT` | 880 / 1350                                              | -    | ✅ via `/pricing-rules` |
| `FAMILY_TAB_LIMITS`          | bornes UI                                                  | -    | UI-only          |
| `DEFAULT_NEW_CHILD_AGE`      | 6                                                          | -    | UI-only          |
| `FAMILY_AGE_OPTIONS`         | array                                                      | -    | UI-only          |

### 3.5 `qfCalc.ts` (1 export)

| Export                  | Signature                                                  | Pure | API ?                        |
|-------------------------|------------------------------------------------------------|------|------------------------------|
| `calcQfFromIncomeParts` | `({ netMonthlyIncome, parts }) => number`                  | ✅   | ✅ `POST /family/qf`         |

### 3.6 `promosTab.ts` (5 exports)

| Export                   | Signature                                                       | Pure | API ?                          |
|--------------------------|-----------------------------------------------------------------|------|--------------------------------|
| `clampRate01`            | `(r) => number`                                                 | ✅   | utilitaire                     |
| `dateDiffNuits`          | `(start, end) => number`                                        | ✅   | utilitaire                     |
| `availableSejourPromos`  | `({ dateDebut, dateFin, now? }) => PromoChoice[]`               | ✅   | ✅ `GET /promos/available`     |
| `promoKeyFromRate`       | `(rate) => VtfPromoKey`                                         | ✅   | helper                         |
| `patchPromos`            | `(sejour, partial) => SejourState`                              | ✅   | UI-only (state mutation)       |

> ⚠️ `availableSejourPromos` utilise `new Date()` par défaut. Toujours passer `now` explicitement côté API pour rester pur/testable.

### 3.7 `restoTab.ts` (5 exports + 1 const)

| Export                  | Signature                                                          | Pure | API ?                       |
|-------------------------|--------------------------------------------------------------------|------|-----------------------------|
| `clampInt`              | `(n, min, max) => number`                                          | ✅   | utilitaire                  |
| `sumQty`                | `(map) => number`                                                  | ✅   | utilitaire                  |
| `restoNoteKey`          | `(formule) => 'notePC' \| 'noteDP' \| 'noteLOC'`                   | ✅   | utilitaire                  |
| `familyMealUnitPrice`   | `({ meal, adults, children }) => number`                           | ✅   | helper                      |
| `restoTotalAmount`      | `({ meals, qtyByMealId, adults, children }) => number`             | ✅   | ✅ `POST /resto/total`      |
| `EMPTY_RESTO_QTY_MAP`   | `{}`                                                               | -    | UI-only                     |

### 3.8 `transportTab.ts` (3 exports)

| Export                | Signature                                                   | Pure | API ?                       |
|-----------------------|-------------------------------------------------------------|------|-----------------------------|
| `clampInt`            | `(n, min, max) => number`                                   | ✅   | utilitaire (dupliqué)       |
| `fuelCostPerKm`       | `(fuel) => number`                                          | ✅   | helper                      |
| `carCostBreakdown`    | `({ distanceOneWayKm, fuel }) => { kmAR, fuelCost, tollCost, total }` | ✅ | ✅ `POST /transport/car` |
| `trainTotal`          | `({ adults, children }) => number`                          | ✅   | ✅ `POST /transport/train`  |

### 3.9 `extrasTab.ts` (5 exports)

| Export                       | Signature                                                  | Pure | API ?         |
|------------------------------|------------------------------------------------------------|------|---------------|
| `saisonKeyFromSejour`        | `(sejour) => VtfSeasonKey`                                 | ✅   | helper        |
| `clampInt`                   | dupliqué                                                   | ✅   | utilitaire    |
| `qtyFromMap`                 | helper                                                     | ✅   | helper        |
| `euro` / `euroCompact` / `formatEuroEn` | formatage                                       | ✅   | UI-only       |
| `seasonLabelFromFunnelKey`   | i18n libellé saison                                        | ✅   | UI-only       |

### 3.10 `planningTab.ts` (3 exports + 1 type)

| Export                | Signature                                                         | Pure | API ?                |
|-----------------------|-------------------------------------------------------------------|------|----------------------|
| `getStayDays`         | `(start, end) => StayDay[]`                                       | ✅   | ✅ `GET /stay-days`  |
| `emptyDaySlots`       | `() => { matin, aprem, soir }`                                    | ✅   | UI-only              |
| `countPlanningItems`  | `(planning) => number`                                            | ✅   | UI-only              |
| `type StayDay`        | `{ key, label, date }`                                            | -    | schéma réponse       |

### 3.11 Bilan exports / duplications à corriger

- `clampInt` est défini **3 fois** (`extrasTab.ts`, `restoTab.ts`, `transportTab.ts`) → centraliser
- L'estimation hôtel est dupliquée entre `viewDetails.ts` et `stayEstimate.ts:265-275` → réutiliser `estimateHotelTotal`
- `getHotelNightRate` n'est pas paramétrable (saisons figées en dur) → exposer via `pricingRules` une fois côté API

---

## 4. Endpoints REST recommandés

### 4.1 Lecture (data)

| Méthode  | Chemin                                           | Source                          | Cache    |
|----------|--------------------------------------------------|---------------------------------|----------|
| `GET`    | `/api/v1/villages`                               | `vtfStay.mock.json`             | 1 j      |
| `GET`    | `/api/v1/villages/{id}`                          | id + highlights + attractions   | 1 j      |
| `GET`    | `/api/v1/villages/{id}/highlights`               | `getHighlights()`               | 1 j      |
| `GET`    | `/api/v1/villages/{id}/attractions`              | `attractionsProches`            | 1 j      |
| `GET`    | `/api/v1/villages/{id}/infra`                    | `vtfInfra`                      | 1 j      |
| `GET`    | `/api/v1/villages/{id}/clubs-ete`                | `vtfClubsEte`                   | 1 j      |
| `GET`    | `/api/v1/regions`                                | dérivé (8 régions)              | 1 sem    |
| `GET`    | `/api/v1/seasons`                                | `SEJOUR_SAISON_OPTIONS`         | 1 sem    |
| `GET`    | `/api/v1/regions/{region}/activities?kind=free`  | `actGratuit`                    | 1 j      |
| `GET`    | `/api/v1/regions/{region}/activities?kind=paid`  | `activitesPayantes`             | 1 j      |
| `GET`    | `/api/v1/animations`                             | `vtfAnimations`                 | 1 j      |
| `GET`    | `/api/v1/meals`                                  | `VTF_RESTO_MEALS` (data)        | 1 sem    |
| `GET`    | `/api/v1/fuels`                                  | `VTF_FUELS` (data)              | 1 sem    |
| `GET`    | `/api/v1/promos/catalog`                         | `SEJOUR_PROMO_CATALOG`          | 1 sem    |
| `GET`    | `/api/v1/pricing-rules`                          | `vtfPricingRules.mock.json`     | 1 j      |

### 4.2 Calcul (utils, idempotents → `POST` car body riche)

| Méthode  | Chemin                                | Body                                    | Réponse                            |
|----------|---------------------------------------|-----------------------------------------|------------------------------------|
| `POST`   | `/api/v1/estimate/stay`               | `{ family, sejour, villageId }`         | `SejourEstimate` (avec hôtel)      |
| `POST`   | `/api/v1/estimate/hotel`              | `{ family, estimate }`                  | `{ total, savings, savingsPct }`   |
| `POST`   | `/api/v1/promos/available`            | `{ dateDebut, dateFin, now? }`          | `PromoChoice[]`                    |
| `POST`   | `/api/v1/family/qf`                   | `{ netMonthlyIncome, parts }`           | `{ qfVal, badge }`                 |
| `POST`   | `/api/v1/transport/car`               | `{ distanceOneWayKm, fuel }`            | `{ kmAR, fuelCost, tollCost, total }` |
| `POST`   | `/api/v1/transport/train`             | `{ adults, children }`                  | `{ total }`                        |
| `POST`   | `/api/v1/resto/total`                 | `{ qtyByMealId, adults, children }`     | `{ total }`                        |
| `POST`   | `/api/v1/stay/days`                   | `{ dateDebut, dateFin }`                | `StayDay[]`                        |
| `GET`    | `/api/v1/season?date=YYYY-MM-DD`      | -                                       | `{ saisonKey, saisonIdx }`         |

> 💡 **Convention** : tous les `POST /estimate/*` et `/transport/*` sont **purs** (idempotents, sans effet de bord). Penser au cache HTTP `Cache-Control: max-age=60` côté CDN/reverse-proxy.

---

## 5. Schémas TypeScript

> Prêts à coller dans une lib partagée (ex: `@uptoone/customer-simulators-types`).

```ts
// ─── Énumérations ────────────────────────────────────────────
export type VtfFormule = 'PC' | 'DP' | 'LOC'
export type VtfSaisonKey = 'hs' | 'vs' | 'ete' | 'fetes'
export type VtfRegion =
  | 'Bretagne / Normandie'
  | 'Aquitaine / Landes'
  | 'Méditerranée / PACA'
  | 'Alpes / Savoie'
  | 'Alpes du Sud'
  | 'Massif Central / Jura'
  | 'Campagne / Provence'
  | 'Occitanie / Pyrénées'
export type VtfEnv = '🌊' | '⛰️' | '🌲' | '🌻' | '☀️'
export type FuelKey = 'essence' | 'diesel' | 'electrique'
export type TransportMode = 'car' | 'train' | 'onSite'
export type RestoMealId = 'pique' | 'snack' | 'bistrot' | 'gastro'
export type VtfPromoKey = 'none' | 'premiere' | 'derniere' | 'jeudi' | 'pack'

// ─── Ressources ──────────────────────────────────────────────
export interface VtfVillage {
  id: string
  nom: string
  nom2?: string
  region: VtfRegion
  env: VtfEnv
  formules: VtfFormule[]
  hasLoc: boolean
  ski: boolean
  ouverture?: string
  tarifs: {
    PC?: Partial<Record<VtfSaisonKey, number>>
    LOC?: Partial<Record<VtfSaisonKey, number>>
  }
  bebeClub?: boolean
  forfaitRM?: boolean
  qfExc?: boolean
  enfSoloHalf?: boolean
}

export interface VtfAttraction {
  nom: string
  type: string
  icon: string
  km: number
}

export interface FreeActivity {
  id: string
  nom: string
  type: string
}
export interface PaidActivity extends FreeActivity {
  ad: number
  enf: number
  saisons: VtfSaisonKey[]
}

export interface PricingRules {
  updatedAt: string
  durationCoefficients: Record<string, number>
  formulaCoefficients: { PC: number; DP: number }
  membership: { individual: number; familyOrCouple: number }
  soloSupplementPerNight: { default: number; reduced: number; off: number }
  quinzaineFuteeRate: number
  maxiFamilyChildrenRate: number
  defaults: {
    activityPriceAdult: number; activityPriceChild: number
    mealPriceAdult: number; mealPriceChild: number
    locKitPrice: number
    tollPerKm: number; fuelCostPerKm: number
    trainAdultOneWay: number; trainChildOneWay: number
  }
  childDiscounts: {
    lt1: number
    '1to3_withBebeClub': number
    '1to3_withoutBebeClub': number
    '4to5': number
    '6to10': number
    '11to15': number
    ge16: number
  }
}

// ─── Inputs / Outputs des endpoints calcul ───────────────────
export interface EstimateStayInput {
  family: { adultes: number; enfants: { age: number }[]; qfVal: number | null; maxiFamily: boolean }
  sejour: {
    dateDebut: string; dateFin: string
    formule: VtfFormule
    fNuits: number
    extras?: { locCleaningFee?: number; locKits?: number }
    activities?: { outings?: number; priceAdult?: number; priceChild?: number }
    extraActivities?: { paidQtyById?: Record<string, number> }
    resto?: { qtyByMealId?: Partial<Record<RestoMealId, number>> }
    transport?: { mode: TransportMode; distanceOneWayKm?: number; fuel?: FuelKey }
    promos?: { promoSejourRate?: number; quinzaineFutee?: boolean; soloSupplementMode?: 'default' | 'reduced' | 'off' }
  }
  villageId: string
}

export interface SejourEstimate {
  total: number
  perPerson: number
  totalAdults: number
  totalChildren: number
  perAdultBase: number
  childLines: { age: number; discountFraction: number; amount: number }[]
  saisonKey: VtfSaisonKey
  nuits: number
  discountRate: number
  staySubtotal: number
  adhesion: number
  soloSupplement: number
  extrasLoc: number
  activitiesTotal: number
  restoTotal: number
  transportTotal: number
  hotelEstimate: number
  hotelSavings: number
  savingsPct: number
}

export interface CarCostInput { distanceOneWayKm: number; fuel: FuelKey }
export interface CarCostOutput { kmAR: number; fuelCost: number; tollCost: number; total: number }

export interface TrainCostInput { adults: number; children: number }
export interface TrainCostOutput { total: number }

export interface RestoTotalInput {
  qtyByMealId: Partial<Record<RestoMealId, number>>
  adults: number
  children: number
}

export interface QfInput { netMonthlyIncome: number; parts: number }
export interface QfOutput { qfVal: number; badge: 'empty' | 'r1' | 'r2' | 'plein' }

export interface AvailablePromosInput {
  dateDebut: string
  dateFin: string
  now?: string
}
export interface PromoChoice {
  key: VtfPromoKey
  icon: string
  label: string
  description: string
  tag: string
  rate: number
  kind: 'auto' | 'manual'
}
```

---

## 6. Schémas Zod

> ⚠️ Zod n'est **pas** une dépendance actuelle (`npm i zod`). Schémas pensés pour le **client** (front qui consomme l'API) et/ou un **BFF Node**. Côté Django, on utilisera `serializers` DRF (section 7).

```ts
// schemas.ts
import { z } from 'zod'

// ─── Énumérations ────────────────────────────────────────────
export const VtfFormuleSchema = z.enum(['PC', 'DP', 'LOC'])
export const VtfSaisonKeySchema = z.enum(['hs', 'vs', 'ete', 'fetes'])
export const VtfRegionSchema = z.enum([
  'Bretagne / Normandie', 'Aquitaine / Landes', 'Méditerranée / PACA',
  'Alpes / Savoie', 'Alpes du Sud', 'Massif Central / Jura',
  'Campagne / Provence', 'Occitanie / Pyrénées',
])
export const FuelKeySchema = z.enum(['essence', 'diesel', 'electrique'])
export const TransportModeSchema = z.enum(['car', 'train', 'onSite'])
export const RestoMealIdSchema = z.enum(['pique', 'snack', 'bistrot', 'gastro'])
export const VtfPromoKeySchema = z.enum(['none', 'premiere', 'derniere', 'jeudi', 'pack'])

// ─── Common ──────────────────────────────────────────────────
export const IsoDateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'YYYY-MM-DD')
export const PriceSchema = z.number().int().nonnegative()

// ─── Resources ───────────────────────────────────────────────
export const VtfVillageSchema = z.object({
  id: z.string().min(1),
  nom: z.string().min(1),
  nom2: z.string().optional(),
  region: VtfRegionSchema,
  env: z.string().min(1),
  formules: z.array(VtfFormuleSchema).min(1),
  hasLoc: z.boolean(),
  ski: z.boolean(),
  ouverture: z.string().optional(),
  tarifs: z.object({
    PC: z.record(VtfSaisonKeySchema, PriceSchema).optional(),
    LOC: z.record(VtfSaisonKeySchema, PriceSchema).optional(),
  }),
  bebeClub: z.boolean().optional(),
  forfaitRM: z.boolean().optional(),
  qfExc: z.boolean().optional(),
  enfSoloHalf: z.boolean().optional(),
})

export const VtfAttractionSchema = z.object({
  nom: z.string(),
  type: z.string(),
  icon: z.string(),
  km: z.number().nonnegative(),
})

export const FreeActivitySchema = z.object({
  id: z.string(),
  nom: z.string(),
  type: z.string(),
})
export const PaidActivitySchema = FreeActivitySchema.extend({
  ad: PriceSchema,
  enf: PriceSchema,
  saisons: z.array(VtfSaisonKeySchema).min(1),
})

export const PricingRulesSchema = z.object({
  updatedAt: IsoDateSchema,
  durationCoefficients: z.record(z.string(), z.number().positive()),
  formulaCoefficients: z.object({ PC: z.number().positive(), DP: z.number().positive() }),
  membership: z.object({ individual: PriceSchema, familyOrCouple: PriceSchema }),
  soloSupplementPerNight: z.object({
    default: PriceSchema, reduced: PriceSchema, off: z.literal(0),
  }),
  quinzaineFuteeRate: z.number().min(0).max(1),
  maxiFamilyChildrenRate: z.number().min(0).max(1),
  defaults: z.object({
    activityPriceAdult: PriceSchema, activityPriceChild: PriceSchema,
    mealPriceAdult: PriceSchema, mealPriceChild: PriceSchema,
    locKitPrice: PriceSchema,
    tollPerKm: z.number().nonnegative(), fuelCostPerKm: z.number().nonnegative(),
    trainAdultOneWay: PriceSchema, trainChildOneWay: PriceSchema,
  }),
  childDiscounts: z.object({
    lt1: z.number(), '1to3_withBebeClub': z.number(), '1to3_withoutBebeClub': z.number(),
    '4to5': z.number(), '6to10': z.number(), '11to15': z.number(), ge16: z.number(),
  }),
})

// ─── Endpoint inputs ─────────────────────────────────────────
export const FamilyStateSchema = z.object({
  adultes: z.number().int().min(1).max(6),
  enfants: z.array(z.object({ age: z.number().int().min(0).max(17) })).max(8),
  qfVal: z.number().int().min(0).max(5000).nullable(),
  maxiFamily: z.boolean(),
})

export const SejourInputSchema = z.object({
  dateDebut: IsoDateSchema,
  dateFin: IsoDateSchema,
  formule: VtfFormuleSchema,
  fNuits: z.number().int().min(1).max(31),
  extras: z.object({
    locCleaningFee: z.number().nonnegative().optional(),
    locKits: z.number().int().nonnegative().optional(),
  }).optional(),
  activities: z.object({
    outings: z.number().int().nonnegative().optional(),
    priceAdult: z.number().nonnegative().optional(),
    priceChild: z.number().nonnegative().optional(),
  }).optional(),
  extraActivities: z.object({
    paidQtyById: z.record(z.string(), z.number().int().nonnegative()).optional(),
  }).optional(),
  resto: z.object({
    qtyByMealId: z.record(RestoMealIdSchema, z.number().int().nonnegative()).optional(),
  }).optional(),
  transport: z.object({
    mode: TransportModeSchema,
    distanceOneWayKm: z.number().min(50).max(1200).optional(),
    fuel: FuelKeySchema.optional(),
  }).optional(),
  promos: z.object({
    promoSejourRate: z.number().min(0).max(1).optional(),
    quinzaineFutee: z.boolean().optional(),
    soloSupplementMode: z.enum(['default', 'reduced', 'off']).optional(),
  }).optional(),
})

export const EstimateStayInputSchema = z.object({
  family: FamilyStateSchema,
  sejour: SejourInputSchema,
  villageId: z.string().min(1),
}).refine(
  ({ sejour }) => new Date(sejour.dateFin) > new Date(sejour.dateDebut),
  { message: 'dateFin doit être > dateDebut', path: ['sejour', 'dateFin'] },
)

export const CarCostInputSchema = z.object({
  distanceOneWayKm: z.number().min(0).max(2000),
  fuel: FuelKeySchema,
})

export const TrainCostInputSchema = z.object({
  adults: z.number().int().min(0).max(10),
  children: z.number().int().min(0).max(10),
})

export const RestoTotalInputSchema = z.object({
  qtyByMealId: z.record(RestoMealIdSchema, z.number().int().nonnegative()),
  adults: z.number().int().min(0),
  children: z.number().int().min(0),
})

export const QfInputSchema = z.object({
  netMonthlyIncome: z.number().nonnegative(),
  parts: z.number().min(1).max(20),
})

export const AvailablePromosInputSchema = z.object({
  dateDebut: IsoDateSchema,
  dateFin: IsoDateSchema,
  now: IsoDateSchema.optional(),
})

// ─── Inférences automatiques ─────────────────────────────────
export type EstimateStayInput = z.infer<typeof EstimateStayInputSchema>
export type SejourInput = z.infer<typeof SejourInputSchema>
export type FamilyStateInput = z.infer<typeof FamilyStateSchema>
// ... etc.
```

---

## 7. Guide d'implémentation Django / DRF

> Hypothèse : projet Django ≥ 4.2, **DRF** + **drf-spectacular** (OpenAPI).
> Les mocks JSON deviennent : soit **fixtures** (rechargeables via management command), soit **modèles ORM** (à terme), soit **fichiers statiques** servis tels quels (transition).

### 7.1 Arborescence cible

```
backend/
├── manage.py
├── pyproject.toml
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   └── urls.py
└── apps/
    ├── catalog/                      # Lecture (mocks)
    │   ├── models.py                 # Village, Region, Activity, PricingRules
    │   ├── serializers.py
    │   ├── views.py                  # ReadOnlyModelViewSet
    │   ├── urls.py
    │   ├── fixtures/
    │   │   ├── villages.json         # ← issus de vtfStay.mock.json
    │   │   ├── activities.json
    │   │   └── pricing_rules.json
    │   └── management/commands/
    │       └── load_vtf_mocks.py     # `python manage.py load_vtf_mocks`
    └── pricing/                      # Calcul (utils)
        ├── services/
        │   ├── stay_estimate.py      # port stayEstimate.ts
        │   ├── promos.py             # port promosTab.ts
        │   ├── transport.py          # port transportTab.ts
        │   ├── resto.py              # port restoTab.ts
        │   ├── qf.py                 # port qfCalc.ts
        │   └── hotel.py              # port viewDetails.ts
        ├── serializers.py            # input/output DRF
        ├── views.py                  # APIView (POST)
        └── urls.py
```

### 7.2 Modèle ORM minimal — `apps/catalog/models.py`

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
    PC = "PC"
    DP = "DP"
    LOC = "LOC"


class Village(models.Model):
    id = models.SlugField(primary_key=True, max_length=64)
    nom = models.CharField(max_length=128)
    nom2 = models.CharField(max_length=128, blank=True)
    region = models.CharField(max_length=64, choices=Region.choices)
    env = models.CharField(max_length=8)  # emoji
    formules = models.JSONField()         # ['PC','DP','LOC']
    has_loc = models.BooleanField()
    ski = models.BooleanField()
    ouverture = models.CharField(max_length=256, blank=True)
    tarifs = models.JSONField()           # { PC: {hs,vs,ete,fetes}, LOC: ... }
    bebe_club = models.BooleanField(default=False)
    forfait_rm = models.BooleanField(default=False)
    qf_exc = models.BooleanField(default=False)
    enf_solo_half = models.BooleanField(default=False)

    class Meta:
        ordering = ["region", "nom"]

    def __str__(self) -> str:
        return self.nom


class Attraction(models.Model):
    village = models.ForeignKey(Village, on_delete=models.CASCADE, related_name="attractions")
    nom = models.CharField(max_length=128)
    type = models.CharField(max_length=128)
    icon = models.CharField(max_length=8)
    km = models.PositiveSmallIntegerField()


class Activity(models.Model):
    KIND_FREE = "free"
    KIND_PAID = "paid"
    KIND_CHOICES = [(KIND_FREE, "Gratuite"), (KIND_PAID, "Payante")]

    code = models.CharField(max_length=64, unique=True)  # ex: "paid:al:surf"
    region = models.CharField(max_length=64, choices=Region.choices)
    kind = models.CharField(max_length=4, choices=KIND_CHOICES)
    nom = models.CharField(max_length=128)
    type = models.CharField(max_length=8)  # emoji
    price_adult = models.PositiveSmallIntegerField(default=0)
    price_child = models.PositiveSmallIntegerField(default=0)
    saisons = models.JSONField(default=list)  # ['hs','vs',...]


class PricingRules(models.Model):
    """Singleton (1 seule ligne)."""
    updated_at = models.DateField()
    payload = models.JSONField()  # tout le JSON tel quel
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"], condition=models.Q(is_active=True),
                name="unique_active_pricing_rules",
            ),
        ]
```

### 7.3 Management command — `load_vtf_mocks.py`

```python
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Activity, Attraction, PricingRules, Village

MOCKS_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"


class Command(BaseCommand):
    help = "Charge les mocks VTF depuis src/mocks/*.json (front)."

    def add_arguments(self, parser):
        parser.add_argument("--src", type=str, required=True,
                            help="Chemin vers le dossier src/mocks du front.")

    @transaction.atomic
    def handle(self, *args, src: str, **opts):
        root = Path(src)
        stay = json.loads((root / "vtfStay.mock.json").read_text(encoding="utf-8"))
        extras = json.loads((root / "vtfExtras.mock.json").read_text(encoding="utf-8"))
        rules = json.loads((root / "vtfPricingRules.mock.json").read_text(encoding="utf-8"))

        # Villages
        Village.objects.all().delete()
        for v in stay["villages"]:
            Village.objects.create(
                id=v["id"],
                nom=v["nom"],
                nom2=v.get("nom2", ""),
                region=v["region"],
                env=v["env"],
                formules=v["formules"],
                has_loc=v["hasLoc"],
                ski=v["ski"],
                ouverture=v.get("ouverture", ""),
                tarifs=v["tarifs"],
                bebe_club=v.get("bebeClub", False),
                forfait_rm=v.get("forfaitRM", False),
                qf_exc=v.get("qfExc", False),
                enf_solo_half=v.get("enfSoloHalf", False),
            )

        # Attractions (clé = nom du village, à mapper sur l'id)
        Attraction.objects.all().delete()
        nom_to_id = {v.nom: v.id for v in Village.objects.all()}
        for nom_village, atts in stay["attractionsProches"].items():
            village_id = nom_to_id.get(nom_village)
            if not village_id:
                self.stdout.write(self.style.WARNING(f"Skip attraction sans village: {nom_village}"))
                continue
            for a in atts:
                Attraction.objects.create(village_id=village_id, **a)

        # Activities
        Activity.objects.all().delete()
        for region, acts in extras["actGratuit"].items():
            for a in acts:
                Activity.objects.create(
                    code=a["id"], region=region, kind=Activity.KIND_FREE,
                    nom=a["nom"], type=a["type"],
                )
        for region, acts in extras["activitesPayantes"].items():
            for a in acts:
                Activity.objects.create(
                    code=a["id"], region=region, kind=Activity.KIND_PAID,
                    nom=a["nom"], type=a["type"],
                    price_adult=a["ad"], price_child=a["enf"],
                    saisons=a["saisons"],
                )

        # Pricing rules (singleton actif)
        PricingRules.objects.filter(is_active=True).update(is_active=False)
        PricingRules.objects.create(
            updated_at=rules["updatedAt"], payload=rules, is_active=True,
        )

        self.stdout.write(self.style.SUCCESS("Mocks VTF chargés."))
```

### 7.4 Sérialiseurs — `apps/catalog/serializers.py`

```python
from rest_framework import serializers
from .models import Activity, Attraction, PricingRules, Village


class AttractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attraction
        fields = ["nom", "type", "icon", "km"]


class VillageListSerializer(serializers.ModelSerializer):
    hasLoc = serializers.BooleanField(source="has_loc")

    class Meta:
        model = Village
        fields = ["id", "nom", "nom2", "region", "env", "formules", "hasLoc", "ski", "ouverture"]


class VillageDetailSerializer(serializers.ModelSerializer):
    hasLoc = serializers.BooleanField(source="has_loc")
    bebeClub = serializers.BooleanField(source="bebe_club")
    forfaitRM = serializers.BooleanField(source="forfait_rm")
    qfExc = serializers.BooleanField(source="qf_exc")
    enfSoloHalf = serializers.BooleanField(source="enf_solo_half")
    attractions = AttractionSerializer(many=True, read_only=True)

    class Meta:
        model = Village
        fields = [
            "id", "nom", "nom2", "region", "env", "formules", "hasLoc", "ski",
            "ouverture", "tarifs", "bebeClub", "forfaitRM", "qfExc", "enfSoloHalf",
            "attractions",
        ]


class ActivitySerializer(serializers.ModelSerializer):
    ad = serializers.IntegerField(source="price_adult")
    enf = serializers.IntegerField(source="price_child")

    class Meta:
        model = Activity
        fields = ["code", "region", "kind", "nom", "type", "ad", "enf", "saisons"]


class PricingRulesSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingRules
        fields = ["updated_at", "payload"]
```

### 7.5 Sérialiseurs d'inputs (calcul) — `apps/pricing/serializers.py`

```python
from rest_framework import serializers


class EnfantSerializer(serializers.Serializer):
    age = serializers.IntegerField(min_value=0, max_value=17)


class FamilySerializer(serializers.Serializer):
    adultes = serializers.IntegerField(min_value=1, max_value=6)
    enfants = EnfantSerializer(many=True, max_length=8)
    qfVal = serializers.IntegerField(min_value=0, max_value=5000, allow_null=True)
    maxiFamily = serializers.BooleanField()


class SejourSerializer(serializers.Serializer):
    dateDebut = serializers.DateField()
    dateFin = serializers.DateField()
    formule = serializers.ChoiceField(choices=["PC", "DP", "LOC"])
    fNuits = serializers.IntegerField(min_value=1, max_value=31)
    extras = serializers.DictField(required=False)
    activities = serializers.DictField(required=False)
    extraActivities = serializers.DictField(required=False)
    resto = serializers.DictField(required=False)
    transport = serializers.DictField(required=False)
    promos = serializers.DictField(required=False)

    def validate(self, attrs):
        if attrs["dateFin"] <= attrs["dateDebut"]:
            raise serializers.ValidationError({"dateFin": "doit être > dateDebut"})
        return attrs


class EstimateStayInputSerializer(serializers.Serializer):
    family = FamilySerializer()
    sejour = SejourSerializer()
    villageId = serializers.SlugField()


class CarCostInputSerializer(serializers.Serializer):
    distanceOneWayKm = serializers.FloatField(min_value=0, max_value=2000)
    fuel = serializers.ChoiceField(choices=["essence", "diesel", "electrique"])


class TrainCostInputSerializer(serializers.Serializer):
    adults = serializers.IntegerField(min_value=0, max_value=10)
    children = serializers.IntegerField(min_value=0, max_value=10)


class QfInputSerializer(serializers.Serializer):
    netMonthlyIncome = serializers.FloatField(min_value=0)
    parts = serializers.FloatField(min_value=1, max_value=20)
```

### 7.6 Service de calcul — `apps/pricing/services/stay_estimate.py`

> **Stratégie** : porter `stayEstimate.ts` ligne-à-ligne vers du Python pur, en passant `pricing_rules` (dict) en paramètre pour rester testable.

```python
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Optional, TypedDict

SaisonKey = Literal["hs", "vs", "ete", "fetes"]


def date_to_saison_idx(d: date) -> int:
    m, j = d.month, d.day
    jj = m * 100 + j
    if 628 <= jj <= 901:
        return 2
    if jj >= 1220 or jj <= 106:
        return 3
    if (m == 2 and j >= 15) or (m == 3 and j <= 3):
        return 1
    if (m == 4 and j >= 12) or (m == 5 and j <= 4):
        return 1
    if (m == 10 and j >= 19) or (m == 11 and j <= 2):
        return 1
    return 0


SAISON_KEYS: list[SaisonKey] = ["hs", "vs", "ete", "fetes"]


def child_discount_fraction(age: int, bebe_club: bool, rules: dict) -> float:
    cd = rules["childDiscounts"]
    if age < 1: return cd["lt1"]
    if age < 4: return cd["1to3_withBebeClub"] if bebe_club else cd["1to3_withoutBebeClub"]
    if age < 6: return cd["4to5"]
    if age < 11: return cd["6to10"]
    if age < 16: return cd["11to15"]
    return cd["ge16"]


def qf_rate(qf_val: Optional[int], qf_exc: bool, qf_seuil_bas: int = 880, qf_seuil_haut: int = 1350) -> float:
    if qf_val is None:
        return 0.0
    if qf_val < qf_seuil_bas:
        return 0.10 if qf_exc else 0.17
    if qf_val < qf_seuil_haut:
        return 0.05 if qf_exc else 0.10
    return 0.0


def duration_coef(nuits: int, rules: dict) -> float:
    exact = rules["durationCoefficients"].get(str(nuits))
    if isinstance(exact, (int, float)) and exact > 0:
        return float(exact)
    return nuits / 7


@dataclass
class SejourEstimate:
    total: int
    per_person: int
    total_adults: int
    total_children: int
    per_adult_base: int
    saison_key: SaisonKey
    nuits: int
    discount_rate: float
    stay_subtotal: int
    adhesion: int
    solo_supplement: int
    extras_loc: int
    activities_total: int
    resto_total: int
    transport_total: int
    hotel_estimate: int
    hotel_savings: int
    savings_pct: float


def estimate_sejour_total(
    *, family: dict, sejour: dict, village: dict, pricing_rules: dict,
) -> Optional[SejourEstimate]:
    """Port de stayEstimate.ts:estimateSejourTotal()."""
    d_start = date.fromisoformat(sejour["dateDebut"])
    d_end = date.fromisoformat(sejour["dateFin"])
    nuits = (d_end - d_start).days
    if nuits < 1:
        return None

    saison_key = SAISON_KEYS[date_to_saison_idx(d_start)]
    coef = duration_coef(nuits, pricing_rules)

    base_pc = (village["tarifs"].get("PC") or {}).get(saison_key, 0)
    base_loc = (village["tarifs"].get("LOC") or {}).get(saison_key, 0)
    base = base_loc if sejour["formule"] == "LOC" else base_pc
    if not base:
        return None

    pb = base * coef
    if sejour["formule"] != "LOC":
        pb *= pricing_rules["formulaCoefficients"].get(sejour["formule"], 1)

    qf = qf_rate(family.get("qfVal"), bool(village.get("qfExc")))
    promo = max(0.0, min(1.0, sejour.get("promos", {}).get("promoSejourRate", 0)))
    quinzaine = (
        pricing_rules.get("quinzaineFuteeRate", 0.10)
        if sejour.get("promos", {}).get("quinzaineFutee")
        and sejour["formule"] == "PC"
        and sejour["fNuits"] >= 14
        else 0.0
    )
    discount_rate = 1 - (1 - qf) * (1 - promo) * (1 - quinzaine)
    pb_after = pb * (1 - discount_rate)

    bebe_club = bool(village.get("bebeClub"))
    total_adults = pb_after * family["adultes"]
    maxi_factor = (
        1 - max(0.0, min(1.0, pricing_rules.get("maxiFamilyChildrenRate", 0.2)))
        if family.get("maxiFamily") and len(family["enfants"]) >= 3 else 1
    )
    total_children = sum(
        pb_after * (1 - child_discount_fraction(c["age"], bebe_club, pricing_rules)) * maxi_factor
        for c in family["enfants"]
    )

    # ... (suite : solo supplement, adhesion, extras LOC, activities, resto, transport, hotel)
    # ... (idem stayEstimate.ts:175-251)
    raise NotImplementedError("Cf. stayEstimate.ts:175-251 pour la suite à porter.")
```

### 7.7 Vues — `apps/pricing/views.py`

```python
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from apps.catalog.models import PricingRules, Village
from .serializers import (
    EstimateStayInputSerializer, CarCostInputSerializer,
    TrainCostInputSerializer, QfInputSerializer,
)
from .services import stay_estimate, transport, qf


class EstimateStayView(APIView):
    """POST /api/v1/estimate/stay"""

    def post(self, request):
        ser = EstimateStayInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            village = Village.objects.values().get(pk=data["villageId"])
        except Village.DoesNotExist:
            return Response({"detail": "village inconnu"}, status=status.HTTP_404_NOT_FOUND)

        rules = PricingRules.objects.filter(is_active=True).values_list("payload", flat=True).first()
        if not rules:
            return Response({"detail": "pricing rules non chargées"}, status=500)

        est = stay_estimate.estimate_sejour_total(
            family=data["family"], sejour=data["sejour"],
            village=village, pricing_rules=rules,
        )
        if est is None:
            return Response({"detail": "estimation impossible"}, status=400)
        return Response(est.__dict__)


class CarCostView(APIView):
    def post(self, request):
        ser = CarCostInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(transport.car_cost_breakdown(**ser.validated_data))


class TrainCostView(APIView):
    def post(self, request):
        ser = TrainCostInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response({"total": transport.train_total(**ser.validated_data)})


class QfView(APIView):
    def post(self, request):
        ser = QfInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(qf.calc_qf_from_income_parts(**ser.validated_data))
```

### 7.8 URLs — `config/urls.py`

```python
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.catalog.views import VillageViewSet, ActivityViewSet, PricingRulesView
from apps.pricing.views import (
    EstimateStayView, CarCostView, TrainCostView, QfView,
)

router = DefaultRouter()
router.register(r"villages", VillageViewSet)
router.register(r"activities", ActivityViewSet)

urlpatterns = [
    path("api/v1/", include([
        *router.urls,
        path("pricing-rules/", PricingRulesView.as_view()),
        path("estimate/stay/", EstimateStayView.as_view()),
        path("transport/car/", CarCostView.as_view()),
        path("transport/train/", TrainCostView.as_view()),
        path("family/qf/", QfView.as_view()),
    ])),
]
```

### 7.9 Tests — patterns recommandés

```python
# apps/pricing/tests/test_stay_estimate.py
import pytest
from apps.pricing.services.stay_estimate import estimate_sejour_total


@pytest.fixture
def pricing_rules():
    # Charger une fois depuis fixtures
    import json, pathlib
    return json.loads((pathlib.Path(__file__).parent / "fixtures/pricing_rules.json").read_text())


def test_basic_pc_summer(pricing_rules):
    village = {
        "id": "biarritz", "region": "Aquitaine / Landes",
        "tarifs": {"PC": {"hs": 520, "vs": 595, "ete": 630, "fetes": 610}},
        "qfExc": False, "bebeClub": True,
    }
    family = {"adultes": 2, "enfants": [{"age": 4}, {"age": 8}], "qfVal": 1000, "maxiFamily": False}
    sejour = {
        "dateDebut": "2026-07-05", "dateFin": "2026-07-12",
        "formule": "PC", "fNuits": 7, "promos": {}, "transport": {"mode": "onSite"},
    }
    est = estimate_sejour_total(
        family=family, sejour=sejour, village=village, pricing_rules=pricing_rules,
    )
    assert est is not None
    assert est.saison_key == "ete"
    assert est.nuits == 7
    assert est.total > 0
```

> 🎯 **Discipline** : porter avec un test de **golden master** (snapshot). Capturer les sorties JS actuelles sur 10–20 cas, les sauver en JSON, et asserter l'équivalence côté Python.

### 7.10 OpenAPI

```python
# settings/base.py
INSTALLED_APPS += ["drf_spectacular"]
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "VTF Customer Simulators API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# urls.py
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
urlpatterns += [
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
]
```

### 7.11 Caching & perf

| Endpoint                            | Cache strategy                                    |
|-------------------------------------|---------------------------------------------------|
| `GET /villages*`                    | `@method_decorator(cache_page(60*60*24))` + ETag  |
| `GET /pricing-rules`                | idem + invalider au load des mocks                |
| `POST /estimate/stay`               | pas de cache server (idempotent mais body riche) — éventuel cache CDN par hash de body |
| `POST /transport/*`, `/family/qf`   | idem                                              |

---

## 8. Recommandations de migration

### 8.1 Ordre conseillé

1. **Geler les mocks** (versionner avec `updatedAt` partout, tagger `vtf-data-2026-1`)
2. **Étape 1 — API lecture seule** : exposer `/villages`, `/regions`, `/activities`, `/pricing-rules` (mocks → DB ou statique)
3. **Étape 2 — API calcul** : porter `transport`, `qf`, `resto`, `hotel`, `promos` (purs, faciles à valider via golden master)
4. **Étape 3 — `/estimate/stay`** : porter `stayEstimate.ts` (cœur métier, prioriser tests snapshot)
5. **Étape 4 — Front** : remplacer les imports `data/*.ts` par un client typé (généré depuis OpenAPI ou écrit à la main)

### 8.2 À nettoyer **avant** l'export

- [ ] Dédupliquer la logique hôtel (`viewDetails.ts` ↔ `stayEstimate.ts:265-275`)
- [ ] Dédupliquer `clampInt` (3 implémentations)
- [ ] Compléter `vtfInfra` et `vtfClubsEte` (un seul village renseigné)
- [ ] Mapper les attractions par `villageId` (pas par `nom`)
- [ ] Sortir les libellés français de `getHighlights()` (i18n)
- [ ] Normaliser `env` : passer d'emoji string à `enum` côté API (`'sea' | 'mountain' | ...`) tout en gardant l'icône en metadata
- [ ] Parser `ouverture` côté backend (logique actuellement dans `parseOuverture()`)
- [ ] Fixer le nom de clé `'1to3_withBebeClub'` → `with_bebe_club_1_to_3` (Python-friendly)

### 8.3 Ce qui ne doit **pas** partir en API

- `getQfBadgeKind` → présentation
- `euro`, `euroCompact`, `formatEuroEn`, `seasonLabelFromFunnelKey` → présentation/i18n
- `FAMILY_TAB_LIMITS`, `DEFAULT_NEW_CHILD_AGE`, `FAMILY_AGE_OPTIONS` → contraintes UI
- `emptyDaySlots`, `countPlanningItems` → state UI
- `patchPromos` → mutation de state
- `CAF_ATTESTATION_URL` → constante UI

### 8.4 Risques connus

| Risque                                    | Impact     | Mitigation                                             |
|-------------------------------------------|------------|--------------------------------------------------------|
| Divergence calcul JS ↔ Python             | Élevé      | Tests golden master + CI bi-runtime                    |
| `Date` → fuseau horaire (UTC vs local)    | Moyen      | Toujours travailler en `date` (pas `datetime`) ISO     |
| Arrondis (`Math.round` vs `round()`)      | Faible     | Documenter la stratégie d'arrondi (banking vs half-up) |
| Mocks figés vs prod VTF                   | Élevé      | Pipeline de sync depuis source de vérité VTF           |
| Régressions front si l'API renomme        | Moyen      | Conserver les noms camelCase en sortie (Serializer)    |

---

**FIN DE L'AUDIT**
