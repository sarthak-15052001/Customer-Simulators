import { Box, Typography } from "../../ui";
import type { PromosDiscountSummaryState } from "./promosDiscountState";

export function TotalDiscountCard(props: {
  tp: (k: string) => string;
  state: PromosDiscountSummaryState;
  /** Integer % from `estimate.displayMetrics.discountPct` (API). */
  discountPct: number | null;
  discountedBudgetLabel: string | null;
}) {
  const { tp, state, discountPct, discountedBudgetLabel } = props;

  const budgetLine = (prefixKey: string) =>
    discountedBudgetLabel ? (
      <Typography sx={{ mt: 0.5, fontSize: 'var(--vtf-font-sm)', color: "text.secondary" }}>
        {tp(prefixKey)} {discountedBudgetLabel}
      </Typography>
    ) : null;

  return (
    <Box
      sx={{
        borderRadius: 3,
        border: "1px solid rgba(0, 68, 90, 0.12)",
        bgcolor: "rgba(0, 68, 90, 0.04)",
        p: 2,
        textAlign: "center",
      }}
    >
      {state === "applied" &&
      discountPct != null &&
      Number.isFinite(discountPct) &&
      discountPct > 0 ? (
        <>
          <Typography
            sx={{
              fontSize: 22,
              fontWeight: 980,
              color: "rgba(4, 120, 87, 0.95)",
            }}
          >
            −{discountPct}% {tp("totalAppliedSuffix")}
          </Typography>
          {budgetLine("discountedBudgetPrefix")}
        </>
      ) : state === "none" ? (
        <>
          <Typography
            sx={{
              fontSize: 'var(--vtf-font-md)',
              fontWeight: 900,
              color: "var(--vtf-navy)",
              lineHeight: 1.35,
            }}
          >
            {tp("totalAppliedNone")}
          </Typography>
          {budgetLine("totalBudgetPrefix")}
        </>
      ) : state === "pending" ? (
        <Typography sx={{ fontSize: 'var(--vtf-font-sm)', color: "text.secondary" }}>
          {tp("totalAppliedPending")}
        </Typography>
      ) : (
        <Typography sx={{ fontSize: 'var(--vtf-font-sm)', color: "text.secondary" }}>
          {tp("totalAppliedMissing")}
        </Typography>
      )}
    </Box>
  );
}
