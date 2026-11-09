#!/usr/bin/env node
/**
 * generate_js_golden_master.mjs
 * ------------------------------------------------------------------
 * AC-1.3 — Golden Master generator (JS oracle ↔ Python parity).
 *
 * `vtf/front/src/utils/stayEstimate.ts` no longer contains a calculable
 * `estimateSejourTotal()` — the calculation logic now lives only in
 * `vtf/api/apps/pricing/services/stay_estimate.py` (the frontend calls
 * `POST /api/v1/estimate/stay` and renders whatever the API returns).
 *
 * This script is therefore a *self-contained* JS re-implementation of
 * that Python service, used purely as an independent oracle: it is a
 * line-for-line port of `stay_estimate.py` (same branches, same
 * rounding, same field names) so that `golden_cases_js.json` encodes
 * "what the service is supposed to produce" from a second, independent
 * codebase — not a copy of the Python output itself.
 *
 * IMPORTANT — keep this in sync with stay_estimate.py whenever that
 * file changes. In particular this currently mirrors the *seasonal QF
 * gate* exactly as shipped (summer always allowed; winter allowed only
 * inside the rolled "hiver" marketing-season window AND only once
 * sales are open on 10 June) — do not "simplify" that gate without
 * checking with the client first, it is intentional business logic.
 *
 * Because that gate depends on `today()`, this script accepts a
 * `--today YYYY-MM-DD` override so regenerating the fixture produces
 * reproducible output regardless of which day it's run on. Without
 * the flag it falls back to the real current date, same as Python.
 *
 * USAGE (from vtf/front/):
 *
 *   npx tsx generate_js_golden_master.mjs --out ../api/tests/golden_cases_js.json
 *   npx tsx generate_js_golden_master.mjs --villages biarritz,agde,chamonix --out ../api/tests/golden_cases_js.json
 *   npx tsx generate_js_golden_master.mjs --today 2026-06-25 --out ../api/tests/golden_cases_js.json
 *
 * Plain `node generate_js_golden_master.mjs ...` also works — this file
 * has no TypeScript syntax, tsx is only used for parity with the docs.
 * ------------------------------------------------------------------
 */

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

// ── CLI args ────────────────────────────────────────────────────────────────

function parseArgs(argv) {
  const out = { out: "../api/tests/golden_cases_js.json", villages: null, today: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--out") out.out = argv[++i];
    else if (a === "--villages") out.villages = argv[++i];
    else if (a === "--today") out.today = argv[++i];
  }
  return out;
}

const args = parseArgs(process.argv.slice(2));

// ── Fixture loading (mirrors apps/catalog/fixtures/*.json) ─────────────────

const FIXTURE_DIR = resolve(__dirname, "../api/apps/catalog/fixtures");

function loadJson(relPath) {
  return JSON.parse(readFileSync(resolve(FIXTURE_DIR, relPath), "utf-8"));
}

const villageFixture = loadJson("villages.json");
const prData = loadJson("pricing_rules.json");
const PRICING_RULES = prData[0].fields.payload;
const mealsRaw = loadJson("meals.json");
const MEALS_CATALOG = mealsRaw.map((m) => ({
  code: m.pk,
  label: m.fields.label,
  price_adult: m.fields.price_adult,
  price_child: m.fields.price_child,
}));
const marketingSeasonsFixture = loadJson("marketing_seasons.json");
const formulasFixture = loadJson("formulas.json");

// formules is a Django model @property derived from the Formula M2M table
// (apps/catalog/models.py:Village.formules) — it is NOT a field in
// villages.json. Rebuild the same village → [codes] map from formulas.json,
// sorted PC, DP, LOC like the property does.
const FORMULE_SORT_ORDER = { PC: 0, DP: 1, LOC: 2 };
const VILLAGE_FORMULES = {};
for (const row of formulasFixture) {
  if (row.model !== "catalog.formula") continue;
  const code = row.pk;
  for (const vid of row.fields.villages ?? []) {
    if (!VILLAGE_FORMULES[vid]) VILLAGE_FORMULES[vid] = [];
    VILLAGE_FORMULES[vid].push(code);
  }
}
for (const vid of Object.keys(VILLAGE_FORMULES)) {
  VILLAGE_FORMULES[vid].sort((a, b) => (FORMULE_SORT_ORDER[a] ?? 99) - (FORMULE_SORT_ORDER[b] ?? 99));
}

const VILLAGES_RAW = {};
for (const d of villageFixture) {
  if (d.model === "catalog.village") VILLAGES_RAW[d.pk] = d.fields;
}

function villageForId(vid) {
  const raw = VILLAGES_RAW[vid];
  if (!raw) return null;
  // snake_case fixture → camelCase, same mapping as test_golden_master_js.py
  return {
    id: vid,
    nom: raw.nom ?? "",
    region: raw.region ?? "",
    formules: VILLAGE_FORMULES[vid] ?? [],
    hasLoc: raw.has_loc ?? false,
    ski: raw.ski ?? false,
    ouverture: raw.ouverture ?? "",
    tarifs: raw.tarifs ?? {},
    bebeClub: raw.bebe_club ?? false,
    forfaitRM: raw.forfait_rm ?? false,
    qfExc: raw.qf_exc ?? false,
    enfSoloHalf: raw.enf_solo_half ?? false,
  };
}

// ── Date helpers — port of common/utils.py ──────────────────────────────────

function parseIsoDate(s) {
  // YYYY-MM-DD, parsed as a UTC calendar date (no time-zone drift).
  const [y, m, d] = s.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

function isoDate(d) {
  return d.toISOString().slice(0, 10);
}

function addDaysUTC(d, days) {
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + days));
}

function diffNuits(dateDebut, dateFin) {
  const ms = dateFin.getTime() - dateDebut.getTime();
  return Math.round(ms / 86400000);
}

function dateToSaisonIdx(d) {
  if (d == null) return 2; // default to ete
  const m = d.getUTCMonth() + 1;
  const j = d.getUTCDate();
  const jj = m * 100 + j;
  if (jj >= 620 && jj <= 901) return 2; // ete
  if (jj >= 1220 || jj <= 106) return 3; // fetes
  if ((m === 2 && j >= 15) || (m === 3 && j <= 3)) return 1;
  if ((m === 4 && j >= 12) || (m === 5 && j <= 4)) return 1;
  if ((m === 10 && j >= 19) || (m === 11 && j <= 2)) return 1;
  return 0; // hs
}

const SAISON_KEYS = ["hs", "vs", "ete", "fetes"];

function saisonKeyFromDate(d) {
  return SAISON_KEYS[dateToSaisonIdx(d)];
}

// ── Marketing-seasons year-rolling — port of apps/catalog/services/marketing_seasons.py ──

function rollSeasonDatesToCurrentYear(anchorStart, anchorEnd, today) {
  const yearOffset = today.getUTCFullYear() - anchorEnd.getUTCFullYear();
  let candStart = new Date(
    Date.UTC(anchorStart.getUTCFullYear() + yearOffset, anchorStart.getUTCMonth(), anchorStart.getUTCDate())
  );
  let candEnd = new Date(
    Date.UTC(anchorEnd.getUTCFullYear() + yearOffset, anchorEnd.getUTCMonth(), anchorEnd.getUTCDate())
  );

  if (candEnd.getTime() < today.getTime()) {
    candStart = new Date(Date.UTC(candStart.getUTCFullYear() + 1, candStart.getUTCMonth(), candStart.getUTCDate()));
    candEnd = new Date(Date.UTC(candEnd.getUTCFullYear() + 1, candEnd.getUTCMonth(), candEnd.getUTCDate()));
  }
  return [candStart, candEnd];
}

function rolledSeasonWindow(seasonRow, today) {
  const anchorStart = parseIsoDate(seasonRow.fields.start_date);
  const anchorEnd = parseIsoDate(seasonRow.fields.end_date);
  const [candStart, candEnd] = rollSeasonDatesToCurrentYear(anchorStart, anchorEnd, today);
  return [candStart, candEnd];
}

const HIVER_ROW = marketingSeasonsFixture.find(
  (r) => r.model === "catalog.marketingseasons" && r.pk === "hiver"
);

// ── Rounding — JS Math.round() is the reference; Python's jsround() mirrors it ──

function jsround(x) {
  return Math.round(x);
}

// ── Transport — port of apps/pricing/services/transport.py ─────────────────

const FUEL_COST_PER_KM = { essence: 0.12, diesel: 0.09, electrique: 0.04 };
const TOLL_PER_KM = 0.07;
const TRAIN_ADULT_ONE_WAY = 65;
const TRAIN_CHILD_ONE_WAY = 35;

function fuelCostPerKm(fuel) {
  return FUEL_COST_PER_KM[fuel] ?? FUEL_COST_PER_KM.essence;
}

function carCostBreakdown(distanceOneWayKm, fuel) {
  const d = Math.max(0, distanceOneWayKm);
  const kmAR = d * 2;
  const fuelCost = jsround(kmAR * fuelCostPerKm(fuel));
  const tollCost = jsround(kmAR * TOLL_PER_KM);
  return { kmAR: Math.trunc(kmAR), fuelCost, tollCost, total: fuelCost + tollCost };
}

function trainTotal(adults, children) {
  const a = Math.max(0, adults);
  const c = Math.max(0, children);
  const oneWay = TRAIN_ADULT_ONE_WAY * a + TRAIN_CHILD_ONE_WAY * c;
  return jsround(oneWay * 2);
}

// ── Resto — port of apps/pricing/services/resto.py ──────────────────────────

function familyMealUnitPrice(meal, adults, children) {
  return Math.max(0, meal.price_adult) * Math.max(0, adults) + Math.max(0, meal.price_child) * Math.max(0, children);
}

function restoTotalAmount(meals, qtyByMealId, adults, children) {
  let total = 0;
  for (const meal of meals) {
    const qty = qtyByMealId[meal.code] ?? 0;
    if (qty <= 0) continue;
    total += qty * familyMealUnitPrice(meal, adults, children);
  }
  return total;
}

// ── Hotel comparison — port of apps/pricing/services/hotel.py ──────────────

function getHotelNightRate(saisonKey) {
  if (saisonKey === "ete") return 120;
  if (saisonKey === "fetes") return 110;
  return 90;
}

function estimateHotelTotal(family, estimate) {
  const nuitRate = getHotelNightRate(estimate.saisonKey);
  const nuits = Math.max(1, estimate.nuits);
  const nbAdults = family.adultes;
  const nbChildren = family.enfants.length;

  const nbCh = Math.ceil(nbAdults / 2 + (nbChildren > 0 ? 1 : 0));
  const hotelHeberg = nuitRate * nbCh * nuits;
  const hotelResto = (28 * nbAdults + 15 * nbChildren) * 3 * nuits;
  const hotelAct = (15 * nbAdults + 10 * nbChildren) * Math.ceil(nuits / 2);
  const transport = Math.max(0, estimate.transportTotal);

  return jsround(hotelHeberg + hotelResto + hotelAct + transport);
}

// ── Pricing rule lookups — port of stay_estimate.py helpers ────────────────

const QF_SEUIL_BAS = 880;
const QF_SEUIL_HAUT = 1350;

function childDiscountWithBebeClub(age, bebeClub, rules) {
  const cd = rules.childDiscounts;
  if (age < 1) return cd.lt1;
  if (age < 3) {
    if (bebeClub) return cd["1to2_withBebeClub"] ?? cd["1to3_withBebeClub"] ?? 0.7;
    return cd["1to2_withoutBebeClub"] ?? cd["1to3_withoutBebeClub"] ?? 0.9;
  }
  if (age < 6) return cd["3to5"] ?? cd["4to5"] ?? 0.4;
  if (age < 11) return cd["6to10"];
  if (age < 16) return cd["11to15"];
  return cd.ge16;
}

function qfRate(qfVal, qfExc) {
  if (qfVal == null) return 0.0;
  if (qfVal < QF_SEUIL_BAS) return qfExc ? 0.10 : 0.17;
  if (qfVal < QF_SEUIL_HAUT) return qfExc ? 0.05 : 0.10;
  return 0.0;
}

function durationCoef(nuits, rules) {
  const coefs = rules.durationCoefficients ?? {};
  const exact = coefs[String(nuits)];
  if (typeof exact === "number" && exact > 0) return exact;
  return nuits / 7;
}

function formulaCoef(formule, rules) {
  if (formule === "LOC") return 1.0;
  const coefs = rules.formulaCoefficients ?? {};
  const c = coefs[formule];
  return typeof c === "number" && c > 0 ? c : 1.0;
}

function membershipFee(family, rules) {
  const m = rules.membership ?? { individual: 22, familyOrCouple: 44 };
  if (family.adultes >= 2 || family.enfants.length > 0) return m.familyOrCouple;
  return m.individual;
}

function quinzaineRate(sejour, nuits, rules) {
  const promos = sejour.promos ?? {};
  if (!promos.quinzaineFutee) return 0.0;
  if (sejour.formule !== "PC") return 0.0;
  if (nuits < 14) return 0.0;
  return rules.quinzaineFuteeRate ?? 0.10;
}

function soloSupplement(family, sejour, nuits, rules) {
  if (family.adultes !== 1 || family.enfants.length < 1) return 0;
  const promos = sejour.promos ?? {};
  const mode = promos.soloSupplementMode ?? "default";
  const perNightMap = rules.soloSupplementPerNight ?? {};
  const perNight = perNightMap[mode] ?? 22;
  return Math.max(0, perNight) * nuits;
}

function maxiFamilyFactor(family, rules) {
  if (!family.maxiFamily) return 1.0;
  if (family.enfants.length < 3) return 1.0;
  const rate = rules.maxiFamilyChildrenRate ?? 0.20;
  return 1 - Math.max(0, Math.min(1, rate));
}

// ── Core estimator — line-for-line port of estimate_sejour_total() ─────────

function estimateSejourTotal({ family, sejour, village, pricingRules, mealsCatalog, today }) {
  if (!sejour.dateDebut || !sejour.dateFin) return null;
  const dStart = parseIsoDate(sejour.dateDebut);
  const dEnd = parseIsoDate(sejour.dateFin);
  const nuits = diffNuits(dStart, dEnd);
  if (nuits < 1) return null;

  const sk = saisonKeyFromDate(dStart);
  const coef = durationCoef(nuits, pricingRules);

  const tarifs = village.tarifs ?? {};
  const basePc = (tarifs.PC ?? {})[sk] ?? 0;
  const baseLoc = (tarifs.LOC ?? {})[sk] ?? 0;
  const base = sejour.formule === "LOC" ? baseLoc : basePc;
  if (!base || base <= 0) return null;

  const pb = base * coef * formulaCoef(sejour.formule, pricingRules);

  // QF discounts apply only in summer, and selectively in winter — exact
  // mirror of the gate currently in stay_estimate.py. Do not change this
  // without checking the Python service first; it is intentional and the
  // client has asked for it to stay as-is.
  let allowQf = false;
  if (sk === "ete") {
    allowQf = true;
  } else if (HIVER_ROW) {
    // Python calls rolled_season_window(hiver, d_start) — the window is
    // rolled to be near the STAY's start date, not near "today". Only the
    // separate sales_open check below uses the real wall-clock today().
    const [candStart, candEnd] = rolledSeasonWindow(HIVER_ROW, dStart);
    const salesOpen = new Date(Date.UTC(today.getUTCFullYear(), 5, 10)); // June 10 (month is 0-indexed)
    if (candStart.getTime() <= dStart.getTime() && dStart.getTime() <= candEnd.getTime() && today.getTime() >= salesOpen.getTime()) {
      allowQf = true;
    }
  }

  const qf = allowQf ? qfRate(family.qfVal, !!village.qfExc) : 0.0;
  const promos = sejour.promos ?? {};
  const promoRate = Math.max(0, Math.min(1, promos.promoSejourRate ?? 0));
  const quinzaine = quinzaineRate(sejour, nuits, pricingRules);
  const discountRate = 1 - (1 - qf) * (1 - promoRate) * (1 - quinzaine);
  const pbAfter = pb * (1 - discountRate);

  const bebeClub = !!village.bebeClub;
  const nbAdults = family.adultes;
  const enfants = family.enfants;
  const nbChildren = enfants.length;
  const totalAdults = pbAfter * nbAdults;

  const childFactor = maxiFamilyFactor(family, pricingRules);
  const childLines = [];
  let totalChildren = 0.0;
  for (const child of enfants) {
    const frac = childDiscountWithBebeClub(child.age, bebeClub, pricingRules);
    const amount = pbAfter * (1 - frac) * childFactor;
    totalChildren += amount;
    childLines.push({ age: child.age, discount_fraction: frac, amount: jsround(amount) });
  }

  const soloSupp = soloSupplement(family, sejour, nuits, pricingRules);
  const staySubtotal = totalAdults + totalChildren + soloSupp;
  const adhesion = membershipFee(family, pricingRules);

  const kitPrice = (pricingRules.defaults ?? {}).locKitPrice ?? 10;
  let extrasLoc = 0;
  if (sejour.formule === "LOC") {
    const extras = sejour.extras ?? {};
    extrasLoc = Math.max(0, extras.locCleaningFee ?? 0) + Math.max(0, extras.locKits ?? 0) * kitPrice;
  }

  // Activities
  const extraActs = sejour.extraActivities ?? {};
  const paidActs = extraActs.paidQtyById ?? {};
  let activitiesTotal = 0;
  const activitiesByRegion = sejour.activitiesByRegion ?? null;
  if (Object.keys(paidActs).length > 0 && activitiesByRegion) {
    const regionActs = activitiesByRegion[village.region] ?? [];
    let running = 0;
    for (const a of regionActs) {
      const qty = paidActs[a.id] ?? 0;
      if (qty <= 0) continue;
      const unit = Math.max(0, a.ad ?? 0) * nbAdults + Math.max(0, a.enf ?? 0) * nbChildren;
      running += qty * unit;
    }
    activitiesTotal = jsround(running);
  } else {
    const acts = sejour.activities ?? {};
    const outings = Math.max(0, acts.outings ?? 0);
    const unit = Math.max(0, acts.priceAdult ?? 0) * nbAdults + Math.max(0, acts.priceChild ?? 0) * nbChildren;
    activitiesTotal = outings * unit;
  }

  // Resto
  const restoBlock = sejour.resto ?? {};
  const qtyByMeal = restoBlock.qtyByMealId ?? {};
  let restoTotal = 0;
  if (Object.keys(qtyByMeal).length > 0 && mealsCatalog) {
    restoTotal = jsround(restoTotalAmount(mealsCatalog, qtyByMeal, nbAdults, nbChildren));
  }

  // Transport
  let transportTotal = 0;
  const transport = sejour.transport ?? {};
  const mode = transport.mode;
  if (mode === "car") {
    const rawDistance = transport.distanceOneWayKm;
    const distance = rawDistance == null ? 400 : rawDistance;
    const rawFuel = transport.fuel;
    const fuel = rawFuel == null ? "essence" : rawFuel;
    transportTotal = carCostBreakdown(distance, fuel).total;
  } else if (mode === "train") {
    transportTotal = trainTotal(nbAdults, nbChildren);
  }

  const total = staySubtotal + adhesion + extrasLoc + activitiesTotal + restoTotal + transportTotal;
  const persons = Math.max(1, nbAdults + nbChildren);

  const est = {
    total: jsround(total),
    perPerson: jsround(total / persons),
    totalAdults: jsround(totalAdults),
    totalChildren: jsround(totalChildren),
    perAdultBase: jsround(pbAfter),
    childLines,
    saisonKey: sk,
    nuits,
    discountRate,
    staySubtotal: jsround(staySubtotal),
    adhesion: jsround(adhesion),
    soloSupplement: jsround(soloSupp),
    extrasLoc: jsround(extrasLoc),
    activitiesTotal: jsround(activitiesTotal),
    restoTotal: jsround(restoTotal),
    transportTotal: jsround(transportTotal),
  };

  const hotel = estimateHotelTotal(family, {
    saisonKey: est.saisonKey,
    nuits: est.nuits,
    transportTotal: est.transportTotal,
  });
  est.hotelEstimate = hotel;
  est.hotelSavings = Math.max(0, hotel - est.total);
  est.savingsPct = hotel > 0 ? (est.hotelSavings / hotel) * 100 : 0.0;

  return est;
}

// ── Case matrix — mirrors export_golden_master.py's coverage shape ─────────

const SEASON_DATES = [
  ["2026-07-05", "2026-07-12", "ete"],
  ["2026-04-11", "2026-04-18", "hs"], // "vs"-targeted date that actually lands in hs per dateToSaisonIdx
  ["2026-02-14", "2026-02-21", "hs"],
  ["2026-12-26", "2027-01-02", "fetes"],
];

const FAMILY_PROFILES = [
  // [label, adultes, enfantsAges, qfVal, maxiFamily]
  ["qf0", 2, [], null, false],
  ["qf700", 2, [3, 10], 700, false],
  ["qf850", 2, [2, 5], 850, false],
  ["qf900", 2, [4, 8], 900, false],
  ["qf1500", 2, [6, 9], 1500, false],
];

const TRANSPORT_VARIANTS = [
  ["car", "car", 600, "essence"],
  ["train", "train", 0, "essence"],
];

function toCamelChildLines(childLines) {
  // Keep `discount_fraction` snake_case to match the existing golden_cases_js.json
  // shape and test_golden_master_js.py's expectations exactly.
  return childLines.map((c) => ({ age: c.age, discount_fraction: c.discount_fraction, amount: c.amount }));
}

function buildCases(villageIds, today) {
  const cases = [];
  for (const vid of villageIds) {
    const village = villageForId(vid);
    if (!village) continue;
    const formules = village.formules ?? [];
    let formule;
    if (formules.includes("PC")) formule = "PC";
    else if (formules.includes("DP")) formule = "DP";
    else if (formules.includes("LOC")) formule = "LOC";
    else continue;

    for (const [dateDebut, dateFin, saisonLabel] of SEASON_DATES) {
      for (const [famLabel, adultes, enfantsAges, qfVal, maxiFamily] of FAMILY_PROFILES) {
        for (const [transLabel, mode, dist, fuel] of TRANSPORT_VARIANTS) {
          const family = {
            adultes,
            enfants: enfantsAges.map((age) => ({ age })),
            qfVal,
            maxiFamily,
          };
          const sejour = {
            dateDebut,
            dateFin,
            formule,
            transport: { mode, distanceOneWayKm: dist, fuel },
            promos: { promoSejourRate: 0, quinzaineFutee: false },
          };

          const est = estimateSejourTotal({
            family,
            sejour,
            village,
            pricingRules: PRICING_RULES,
            mealsCatalog: MEALS_CATALOG,
            today,
          });
          if (est == null) continue;

          const id = `${vid}-${formule}-${dateDebut.slice(0, 7)}-${famLabel}-${transLabel}`;
          cases.push({
            id,
            input: { villageId: vid, family, sejour },
            expected: { ...est, childLines: toCamelChildLines(est.childLines) },
          });
        }
      }
    }
  }
  return cases;
}

// ── Main ─────────────────────────────────────────────────────────────────

function main() {
  const villageIds = args.villages
    ? args.villages.split(",").map((v) => v.trim()).filter(Boolean)
    : Object.keys(VILLAGES_RAW);

  const today = args.today ? parseIsoDate(args.today) : new Date(Date.UTC(
    new Date().getFullYear(), new Date().getMonth(), new Date().getDate()
  ));

  const cases = buildCases(villageIds, today);

  const outPath = resolve(__dirname, args.out);
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, JSON.stringify(cases, null, 2) + "\n", "utf-8");

  console.log(`Generated ${cases.length} case(s) for ${villageIds.length} village(s).`);
  console.log(`today=${isoDate(today)}${args.today ? " (overridden via --today)" : " (system date)"}`);
  console.log(`Written to ${outPath}`);
}

main();
