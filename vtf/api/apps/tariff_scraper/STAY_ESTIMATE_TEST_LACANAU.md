# Stay-Estimate API Test Matrix — Lacanau (18–25 Jul 2026)

## Overview

- **API Endpoint:** `POST /api/v1/estimate/stay`
- **Village:** `lacanau` (La Forestière)
- **Test Dates:** 18 Jul – 25 Jul 2026 (7 nights)
- **Season Key:** `ete` (summer)
- **Tariff Source:** `VillageTarif` (scraped from VTF grille, NOT the static `Village.tarifs` fixture)

---

## Tariff Source Explanation

The stay-estimate engine resolves pricing in two tiers:

1. **Primary:** `VillageTarif` rows (live scraped data from the VTF grille)
2. **Fallback:** `Village.tarifs` JSON fixture (only when no VillageTarif row exists)

For Lacanau with an approved scrape, the API uses **VillageTarif** (scraped grille prices).

### Scraped Prices (VillageTarif) for Lacanau

| Band | Dates | PC (regular) | DP (regular) | Source |
|---|---|---|---|---|
| Paques | 11/04 – 02/05 | 469 | 398.65 | Grille |
| Hors vacances | 02/05 – 04/07 | 581 | 493.85 | Grille |
| Ete low | 04/07 – 11/07 | 728 | 618.80 | Grille |
| **Ete mid** | **11/07 – 25/07** | **903** | **767.55** | **Grille** |
| Ete peak | 25/07 – 15/08 | 945 | 803.25 | Grille |
| Ete mid | 15/08 – 22/08 | 903 | 767.55 | Grille |
| Ete low | 22/08 – 29/08 | 728 | 618.80 | Grille |
| Hors vacances | 29/08 – 03/10 | 581 | 493.85 | Grille |
| Toussaint | 17/10 – 01/11 | 455 | 386.75 | Grille |

> **Note:** DP is derived from PC × 0.85 (15% remise). VTF widget may show slightly different regular DP prices (e.g. 770 vs 767.55).

---

## VTF-Vacances Website Comparison (18–25 Jul 2026)

| Formula | VTF Regular (crossed out) | VTF Promo | Discount |
|---|---|---|---|
| PC (Pension complète) | ~~903,00 €~~ | **632,10 €** | 30% off |
| DP (Demi-pension) | ~~770,00 €~~ | **539,00 €** | ~30% off |

---

## Pricing Rules

| Rule | Value |
|---|---|
| Duration coefficients | 3n=0.5, 7n=1.0, 11n=1.45, 14n=1.8 |
| Formula coefficients | PC=1.0, DP=0.82 |
| Child discounts | <1: free, 1-2 (no bebe club): 90%, 3-5: 40%, 6-10: 20%, 11-15: 10%, 16+: 0% |
| Membership | Individual=22€, Family=44€ |
| Solo supplement | 22€/night (default) |
| Quinzaine futée | 10% off (PC, ≥14 nights) |
| MaxiFamily children rate | 20% off child rates (3+ children) |

---

## Test Cases

### Case 1: 1 Adult, PC (no promo)

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 1,
    "enfants": []
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "PC"
  }
}
```

**Expected Response:**
```json
{
  "total": 925,
  "perPerson": 925,
  "totalAdults": 903,
  "totalChildren": 0,
  "perAdultBase": 903,
  "childLines": [],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0,
  "staySubtotal": 903,
  "adhesion": 22,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

---

### Case 2: 1 Adult, DP (no promo)

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 1,
    "enfants": []
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "DP"
  }
}
```

**Expected Response:**
```json
{
  "total": 790,
  "perPerson": 790,
  "totalAdults": 768,
  "totalChildren": 0,
  "perAdultBase": 768,
  "childLines": [],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0,
  "staySubtotal": 768,
  "adhesion": 22,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

> **Note:** VTF widget shows regular DP as 770 € (vs scraped 767.55). Small gap due to scraper using flat 15% formula.

---

### Case 3: 2 Adults, PC

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 2,
    "enfants": []
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "PC"
  }
}
```

**Expected Response:**
```json
{
  "total": 1850,
  "perPerson": 925,
  "totalAdults": 1806,
  "totalChildren": 0,
  "perAdultBase": 903,
  "childLines": [],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0,
  "staySubtotal": 1806,
  "adhesion": 44,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

---

### Case 4: 2 Adults, DP

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 2,
    "enfants": []
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "DP"
  }
}
```

**Expected Response:**
```json
{
  "total": 1579,
  "perPerson": 790,
  "totalAdults": 1535,
  "totalChildren": 0,
  "perAdultBase": 768,
  "childLines": [],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0,
  "staySubtotal": 1535,
  "adhesion": 44,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

---

### Case 5: 2 Adults + 2 Children (age 3, age 8), PC

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 2,
    "enfants": [
      {"age": 3},
      {"age": 8}
    ]
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "PC"
  }
}
```

**Expected Response:**
```json
{
  "total": 3114,
  "perPerson": 1038,
  "totalAdults": 1806,
  "totalChildren": 1264,
  "perAdultBase": 903,
  "childLines": [
    {"age": 3, "discountFraction": 0.4, "amount": 542},
    {"age": 8, "discountFraction": 0.2, "amount": 722}
  ],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0,
  "staySubtotal": 3070,
  "adhesion": 44,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

**Child calculation:**
- Child age 3: 903 × (1 - 0.40) = 903 × 0.60 = 542
- Child age 8: 903 × (1 - 0.20) = 903 × 0.80 = 722

---

### Case 6: QF 700 (17% discount), 2 Adults, PC

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 2,
    "enfants": [],
    "qfVal": 700
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "PC"
  }
}
```

**Expected Response:**
```json
{
  "total": 1536,
  "perPerson": 768,
  "totalAdults": 1499,
  "totalChildren": 0,
  "perAdultBase": 749,
  "childLines": [],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0.17,
  "staySubtotal": 1499,
  "adhesion": 37,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

**Calculation:**
- QF 700 < 880 → 17% discount (Lacanau qfExc=false)
- pb = 903 × 1.0 × 1.0 = 903
- pb_after = 903 × (1 - 0.17) = 749
- stay = 749 × 2 = 1499
- adhesion = 44 × (1 - 0.17) = 37

---

### Case 7: QF 900 (10% discount), 2 Adults, PC

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 2,
    "enfants": [],
    "qfVal": 900
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "PC"
  }
}
```

**Expected Response:**
```json
{
  "total": 1665,
  "perPerson": 833,
  "totalAdults": 1625,
  "totalChildren": 0,
  "perAdultBase": 813,
  "childLines": [],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0.1,
  "staySubtotal": 1625,
  "adhesion": 40,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

**Calculation:**
- QF 900 (880–1350) → 10% discount
- pb_after = 903 × 0.90 = 813
- stay = 813 × 2 = 1625
- adhesion = 44 × 0.90 = 40

---

### Case 8: QF 1500 (no discount), 2 Adults, PC

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 2,
    "enfants": [],
    "qfVal": 1500
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "PC"
  }
}
```

**Expected Response:**
```json
{
  "total": 1850,
  "perPerson": 925,
  "totalAdults": 1806,
  "totalChildren": 0,
  "perAdultBase": 903,
  "childLines": [],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0,
  "staySubtotal": 1806,
  "adhesion": 44,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

---

### Case 9: Promo 30% (matching VTF promo), 1 Adult, PC

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 1,
    "enfants": []
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "PC",
    "promos": {
      "promoSejourRate": 0.30
    }
  }
}
```

**Expected Response:**
```json
{
  "total": 647,
  "perPerson": 647,
  "totalAdults": 632,
  "totalChildren": 0,
  "perAdultBase": 632,
  "childLines": [],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0.3,
  "staySubtotal": 632,
  "adhesion": 15,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

**Calculation:**
- pb_after = 903 × (1 - 0.30) = 632
- adhesion = 22 × (1 - 0.30) = 15
- **Matches VTF promo price: 632,10 €**

---

### Case 10: Promo 30% (matching VTF promo), 1 Adult, DP

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 1,
    "enfants": []
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "DP",
    "promos": {
      "promoSejourRate": 0.30
    }
  }
}
```

**Expected Response:**
```json
{
  "total": 554,
  "perPerson": 554,
  "totalAdults": 538,
  "totalChildren": 0,
  "perAdultBase": 538,
  "childLines": [],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0.3,
  "staySubtotal": 538,
  "adhesion": 15,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

**Calculation:**
- pb_after = 768 × (1 - 0.30) = 538
- adhesion = 22 × (1 - 0.30) = 15
- **Close to VTF promo DP: 539 €** (small gap due to 768 vs 770 regular price)

---

### Case 11: 2 Adults + Car 600km, PC

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 2,
    "enfants": []
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "PC",
    "transport": {
      "mode": "car",
      "distanceOneWayKm": 600
    }
  }
}
```

**Expected Response:**
```json
{
  "total": 2078,
  "perPerson": 1039,
  "totalAdults": 1806,
  "totalChildren": 0,
  "perAdultBase": 903,
  "childLines": [],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0,
  "staySubtotal": 1806,
  "adhesion": 44,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 272
}
```

---

### Case 12: 2 Adults + Train, PC

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 2,
    "enfants": []
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "PC",
    "transport": {
      "mode": "train"
    }
  }
}
```

**Expected Response:**
```json
{
  "total": 2110,
  "perPerson": 1055,
  "totalAdults": 1806,
  "totalChildren": 0,
  "perAdultBase": 903,
  "childLines": [],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0,
  "staySubtotal": 1806,
  "adhesion": 44,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 300
}
```

---

### Case 13: Family + QF 900 + Promo 10%, PC

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 2,
    "enfants": [
      {"age": 3},
      {"age": 8}
    ],
    "qfVal": 900
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "PC",
    "promos": {
      "promoSejourRate": 0.10
    }
  }
}
```

**Expected Response:**
```json
{
  "total": 2523,
  "perPerson": 841,
  "totalAdults": 1462,
  "totalChildren": 1025,
  "perAdultBase": 731,
  "childLines": [
    {"age": 3, "discountFraction": 0.4, "amount": 438},
    {"age": 8, "discountFraction": 0.2, "amount": 585}
  ],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0.19,
  "staySubtotal": 2487,
  "adhesion": 36,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

**Calculation:**
- Combined discount: 1 - (1 - 0.10) × (1 - 0.10) = 1 - 0.81 = 0.19
- pb_after = 903 × 0.81 = 731
- stay = 731 × 2 + child_discounts = 2487
- adhesion = 44 × 0.81 = 36

---

### Case 14: MaxiFamily (3 children), 2 Adults, PC

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 2,
    "enfants": [
      {"age": 2},
      {"age": 5},
      {"age": 10}
    ],
    "maxiFamily": true
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "PC"
  }
}
```

**Expected Response:**
```json
{
  "total": 3439,
  "perPerson": 860,
  "totalAdults": 1806,
  "totalChildren": 1589,
  "perAdultBase": 903,
  "childLines": [
    {"age": 2, "discountFraction": 0.9, "amount": 72},
    {"age": 5, "discountFraction": 0.4, "amount": 434},
    {"age": 10, "discountFraction": 0.2, "amount": 578}
  ],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0,
  "staySubtotal": 3395,
  "adhesion": 44,
  "soloSupplement": 0,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

**Calculation:**
- MaxiFamily factor = 1 - 0.20 = 0.80 (applied to child costs)
- Child age 2: 903 × (1 - 0.90) × 0.80 = 72
- Child age 5: 903 × (1 - 0.40) × 0.80 = 434
- Child age 10: 903 × (1 - 0.20) × 0.80 = 578

---

### Case 15: Solo Parent (1 adult + 1 child age 5), PC

**Payload:**
```json
{
  "villageId": "lacanau",
  "family": {
    "adultes": 1,
    "enfants": [
      {"age": 5}
    ],
    "isSoloParent": true
  },
  "sejour": {
    "dateDebut": "2026-07-18",
    "dateFin": "2026-07-25",
    "formule": "PC"
  }
}
```

**Expected Response:**
```json
{
  "total": 1823,
  "perPerson": 912,
  "totalAdults": 903,
  "totalChildren": 876,
  "perAdultBase": 903,
  "childLines": [
    {"age": 5, "discountFraction": 0.4, "amount": 542}
  ],
  "saisonKey": "ete",
  "nuits": 7,
  "discountRate": 0,
  "staySubtotal": 1779,
  "adhesion": 22,
  "soloSupplement": 154,
  "extrasLoc": 0,
  "activitiesTotal": 0,
  "restoTotal": 0,
  "transportTotal": 0
}
```

**Calculation:**
- Solo supplement: 22€/night × 7 nights = 154
- stay = 903 + 542 + 154 = 1599
- adhesion = 22

---

## Summary Table

| # | Case | Formule | Promo | perAdultBase | Adhesion | Total |
|---|---|---|---|---|---|---|
| 1 | 1 adult | PC | — | 903 | 22 | **925** |
| 2 | 1 adult | DP | — | 768 | 22 | **790** |
| 3 | 2 adults | PC | — | 903 | 44 | **1850** |
| 4 | 2 adults | DP | — | 768 | 44 | **1579** |
| 5 | 2ad + 2enf (3,8) | PC | — | 903 | 44 | **3114** |
| 6 | QF 700 | PC | — | 749 | 37 | **1536** |
| 7 | QF 900 | PC | — | 813 | 40 | **1665** |
| 8 | QF 1500 | PC | — | 903 | 44 | **1850** |
| 9 | 1 adult | PC | 30% | 632 | 15 | **647** |
| 10 | 1 adult | DP | 30% | 538 | 15 | **554** |
| 11 | + Car 600km | PC | — | 903 | 44 | **2078** |
| 12 | + Train | PC | — | 903 | 44 | **2110** |
| 13 | Family+QF900+Promo10% | PC | 10% | 731 | 36 | **2523** |
| 14 | MaxiFamily 3kids | PC | — | 903 | 44 | **3439** |
| 15 | Solo Parent | PC | — | 903 | 22 | **1823** |

---

## VTF vs API Comparison (18–25 Jul 2026)

| Formula | VTF Regular | API (no promo) | VTF Promo (30%) | API (promo 30%) | Match? |
|---|---|---|---|---|---|
| PC | 903 € | 903 | 632,10 € | 632 | ✅ |
| DP | 770 € | 768 | 539 € | 538 | ⚠️ (2€ gap) |

> **DP gap explained:** Scraper derives DP as PC × 0.85 = 767.55. VTF widget shows 770 as regular DP. The 2.45€ difference is because VTF's actual DP pricing is not exactly 15% off PC for this band.

---

## Key Notes

1. **Tariff Source:** API uses `VillageTarif` (scraped grille data), NOT `Village.tarifs` fixture
2. **Promo prices:** Not scraped — frontend must pass `promoSejourRate` to match VTF promo pricing
3. **Adhesion:** Automatically added (22€ individual, 44€ family), discounted with QF/promo
4. **DP regular price:** Scraper uses flat 15% formula; VTF widget may show slightly different values
5. **Season key:** 18 Jul → `ete` (summer), covers all summer sub-tiers with VillageTarif date bands
