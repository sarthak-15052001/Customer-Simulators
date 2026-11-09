export type PromosDiscountSummaryState =
  | "incomplete"
  | "pending"
  | "none"
  | "applied";

export function resolvePromosDiscountSummaryState(args: {
  isStayConfigured: boolean;
  hasEstimate: boolean;
  discountPct: number | null;
}): PromosDiscountSummaryState {
  const { isStayConfigured, hasEstimate, discountPct } = args;
  if (!isStayConfigured) return "incomplete";
  if (!hasEstimate) return "pending";
  if (
    discountPct != null &&
    Number.isFinite(discountPct) &&
    discountPct > 0
  ) {
    return "applied";
  }
  return "none";
}
