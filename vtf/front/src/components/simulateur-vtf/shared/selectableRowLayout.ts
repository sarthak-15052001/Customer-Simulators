import type { SxProps, Theme } from "@mui/material/styles";

/** Flex / grid shell for selectable activity, meal, and resto lines. */
export const selectableRowShellSx: SxProps<Theme> = {
  position: "relative",
  display: "flex",
  alignItems: { xs: "flex-start", sm: "center" },
  gap: { xs: 1, sm: 1.25 },
  flexWrap: "wrap",
  "@media (min-width: 600px)": {
    flexWrap: "nowrap",
  },
};

/** Primary label column (title + per-person rates). */
export const selectableRowTitleWrapSx: SxProps<Theme> = {
  flex: 1,
  minWidth: 0,
  order: { xs: 1, sm: 0 },
  flexBasis: { xs: "calc(100% - 44px)", sm: "auto" },
  pr: { xs: 0, sm: "var(--vtf-font-md)" },
};

/** Price column — in flow on mobile, centered overlay from sm up. */
export const selectableRowPriceCenterSx: SxProps<Theme> = {
  position: { xs: "relative", sm: "absolute" },
  left: { sm: "50%" },
  top: { sm: "50%" },
  transform: { sm: "translate(-50%, -50%)" },
  display: "flex",
  flexDirection: "column",
  alignItems: { xs: "flex-end", sm: "center" },
  textAlign: { xs: "right", sm: "center" },
  pointerEvents: "none",
  zIndex: 1,
  flexShrink: 0,
  order: { xs: 2, sm: 0 },
  ml: { xs: "auto", sm: 0 },
  alignSelf: { xs: "flex-start", sm: "auto" },
  maxWidth: { xs: "42%", sm: "none" },
};

/** Secondary line under price (e.g. "€/family outing"). */
export const selectableRowPriceMetaSx: SxProps<Theme> = {
  whiteSpace: { xs: "normal", sm: "nowrap" },
  wordBreak: { xs: "break-word", sm: "normal" },
};

/** Quantity stepper column — full-width row on mobile. */
export const selectableRowStepperWrapSx: SxProps<Theme> = {
  flexShrink: 0,
  flexBasis: { xs: "100%", sm: "auto" },
  width: { xs: "100%", sm: "auto" },
  order: { xs: 10, sm: 0 },
  ml: { xs: 0, sm: "auto" },
  display: "flex",
  justifyContent: "flex-end",
  pt: { xs: 0.25, sm: 0 },
  position: "relative",
  zIndex: 2,
};

/** Spacer when stepper hidden (keeps sm row height aligned). */
export const selectableRowStepperSpacerSx: SxProps<Theme> = {
  display: { xs: "none", sm: "block" },
  width: 108,
  flexShrink: 0,
  order: { xs: 10, sm: 0 },
};

/** Toggle button column. */
export const selectableRowToggleSx: SxProps<Theme> = {
  flexShrink: 0,
  alignSelf: "flex-start",
  mt: 0.25,
  order: { xs: 0, sm: 0 },
};

/** Footer / total summary row. */
export const selectableRowTotalShellSx: SxProps<Theme> = {
  position: "relative",
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: { xs: 1, sm: 0.75 },
  rowGap: { xs: 0.75, sm: 0 },
};

export const selectableRowTotalLabelSx: SxProps<Theme> = {
  display: "flex",
  alignItems: "center",
  gap: 0.75,
  minWidth: 0,
  flex: { xs: "1 1 160px", sm: 1 },
};

/** Total price — always in document flow (no absolute overlay). */
export const selectableRowTotalPriceSx: SxProps<Theme> = {
  display: "flex",
  flexDirection: "column",
  alignItems: { xs: "flex-end", sm: "center" },
  textAlign: { xs: "right", sm: "center" },
  flexShrink: 0,
  ml: { xs: "auto", sm: 0 },
  "@media (min-width: 600px)": {
    position: "absolute",
    left: "50%",
    top: "50%",
    transform: "translate(-50%, -50%)",
    ml: 0,
  },
};

/** Title column when there is no toggle (resto meals). */
export const selectableRowTitleWrapRestoSx: SxProps<Theme> = {
  flex: 1,
  minWidth: 0,
  order: { xs: 1, sm: 0 },
  flexBasis: { xs: "calc(100% - 92px)", sm: "auto" },
  pr: { xs: 0, sm: "var(--vtf-font-md)" },
};

export const selectableRowTotalActionSx: SxProps<Theme> = {
  flexShrink: 0,
  ml: { xs: "auto", sm: 0 },
  width: { xs: "100%", sm: "auto" },
  display: "flex",
  justifyContent: { xs: "flex-end", sm: "flex-start" },
  "@media (min-width: 600px)": {
    position: "relative",
    zIndex: 2,
    width: "auto",
  },
};
