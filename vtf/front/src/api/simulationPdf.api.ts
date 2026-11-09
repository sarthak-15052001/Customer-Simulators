import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";
import type { FamilyState } from "../types/familyTab";
import type { SejourState } from "../types/stayTab";
import type { VtfVillage } from "../data/vtfStay";
import type { SejourEstimate } from "../utils/stayEstimate";
import {
  appLanguageToIntlLocale,
  formatPlanningDayLabel,
  getStayDays,
} from "../utils/planningTab";
import type { Language } from "../locales/loadLocale";

export type SimulationPdfPayload = {
  // Matches the user-provided schema (camelCase, no underscores).
  villageName: string;
  dateDebut: string;
  dateFin: string;
  nuits: string;
  saison: string;
  adultes: string;
  nbEnfants: string;
  enfantsAges: string;
  totalEuro: string;
  perPersonEuro: string;
  perPersonPerDay: string;
  perDayFamily: string;
  formuleLabel: string;
  perAdultBase: string;
  totalAdults: string;
  /**
   * Dynamic children detail lines (recommended for rendering).
   */
  children: Array<{
    age: string;
    discountLabel: string;
    amount: string;
  }>;
  totalChildren: string;
  staySubtotal: string;
  adhesionEuro: string;
  stayPackageTotal: string;
  activitiesTotal: string;
  restoTotal: string;
  transportModeLabel: string;
  transportDetailNote: string;
  transportTotal: string;
  formuleIncludesText: string;
  hotelSavingsEuro: string;
  savingsPct: string;
  bookingUrl: string;

  planning: Array<{
    label: string;
    morning: string;
    afternoon: string;
    evening: string;
    kind: "day" | "departure";
  }>;
};

function sanitizePdfText(input: string): string {
  // Many PDF renderers crash on emoji/ZWJ/variation selectors depending on fonts.
  // Keep plain text only to avoid backend 500s.
  return (input ?? "")
    .replace(/[\uFE0F\u200D]/g, "") // variation selector + ZWJ
    .replace(/\p{Extended_Pictographic}/gu, "") // emoji pictographs
    .trim();
}

function joinSlotLabels(
  sejour: SejourState,
  dayKey: string,
  slot: "matin" | "aprem" | "soir",
): string {
  const items = sejour.planning?.[dayKey]?.[slot] ?? [];
  const label = items
    .map((it) => it.label)
    .filter(Boolean)
    .join(" · ");
  return sanitizePdfText(label) || "-";
}

export function buildSimulationPdfPayload(args: {
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
  estimate: SejourEstimate | null;
  bookingUrl: string;
  language: Language;
  formuleLabel: string;
  formuleIncludesText: string;
  transportModeLabel: string;
  transportDetailNote: string;
}): SimulationPdfPayload {
  const { family, sejour, village, estimate, bookingUrl } = args;

  const enfantsAges =
    family.enfants.length > 0
      ? family.enfants.map((e) => `${e.age}`).join(" · ")
      : "";

  const locale = appLanguageToIntlLocale(args.language);
  const days = getStayDays(sejour.dateDebut, sejour.dateFin);
  const d1 = days[0] ?? null;
  const d2 = days[1] ?? null;
  const d3 = days[2] ?? null;
  const dn = days.length ? days[days.length - 1] : null;

  const children =
    estimate?.childLines?.map((child) => ({
      age: child?.age != null ? String(child.age) : "",
      discountLabel:
        child?.discountFraction != null ? String(child.discountFraction) : "",
      amount: child?.amount != null ? String(child.amount) : "",
    })) ?? [];

  const planning: SimulationPdfPayload["planning"] = [
    {
      kind: "day",
      label: d1 ? sanitizePdfText(formatPlanningDayLabel(d1.key, locale)) : "-",
      morning: d1 ? joinSlotLabels(sejour, d1.key, "matin") : "-",
      afternoon: d1 ? joinSlotLabels(sejour, d1.key, "aprem") : "-",
      evening: d1 ? joinSlotLabels(sejour, d1.key, "soir") : "-",
    },
    {
      kind: "day",
      label: d2 ? sanitizePdfText(formatPlanningDayLabel(d2.key, locale)) : "-",
      morning: d2 ? joinSlotLabels(sejour, d2.key, "matin") : "-",
      afternoon: d2 ? joinSlotLabels(sejour, d2.key, "aprem") : "-",
      evening: d2 ? joinSlotLabels(sejour, d2.key, "soir") : "-",
    },
    {
      kind: "day",
      label: d3 ? sanitizePdfText(formatPlanningDayLabel(d3.key, locale)) : "-",
      morning: d3 ? joinSlotLabels(sejour, d3.key, "matin") : "-",
      afternoon: d3 ? joinSlotLabels(sejour, d3.key, "aprem") : "-",
      evening: d3 ? joinSlotLabels(sejour, d3.key, "soir") : "-",
    },
    {
      kind: "departure",
      label: dn ? sanitizePdfText(formatPlanningDayLabel(dn.key, locale)) : "-",
      morning: dn ? joinSlotLabels(sejour, dn.key, "matin") : "-",
      afternoon: dn ? joinSlotLabels(sejour, dn.key, "aprem") : "-",
      evening: dn ? joinSlotLabels(sejour, dn.key, "soir") : "-",
    },
  ];

  const stayPackageTotal =
    estimate?.budgetBreakdown?.stay != null
      ? estimate.budgetBreakdown.stay
      : (estimate?.staySubtotal ?? 0) + (estimate?.adhesion ?? 0);

  return {
    villageName: sanitizePdfText(village?.nom ?? ""),
    dateDebut: sejour.dateDebut ?? "",
    dateFin: sejour.dateFin ?? "",
    nuits: String(estimate?.nuits ?? sejour.fNuits ?? 0),
    saison: String(estimate?.saisonKey ?? sejour.fSaison ?? ""),
    adultes: String(family.adultes ?? 0),
    nbEnfants: String(family.enfants.length ?? 0),
    enfantsAges: sanitizePdfText(enfantsAges),
    totalEuro: String(estimate?.total ?? 0),
    perPersonEuro: String(estimate?.perPerson ?? 0),
    perPersonPerDay: String(estimate?.displayMetrics?.perPersonPerDay ?? 0),
    perDayFamily: String(estimate?.displayMetrics?.perDayFamily ?? 0),
    formuleLabel: sanitizePdfText(args.formuleLabel),
    perAdultBase: String(estimate?.perAdultBase ?? 0),
    totalAdults: String(estimate?.totalAdults ?? 0),
    children,
    totalChildren: String(estimate?.totalChildren ?? 0),
    staySubtotal: String(estimate?.staySubtotal ?? 0),
    adhesionEuro: String(estimate?.adhesion ?? 0),
    stayPackageTotal: String(stayPackageTotal ?? 0),
    activitiesTotal: String(estimate?.activitiesTotal ?? 0),
    restoTotal: String(estimate?.restoTotal ?? 0),
    transportModeLabel: sanitizePdfText(args.transportModeLabel),
    transportDetailNote: sanitizePdfText(args.transportDetailNote),
    transportTotal: String(estimate?.transportTotal ?? 0),
    formuleIncludesText: sanitizePdfText(args.formuleIncludesText),
    hotelSavingsEuro: String(estimate?.hotelSavings ?? 0),
    savingsPct: String(
      estimate?.displayMetrics?.savingsPct ?? estimate?.savingsPct ?? 0,
    ),
    bookingUrl,
    planning,
  };
}

export const simulationPdfApi = {
  generate: async (payload: SimulationPdfPayload): Promise<Blob> => {
    const url = ENDPOINTS.SIMULATIONS.PDF.endsWith("/")
      ? ENDPOINTS.SIMULATIONS.PDF
      : `${ENDPOINTS.SIMULATIONS.PDF}/`;

    const res = await apiClient.post(url, payload, {
      responseType: "blob",
      headers: {
        Accept: "application/pdf",
        "Content-Type": "application/json",
      },
      transformRequest: [(data) => JSON.stringify(data)],
    });
    return res.data as Blob;
  },
};
