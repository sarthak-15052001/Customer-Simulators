import type { SxProps, Theme } from "@mui/material/styles";

export type RecapSectionTheme = "budget" | "activities" | "resto" | "transport";

export type RecapMetricVariant = "family" | "stay" | "formula" | "budget";

const META_MUTED = "color-mix(in srgb, var(--vtf-navy) 58%, transparent)";
const META_SOFT = "color-mix(in srgb, var(--vtf-navy) 72%, transparent)";

/** Metadata / body copy — 14px primary, 11px tertiary (not section headings). */
export const RECAP_META = {
  body: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 700,
    color: "var(--vtf-navy)",
    lineHeight: 1.4,
  },
  bodyStrong: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 950,
    color: "var(--vtf-navy)",
    lineHeight: 1.35,
  },
  bodyMuted: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 650,
    color: META_MUTED,
    lineHeight: 1.45,
  },
  bodySoft: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 700,
    color: META_SOFT,
    lineHeight: 1.4,
  },
  caption: {
    fontSize: "var(--vtf-font-xs)",
    fontWeight: 650,
    color: META_MUTED,
    lineHeight: 1.4,
  },
  captionStrong: {
    fontSize: "var(--vtf-font-xs)",
    fontWeight: 800,
    color: META_SOFT,
    lineHeight: 1.35,
  },
  metricLine: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 950,
    color: "var(--vtf-navy)",
    lineHeight: 1.35,
  },
  rowValue: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 980,
    color: "var(--vtf-navy)",
    lineHeight: 1.3,
  },
  rowValueAccent: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 980,
    color: "var(--vtf-orange-dark)",
    lineHeight: 1.3,
  },
  note: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 700,
    color: "var(--vtf-green)",
    lineHeight: 1.4,
  },
} as const satisfies Record<string, SxProps<Theme>>;

/** Solid hex surfaces — no linear gradients in details / recap UI. */
export const RECAP_SURFACE = {
  panel: {
    budget: { bg: "#ffffff", border: "#e2e8ec", accent: "navy" as const },
    activities: { bg: "#faf3ef", border: "#f0ddd4", accent: "orange" as const },
    resto: { bg: "#f0fafb", border: "#d4ecef", accent: "teal" as const },
    transport: { bg: "#f4f7f8", border: "#dce4e7", accent: "navy" as const },
  },
  total: { bg: "#d6ece1", border: "#c8ddd0" },
  includes: { bg: "#fef0ec", border: "#f5d4c4" },
  header: { bg: "#fcf9f6", border: "#e2e8ec", icon: "#f4f7f8" },
  comparatorHotel: { bg: "#fff5f5", border: "#fadada" },
  comparatorSavings: { bg: "#2e7d5a" },
  savingsCard: { bg: "#fef0ec", border: "#f5d4c4" },
  ctaCard: { bg: "#ffffff", border: "#f5d4c4" },
  metric: {
    family: {
      bg: "#f4f7f8",
      border: "#e2e8ec",
      icon: "#00445a",
      label: "#00445a",
    },
    stay: {
      bg: "#faf3ef",
      border: "#f0ddd4",
      icon: "#f2a680",
      label: "#F2A680",
    },
    formula: {
      bg: "#f0fafb",
      border: "#d4ecef",
      icon: "#00a8b5",
      label: "#00a8b5",
    },
    budget: {
      bg: "#f4f7f8",
      border: "#dce4e7",
      icon: "#00445a",
      label: "#00445a",
    },
  },
} as const;

export function recapMetricLabelSx(variant: RecapMetricVariant): SxProps<Theme> {
  const m = RECAP_SURFACE.metric[variant];
  return {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 950,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: m.label,
    lineHeight: 1.2,
  };
}

/** Section headings & hero titles only — do not use for metadata lines. */
export const RECAP_TYPO = {
  tagline: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 950,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "var(--vtf-navy)",
    lineHeight: 1.2,
  },
  title: {
    fontSize: { xs: 22, sm: 26 },
    fontWeight: 980,
    letterSpacing: "-0.02em",
    lineHeight: 1.12,
    color: "var(--vtf-navy)",
  },
  sectionTitle: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 950,
    color: "var(--vtf-navy)",
    lineHeight: 1.2,
  },
  heroAmount: {
    fontSize: { xs: 28, sm: 32 },
    fontWeight: 980,
    color: "var(--vtf-navy)",
    lineHeight: 1,
    letterSpacing: "-0.02em",
  },
  heroAmountTeal: {
    fontSize: { xs: 24, sm: 28 },
    fontWeight: 980,
    color: "var(--vtf-teal)",
    lineHeight: 1,
  },
  comparatorAmount: {
    fontSize: 34,
    fontWeight: 980,
    lineHeight: 1,
    letterSpacing: "-0.02em",
  },
  totalAmount: {
    fontSize: 24,
    fontWeight: 980,
    color: "var(--vtf-orange-dark)",
    lineHeight: 1.1,
  },
  totalLabel: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 950,
    color: "var(--vtf-navy)",
    lineHeight: 1.2,
  },
  infoEyebrow: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 950,
    color: "var(--vtf-orange-dark)",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    lineHeight: 1.2,
  },
  savingsLead: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 950,
    color: "var(--vtf-navy)",
    lineHeight: 1.35,
  },
  actionSecondary: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 950,
    lineHeight: 1.2,
  },
  /** @deprecated Use RECAP_META — kept for gradual migration */
  metricValue: RECAP_META.metricLine,
  metricSublabel: RECAP_META.bodyMuted,
  rowLabel: RECAP_META.body,
  rowLabelStrong: RECAP_META.bodyStrong,
  rowValue: RECAP_META.rowValue,
  rowValueStrong: RECAP_META.rowValueAccent,
  rowNote: RECAP_META.note,
  infoBody: RECAP_META.body,
  metricLabel: RECAP_META.caption,
} as const satisfies Record<string, SxProps<Theme>>;

export const RECAP_ICON = {
  metric: 18,
  row: 18,
  rowChild: 17,
  header: 20,
  section: 18,
  action: 17,
} as const;
