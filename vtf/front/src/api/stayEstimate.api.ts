import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";
import type { FamilyState } from "../types/familyTab";
import type { SejourState } from "../types/stayTab";
import type {
  SejourEstimate,
  StayBudgetBreakdown,
  StayDisplayMetrics,
  StayEstimateIncludes,
  FormuleAlternativeEstimate,
} from "../utils/stayEstimate";
import type { VtfFormule } from "../data/vtfStay";
import type { FuelKey } from "../data/vtfTransport";
import { addDaysIso, diffNuits, todayIsoLocal } from "../utils/stayTab";
import { isQfReductionPeriod } from "../utils/familyTab";

/** Transport slice sent to `POST /estimate/stay` — fields match what each mode uses server-side. */
export type EstimateStayTransport =
  | { mode: "onSite" }
  | { mode: "train" }
  | { mode: "car"; distanceOneWayKm: number; fuel: FuelKey };

/** `POST /api/v1/estimate/stay` body (camelCase, matches `EstimateStayInputSerializer`). */
export type EstimateStayRequestBody = {
  villageId: string;
  family: {
    adultes: number;
    enfants: Array<{ age: number }>;
    qfVal: number | null;
    maxiFamily: boolean;
    isSoloParent: boolean;
  };
  sejour: {
    dateDebut: string;
    dateFin: string;
    formule: SejourState["formule"];
    fNuits: number;
    extras: { locCleaningFee: number; locKits: number };
    activities: { outings: number; priceAdult: number; priceChild: number };
    extraActivities: { paidQtyById: Record<string, number> };
    resto: SejourState["resto"];
    transport: EstimateStayTransport;
    promos: SejourState["promos"];
  };
  _meta?: Record<string, unknown>;
  /** When `sejour.formule` is LOC, ask API for PC/DP comparison totals in one response. */
  includeFormuleAlternatives?: boolean;
};

export type StayEstimateApiResult = SejourEstimate & { bookingUrl?: string };

function unwrapStayEstimatePayload(data: unknown): unknown {
  if (!data || typeof data !== "object") return data;
  const o = data as Record<string, unknown>;
  if ("data" in o && o.data != null && typeof o.data === "object") {
    return o.data;
  }
  return data;
}

function asNumber(v: unknown, fallback = 0): number {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function parseDisplayMetrics(row: Record<string, unknown>): StayDisplayMetrics | null {
  const raw = row.displayMetrics ?? row.display_metrics;
  if (!raw || typeof raw !== "object") return null;
  const m = raw as Record<string, unknown>;
  const discountPctRaw = m.discountPct ?? m.discount_pct;
  const discountPct =
    discountPctRaw === null || discountPctRaw === undefined
      ? null
      : asNumber(discountPctRaw, NaN);
  return {
    perDayFamily: asNumber(m.perDayFamily ?? m.per_day_family),
    perPersonPerDay: asNumber(m.perPersonPerDay ?? m.per_person_per_day),
    totalVtfStayOnly: asNumber(m.totalVtfStayOnly ?? m.total_vtf_stay_only),
    savingsPct: asNumber(m.savingsPct ?? m.savings_pct),
    discountPct:
      discountPct !== null && Number.isFinite(discountPct) ? discountPct : null,
  };
}

const VTF_FORMULE_CODES = new Set<VtfFormule>(["PC", "DP", "LOC"]);

function parseIncludes(row: Record<string, unknown>): StayEstimateIncludes | undefined {
  const raw = row.includes;
  if (!raw || typeof raw !== "object") return undefined;
  const out: StayEstimateIncludes = {};
  for (const [key, val] of Object.entries(raw as Record<string, unknown>)) {
    if (!VTF_FORMULE_CODES.has(key as VtfFormule)) continue;
    if (typeof val !== "string") continue;
    const text = val.trim();
    if (text) out[key as VtfFormule] = text;
  }
  return Object.keys(out).length ? out : undefined;
}

function parseBudgetBreakdown(row: Record<string, unknown>): StayBudgetBreakdown | null {
  const raw = row.budgetBreakdown ?? row.budget_breakdown;
  if (!raw || typeof raw !== "object") return null;
  const b = raw as Record<string, unknown>;
  return {
    stay: asNumber(b.stay),
    restoration: asNumber(b.restoration),
    transport: asNumber(b.transport),
    activities: asNumber(b.activities),
  };
}

function parseFormuleAlternatives(
  row: Record<string, unknown>,
): FormuleAlternativeEstimate[] | undefined {
  const raw = row.formuleAlternatives ?? row.formule_alternatives;
  if (!Array.isArray(raw) || !raw.length) return undefined;
  const out: FormuleAlternativeEstimate[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const o = item as Record<string, unknown>;
    const code = o.formule;
    if (code !== "PC" && code !== "DP" && code !== "LOC") continue;
    out.push({ formule: code, total: asNumber(o.total) });
  }
  return out.length ? out : undefined;
}

/** Parse JSON from `SejourEstimateOutputSerializer` or wrapped `{ success, data }` (+ optional `bookingUrl`). */
export function parseStayEstimateResponse(data: unknown): StayEstimateApiResult {
  const root = data && typeof data === "object" ? (data as Record<string, unknown>) : null;
  if (root && root.success === false) {
    const msg = typeof root.message === "string" ? root.message : "Stay estimate failed";
    throw new Error(msg);
  }

  const node = unwrapStayEstimatePayload(data);
  if (!node || typeof node !== "object") {
    throw new Error("Invalid estimate response");
  }
  const row = node as Record<string, unknown>;
  const childLinesRaw = row.childLines ?? row.child_lines;
  const childLines: SejourEstimate["childLines"] = [];
  if (Array.isArray(childLinesRaw)) {
    for (const line of childLinesRaw) {
      if (!line || typeof line !== "object") continue;
      const c = line as Record<string, unknown>;
      childLines.push({
        age: asNumber(c.age, 0),
        discountFraction: asNumber(
          c.discountFraction !== undefined && c.discountFraction !== null
            ? c.discountFraction
            : c.discount_fraction,
          0,
        ),
        amount: asNumber(c.amount, 0),
      });
    }
  }

  const displayMetrics = parseDisplayMetrics(row);
  const budgetBreakdown = parseBudgetBreakdown(row);
  const includes = parseIncludes(row);
  const formuleAlternatives = parseFormuleAlternatives(row);

  return {
    total: asNumber(row.total),
    perPerson: asNumber(row.perPerson ?? row.per_person),
    totalAdults: asNumber(row.totalAdults ?? row.total_adults),
    totalChildren: asNumber(row.totalChildren ?? row.total_children),
    perAdultBase: asNumber(row.perAdultBase ?? row.per_adult_base),
    childLines,
    saisonKey: (typeof row.saisonKey === "string"
      ? row.saisonKey
      : typeof row.saison_key === "string"
        ? row.saison_key
        : "ete") as SejourEstimate["saisonKey"],
    nuits: asNumber(row.nuits),
    discountRate: asNumber(row.discountRate ?? row.discount_rate),
    staySubtotal: asNumber(row.staySubtotal ?? row.stay_subtotal),
    adhesion: asNumber(row.adhesion),
    soloSupplement: asNumber(row.soloSupplement ?? row.solo_supplement),
    extrasLoc: asNumber(row.extrasLoc ?? row.extras_loc),
    activitiesTotal: asNumber(row.activitiesTotal ?? row.activities_total),
    restoTotal: asNumber(row.restoTotal ?? row.resto_total),
    transportTotal: asNumber(row.transportTotal ?? row.transport_total),
    hotelEstimate: asNumber(row.hotelEstimate ?? row.hotel_estimate),
    hotelSavings: asNumber(row.hotelSavings ?? row.hotel_savings),
    savingsPct: asNumber(row.savingsPct ?? row.savings_pct),
    displayMetrics,
    budgetBreakdown,
    includes,
    formuleAlternatives,
    bookingUrl:
      typeof row.bookingUrl === "string"
        ? row.bookingUrl
        : typeof row.booking_url === "string"
          ? row.booking_url
          : undefined,
  };
}

/** Build transport payload: only send fields the pricing engine uses per mode. */
export function buildEstimateTransportPayload(
  transport: SejourState["transport"],
): EstimateStayTransport {
  if (transport.mode === "car") {
    return {
      mode: "car",
      distanceOneWayKm: transport.distanceOneWayKm,
      fuel: transport.fuel,
    };
  }
  if (transport.mode === "train") {
    return { mode: "train" };
  }
  return { mode: "onSite" };
}

/**
 * Build the request payload for `POST /estimate/stay`.
 * Returns `null` when village, dates, or pricing formule are not ready.
 */
export function buildEstimateStayRequestBody(args: {
  villageId: string | null;
  family: FamilyState;
  sejour: SejourState;
}): EstimateStayRequestBody | null {
  const { villageId, family, sejour } = args;
  if (!villageId) return null;
  if (!sejour.formule) return null;
  /**
   * `StayNightsCard` keeps draft dates until « Appliquer »; users can pick a village
   * before committing. Match that card’s defaults (`draftFromCommitted`) so the
   * estimate API still runs once a village and formule are selected.
   */
  const dateDebut = sejour.dateDebut ?? todayIsoLocal();
  const dateFin =
    sejour.dateFin ?? addDaysIso(dateDebut, Math.max(1, sejour.fNuits || 7));
  const nuits = diffNuits(dateDebut, dateFin);
  if (nuits == null || nuits < 1) return null;

  return {
    villageId,
    family: {
      adultes: family.adultes,
      enfants: family.enfants.map((e) => ({ age: e.age })),
      qfVal: isQfReductionPeriod(dateDebut, villageId, sejour.fSaison)
        ? family.qfVal
        : null,
      maxiFamily: family.maxiFamily,
      isSoloParent: family.adultes === 1 && family.enfants.length > 0,
    },
    sejour: {
      dateDebut,
      dateFin,
      formule: sejour.formule,
      fNuits: sejour.fNuits,
      extras: { locCleaningFee: 0, locKits: 0 },
      activities: { outings: 0, priceAdult: 0, priceChild: 0 },
      extraActivities: {
        paidQtyById: { ...(sejour.extraActivities?.paidQtyById ?? {}) },
      },
      resto: sejour.resto,
      transport: buildEstimateTransportPayload(sejour.transport),
      promos: {
        promoSejourRate: sejour.promos.promoSejourRate,
        quinzaineFutee: sejour.formule === "PC" && nuits >= 14,
        soloSupplementMode: sejour.promos.soloSupplementMode,
      },
    },
    includeFormuleAlternatives: true,
  };
}

export const stayEstimateApi = {
  postEstimateStay: async (body: EstimateStayRequestBody): Promise<StayEstimateApiResult> => {
    const { data } = await apiClient.post<unknown>(ENDPOINTS.PRICING.ESTIMATE_STAY, body);
    return parseStayEstimateResponse(data);
  },
};
