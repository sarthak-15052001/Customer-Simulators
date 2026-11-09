import * as React from "react";
import { Box, Typography } from "../../../ui";
import { RECAP_ICON, RECAP_META } from "../recapCard.ui";
import { formatEuro } from "../_format";

export type BudgetDetailRowTone = "free" | "paid" | "resto" | "neutral";

const TONE_STYLES: Record<
  BudgetDetailRowTone,
  { border: string; bgActive: string; accent: string }
> = {
  free: {
    border: "rgba(var(--vtf-teal-rgb), 0.22)",
    bgActive: "rgba(var(--vtf-teal-rgb), 0.07)",
    accent: "var(--vtf-teal)",
  },
  paid: {
    border: "rgba(var(--vtf-orange-rgb), 0.28)",
    bgActive: "rgba(var(--vtf-orange-rgb), 0.08)",
    accent: "var(--vtf-orange)",
  },
  resto: {
    border: "rgba(var(--vtf-teal-rgb), 0.22)",
    bgActive: "rgba(var(--vtf-teal-rgb), 0.06)",
    accent: "var(--vtf-teal)",
  },
  neutral: {
    border: "rgba(0, 68, 90, 0.1)",
    bgActive: "rgba(0, 68, 90, 0.04)",
    accent: "var(--vtf-navy)",
  },
};

export function BudgetDetailSectionLabel({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Typography
      sx={{
        ...RECAP_META.captionStrong,
        mt: 1.25,
        mb: 0.75,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        "&:first-of-type": { mt: 0 },
      }}
    >
      {children}
    </Typography>
  );
}

export function BudgetDetailItemRow({
  icon,
  title,
  subtitle,
  qty,
  amount,
  amountLabel,
  tone = "neutral",
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  qty: number;
  amount: number | null;
  amountLabel?: string;
  tone?: BudgetDetailRowTone;
}) {
  const s = TONE_STYLES[tone];

  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: "auto 1fr auto",
        alignItems: "center",
        gap: { xs: 1, sm: 1.25 },
        px: { xs: 1, sm: 1.25 },
        py: 1,
        mb: 0.5,
        borderRadius: 2,
        border: "1px solid",
        borderColor: s.border,
        bgcolor: s.bgActive,
        transition: "border-color 0.15s ease, background 0.15s ease",
      }}
    >
      <Box
        sx={{
          width: 36,
          height: 36,
          borderRadius: 1.5,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          bgcolor: "rgba(255,255,255,0.85)",
          border: "1px solid rgba(0, 68, 90, 0.06)",
          color: s.accent,
          "& svg": { fontSize: RECAP_ICON.row },
        }}
      >
        {icon}
      </Box>

      <Box sx={{ minWidth: 0 }}>
        <Typography
          sx={{
            ...RECAP_META.bodyStrong,
            fontSize: "var(--vtf-font-sm)",
            color: s.accent,
            lineHeight: 1.3,
          }}
        >
          {title}
        </Typography>
        {subtitle ? (
          <Typography
            sx={{ ...RECAP_META.caption, mt: 0.25, lineHeight: 1.35 }}
          >
            {subtitle}
          </Typography>
        ) : null}
      </Box>

      <Box sx={{ textAlign: "right", flexShrink: 0 }}>
        <Typography
          sx={{
            ...RECAP_META.rowValue,
            fontSize: "var(--vtf-font-sm)",
            color:
              amount != null && amount > 0
                ? "rgba(185, 28, 28, 0.92)"
                : amount === 0
                  ? "#047857"
                  : "var(--vtf-navy)",
          }}
        >
          {amountLabel ?? (amount === null ? "-" : formatEuro(amount))}
        </Typography>
        <Typography
          sx={{
            ...RECAP_META.caption,
            mt: 0.2,
            fontWeight: 800,
            color: "var(--vtf-navy)",
          }}
        >
          × {qty}
        </Typography>
      </Box>
    </Box>
  );
}
