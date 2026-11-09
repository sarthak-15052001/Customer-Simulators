import type { SxProps, Theme } from "@mui/material/styles";

export const backToTopRootSx: SxProps<Theme> = {
  position: "fixed",
  right: { xs: "var(--vtf-font-md)", md: 22 },
  bottom: { xs: "var(--vtf-font-lg)", md: 24 },
  zIndex: 1200,
  cursor: "pointer",

  animation: "backToTopFadeIn 0.3s ease",

  "@keyframes backToTopFadeIn": {
    from: {
      opacity: 0,
      transform: "translateY(12px)",
    },
    to: {
      opacity: 1,
      transform: "translateY(0)",
    },
  },
};

export const backToTopButtonSx: SxProps<Theme> = {
  position: "relative",

  width: 60,
  height: 80,

  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
};

export const backToTopBgSvgStyle = {
  position: "absolute" as const,
  inset: 0,
  width: "100%",
  height: "100%",
};

export const backToTopArrowSvgStyle = {
  position: "relative" as const,
  zIndex: 1,
  width: 18,
  height: 18,
  marginBottom: 4,
};

export const backToTopTextSx: SxProps<Theme> = {
  position: "relative",
  zIndex: 1,

  fontSize: "11px",
  lineHeight: 1.1,

  textAlign: "center",
  fontWeight: 700,

  color: "#00445A",

  maxWidth: 42,
  userSelect: "none",
};
