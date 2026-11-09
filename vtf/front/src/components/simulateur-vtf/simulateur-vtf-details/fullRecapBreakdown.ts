import type { SejourEstimate } from "../../../utils/stayEstimate";
import { formatPercentInt } from "./_format";

/** `discountFraction` from API: share off adult rate (0.9 → −90 %). */
export function childDiscountLabel(
  fraction: number,
  tp: (key: string) => string,
): string | null {
  if (!Number.isFinite(fraction) || fraction <= 0) return null;
  const pct = Math.round(fraction * 100);
  if (pct <= 0) return null;
  return tp("recapCard.details.childDiscountNote").replace(
    "{{pct}}",
    formatPercentInt(pct),
  );
}

export function resolveStayDiscountPct(estimate: SejourEstimate): number | null {
  const dmPct = estimate.displayMetrics?.discountPct;
  if (dmPct != null && Number.isFinite(dmPct) && dmPct > 0) {
    return Math.round(dmPct);
  }
  if (estimate.discountRate > 0) {
    return Math.round(estimate.discountRate * 100);
  }
  return null;
}

export function resolveStayPackageTotal(estimate: SejourEstimate): number {
  const fromBreakdown = estimate.budgetBreakdown?.stay;
  if (fromBreakdown != null && Number.isFinite(fromBreakdown) && fromBreakdown > 0) {
    return fromBreakdown;
  }
  return estimate.staySubtotal + estimate.adhesion;
}
