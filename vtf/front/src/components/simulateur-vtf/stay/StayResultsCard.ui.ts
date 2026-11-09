export const StayResultsS = {
  toolbar: {
    display: "flex",
    flexDirection: { xs: "column", sm: "row" },
    flexWrap: { xs: "nowrap", sm: "wrap" },
    gap: 1,
    alignItems: { xs: "stretch", sm: "center" },
    width: "100%",
    justifyContent: { xs: "flex-start", sm: "flex-end" },
  },
  toolbarScrollRow: {
    display: "flex",
    alignItems: "center",
    gap: 0.75,
    width: { xs: "100%", sm: "auto" },
    flexShrink: 0,
  },
  activityBtnRow: {
    display: "flex",
    alignItems: "center",
    gap: 0.75,
    flexShrink: 0,
  },
  modeBtnText: {
    fontSize: "var(--vtf-font-sm) !important",
    whiteSpace: "nowrap",
  },
  filterFab: {
    width: 36,
    height: 36,
    flexShrink: 0,
    borderRadius: "50%",
    border: "2px solid rgba(var(--vtf-teal-rgb), 0.35)",
    bgcolor: "rgba(255, 255, 255, 0.98)",
    color: "var(--vtf-teal)",
    boxShadow: "0 4px 14px rgba(var(--vtf-teal-rgb), 0.16)",
    transition: "transform 0.15s ease, box-shadow 0.15s ease",
    "&:hover": {
      bgcolor: "rgba(var(--vtf-teal-rgb), 0.1)",
      boxShadow: "0 6px 18px rgba(var(--vtf-teal-rgb), 0.24)",
      transform: "translateY(-1px)",
    },
  },
  checkIconTeal: {
    fontSize: "var(--vtf-font-md)",
    mr: 0.5,
    color: "var(--vtf-teal)",
  },
  checkIconOrange: {
    fontSize: "var(--vtf-font-md)",
    mr: 0.5,
    color: "var(--vtf-orange)",
  },
  emptyDatasetWrap: {
    border: "2px dashed rgba(148, 163, 184, 0.5)",
    borderRadius: "22px",
    px: { xs: 2.5, sm: 3.5 },
    py: { xs: 3.5, sm: 4.5 },
    textAlign: "center",
    bgcolor: "rgba(15, 23, 42, 0.02)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 1.5,
  },
  emptyDatasetIcon: {
    width: 56,
    height: 56,
    borderRadius: "18px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    bgcolor: "rgba(var(--vtf-teal-rgb), 0.08)",
    border: "1px solid rgba(0, 168, 181, 0.18)",
  },
  emptyDatasetTitle: {
    fontWeight: 950,
    fontSize: { xs: "var(--vtf-font-md)", sm: "var(--vtf-font-md)" },
    color: "var(--vtf-navy)",
    lineHeight: 1.25,
  },
  emptyDatasetSubtitle: {
    fontWeight: 650,
    fontSize: { xs: "var(--vtf-font-sm)", sm: "var(--vtf-font-sm)" },
    color: "var(--vtf-navy)",
    opacity: 0.62,
    lineHeight: 1.45,
    maxWidth: 440,
  },
};

const searchNoMatchBase = {
  textAlign: "center",
  fontSize: "var(--vtf-font-sm)",
  fontWeight: 700,
  color: "var(--vtf-navy)",
  opacity: 0.55,
} as const;

export function searchNoMatchSx(compact?: boolean) {
  return { ...searchNoMatchBase, py: compact ? 2 : 3 };
}

export function attractionTileSx(sel: boolean) {
  return {
    p: 1.25,
    borderRadius: "18px",
    alignItems: "center",
    bgcolor: sel
      ? "rgba(var(--vtf-orange-rgb), 0.07)"
      : "rgba(var(--vtf-cream-rgb), 0.35)",
    borderColor: sel ? "var(--vtf-orange)" : "rgba(15, 23, 42, 0.08)",
    boxShadow: sel
      ? "0 14px 28px rgba(242,166,128,0.16)"
      : "0 10px 22px rgba(2,8,23,0.05)",
    "&:hover": {
      boxShadow: sel
        ? "0 18px 34px rgba(242,166,128,0.22)"
        : "0 14px 28px rgba(2,8,23,0.09)",
      bgcolor: sel
        ? "rgba(var(--vtf-orange-rgb), 0.085)"
        : "rgba(var(--vtf-cream-rgb), 0.42)",
      transform: "translateY(-2px)",
    },
  };
}

export function attractionIconWrapSx(sel: boolean) {
  return {
    width: 44,
    height: 44,
    borderRadius: "16px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    mb: 1.15,
    bgcolor: sel
      ? "rgba(var(--vtf-orange-rgb), 0.10)"
      : "rgba(255,255,255,0.55)",
    border: "1px solid rgba(148, 163, 184, 0.30)",
    boxShadow: sel
      ? "0 14px 28px rgba(242,166,128,0.16)"
      : "0 10px 20px rgba(2,8,23,0.05)",
  };
}
