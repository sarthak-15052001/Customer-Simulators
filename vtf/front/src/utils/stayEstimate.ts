import type { VtfFormule, VtfSaisonKey } from "../data/vtfStay";

/** Texte « inclus » par formule — fourni par `POST /estimate/stay` (`includes`). */
export type StayEstimateIncludes = Partial<Record<VtfFormule, string>>;

/**
 * Valeurs d’affichage pré-calculées par le backend (`display_metrics`).
 * L’interface ne doit pas recalculer ces données
 * (les arrondis et totaux doivent rester cohérents avec le PDF et la réservation).
 */
export type StayDisplayMetrics = {
  perDayFamily: number;
  perPersonPerDay: number;
  totalVtfStayOnly: number;
  savingsPct: number;

  /** Pourcentage entier provenant de l’API (`display_metrics.discount_pct`)
   * — ne pas recalculer depuis `discountRate` côté UI.
   */
  discountPct?: number | null;
};

/**
 * Répartition budgétaire utilisée pour les graphiques (`budget_breakdown`).
 * Tous les montants proviennent du serveur.
 * `activities` représente la partie des activités payantes
 * (même logique que `activitiesTotal`, mais regroupée pour les graphiques).
 */
export type StayBudgetBreakdown = {
  stay: number;
  restoration: number;
  transport: number;
  activities: number;
};

export type FormuleAlternativeEstimate = {
  formule: VtfFormule;
  total: number;
};

export type SejourEstimate = {
  /** Budget total (séjour + adhésion + extras + activités + restauration + transport). */
  total: number;
  /** Total divisé par le nombre de participants (indicatif). */
  perPerson: number;
  totalAdults: number;
  totalChildren: number;
  perAdultBase: number;
  childLines: Array<{
    age: number;
    discountFraction: number;
    amount: number;
  }>;
  saisonKey: VtfSaisonKey;
  nuits: number;
  discountRate: number;
  staySubtotal: number;
  adhesion: number;
  soloSupplement: number;
  extrasLoc: number;
  activitiesTotal: number;
  restoTotal: number;
  transportTotal: number;
  hotelEstimate: number;
  hotelSavings: number;
  savingsPct: number;
  bookingUrl?: string;
  displayMetrics?: StayDisplayMetrics | null;
  budgetBreakdown?: StayBudgetBreakdown | null;
  /** Libellés dynamiques « inclus » (clés PC / DP / LOC). */
  includes?: StayEstimateIncludes;
  /** PC/DP totals when `formule` is LOC (`POST /estimate/stay`). */
  formuleAlternatives?: FormuleAlternativeEstimate[];
};

export function resolveStayIncludesText(
  formule: VtfFormule | null,
  includes?: StayEstimateIncludes | null,
): string | null {
  if (!formule) return null;
  const text = includes?.[formule]?.trim();
  return text || null;
}

export function extractErrorMessage(error: unknown): string | null {
  if (!error) return null;
  if (typeof error === "object" && error !== null) {
    const errObj = error as Record<string, unknown>;
    const response = errObj.response;
    if (response && typeof response === "object") {
      const resData = (response as Record<string, unknown>).data;
      if (typeof resData === "string" && resData.trim()) {
        return resData.trim();
      }
      if (typeof resData === "object" && resData !== null) {
        const dataObj = resData as Record<string, unknown>;
        if (typeof dataObj.message === "string" && dataObj.message.trim()) {
          return dataObj.message.trim();
        }
        if (typeof dataObj.error === "string" && dataObj.error.trim()) {
          return dataObj.error.trim();
        }
        if (typeof dataObj.detail === "string" && dataObj.detail.trim()) {
          return dataObj.detail.trim();
        }
      }
    }
    if (
      typeof errObj.message === "string" &&
      errObj.message.trim() &&
      !errObj.message.startsWith("Request failed")
    ) {
      return errObj.message.trim();
    }
  }
  if (typeof error === "string" && error.trim()) return error.trim();
  return null;
}

