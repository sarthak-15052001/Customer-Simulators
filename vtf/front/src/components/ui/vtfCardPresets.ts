import type { SxProps, Theme } from "@mui/material/styles";

export const vtfTransparentCardSx: SxProps<Theme> = {
  overflow: "visible",
  background: "transparent",
  boxShadow: "none",
};

export const vtfTransparentCardContentSx: SxProps<Theme> = {
  overflow: "visible",
  p: 0,
};

/** Compact uppercase badge on section headings (included pill, live status, etc.). */
export const pillCompactCapsSx = {
  fontSize: 'var(--vtf-font-xs)',
  fontWeight: 950,
  height: "auto",
  py: 0.35,
  textTransform: "uppercase",
  letterSpacing: "0.12em",
  whiteSpace: "nowrap",
} as const;

export const pillTealAccentBorderSx = {
  border: "1px solid rgba(var(--vtf-teal-rgb), 0.20)",
} as const;

export const pillCompactRowSx = {
  fontSize: 'var(--vtf-font-xs)',
  fontWeight: 950,
  height: "auto",
  py: 0.2,
} as const;

/** Small caps field / section labels inside inset panels. */
export const vtfCapsLabelSx = {
  fontSize: 'var(--vtf-font-xs)',
  fontWeight: 950,
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  color: "rgba(0, 68, 90, 0.62)",
} as const;
