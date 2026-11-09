import type { SxProps, Theme } from "@mui/material/styles";

/** Shared styles for StayNightsCard — fonts: xs 11px, sm 14px, md 16px only */
export const StayNightsS = {
  fieldLabel: {
    fontSize: "var(--vtf-font-xs)",
    fontWeight: 950,
    letterSpacing: "0.12em",
    textTransform: "uppercase",
    color: "var(--vtf-navy)",
    opacity: 0.55,
    mb: 0.5,
    display: "block",
  } as const,

  stepperWrap: {
    display: "inline-flex",
    alignItems: "center",
    gap: 1,
    p: 0.5,
    borderRadius: "16px",
    border: "1px solid #ececee",
    bgcolor: "var(--vtf-cream)",
    width: "fit-content",
  } as const,

  stepperValue: {
    fontSize: "var(--vtf-font-md)",
    fontWeight: 950,
    color: "var(--vtf-navy)",
    lineHeight: 1,
  } as const,

  stepperUnit: {
    fontSize: "var(--vtf-font-xs)",
    color: "var(--vtf-navy)",
    opacity: 0.55,
    fontWeight: 700,
  } as const,

  stepperValueWrap: {
    px: 1.5,
    textAlign: "center",
    minWidth: 52,
  } as const,

  shortcutsRow: {
    mt: 1.5,
    display: "flex",
    gap: 0.75,
  } as const,

  datesGrid: {
    mt: 1.5,
    display: "grid",
    gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
    gap: 1.5,
  } as const,

  dateField: {
    display: "grid",
    gap: 0.5,
  } as const,

  warningBox: {
    mt: 1.5,
    p: 1.25,
    borderRadius: "14px",
    border: "1px solid #d1dde1",
    bgcolor: "var(--vtf-soft-navy)",
  } as const,

  warningText: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 800,
    color: "var(--vtf-navy)",
  } as const,

  footerRow: {
    mt: 1.5,
    display: "flex",
    flexDirection: { xs: "column", sm: "row" },
    alignItems: { xs: "stretch", sm: "center" },
    justifyContent: "space-between",
    gap: 1,
  } as const,

  draftHint: {
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 700,
    color: "var(--vtf-navy)",
    opacity: 0.55,
  } as const,

  applyBtn: {
    alignSelf: { xs: "stretch", sm: "auto" },
  } as const,
} satisfies Record<string, SxProps<Theme> | Record<string, unknown>>;
