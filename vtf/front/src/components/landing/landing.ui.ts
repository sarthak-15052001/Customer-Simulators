import type { SxProps, Theme } from "@mui/material/styles";
import { VTF_FONT } from "../ui";

export const LANDING_MAP_WAVE_FILL = "#EAF6F0";

export const landingPageSx: SxProps<Theme> = {
  bgcolor: "var(--vtf-cream)",
  pb: 8,
  overflow: "hidden",
};

export const landingHeroSx: SxProps<Theme> = {
  background: `
    radial-gradient(circle at top left, rgba(242,166,128,0.22), transparent 34%),
    radial-gradient(circle at top right, rgba(0,168,181,0.14), transparent 38%),
    radial-gradient(circle at center, rgba(174,218,196,0.26), transparent 42%),
    linear-gradient(180deg, #fff 0%, #fcf9f6 14%, #fdf2ec 28%, #f6faf8 46%, #eaf7f8 64%, #d8eef1 82%, #cbe4e8 100%)
  `,
  pt: { xs: 6, md: 8 },
  pb: {
  xs: `calc(${VTF_FONT.lg} * 4)`,
  md: `calc(${VTF_FONT.lg} * 6)`,
},
  position: "relative",
  color: "var(--vtf-navy)",
};

export const landingHeroGlowSx: SxProps<Theme> = {
  position: "absolute",
  inset: 0,
  background: `
    radial-gradient(circle at top left, rgba(var(--vtf-orange-rgb),0.16), transparent 32%),
    radial-gradient(circle at top right, rgba(var(--vtf-teal-rgb),0.12), transparent 34%),
    radial-gradient(circle at center right, rgba(174,218,196,0.22), transparent 38%)
  `,
  pointerEvents: "none",
};

export const landingHeroBlob = (
  top: number,
  side: "left" | "right",
  color: string,
): SxProps<Theme> => ({
  position: "absolute",
  top,
  [side]: side === "left" ? -120 : -80,
  width: side === "left" ? 320 : 300,
  height: side === "left" ? 320 : 300,
  borderRadius: "50%",
  background: color,
  filter: "blur(70px)",
  pointerEvents: "none",
});

export const landingHeroScriptSx: SxProps<Theme> = {
  color: "var(--vtf-orange)",
  fontSize: { xs: 24, md: 32 },
  mb: 1.5,
  textShadow: "0 4px 12px rgba(var(--vtf-orange-rgb),0.12)",
};

export const landingHeroTitleSx: SxProps<Theme> = {
  fontWeight: 900,
  fontSize: { xs: 34, sm: 48, md: 64 },
  lineHeight: 1.05,
  mb: 2.5,
  textTransform: "uppercase",
  letterSpacing: "-0.03em",
  fontFamily: "var(--heading)",
  color: "var(--vtf-navy)",
};

export const landingHeroDescSx: SxProps<Theme> = {
  color: "rgba(var(--vtf-navy-rgb),0.78)",
  fontWeight: 500,
  fontSize: { xs: 'var(--vtf-font-lg)', md: 20 },
  lineHeight: 1.7,
  maxWidth: 680,
  mx: "auto",
  mb: 5,
};

export const landingHeroCtaSx: SxProps<Theme> = {
  fontSize: 'var(--vtf-font-md)',
  py: 1.2,
  px: 4,
  background:
    "linear-gradient(135deg, var(--vtf-orange) 0%, var(--vtf-orange-dark) 100%)",
  boxShadow: "0 14px 34px rgba(var(--vtf-orange-rgb),0.28)",
  borderRadius: "999px",
  "&:hover": {
    background:
      "linear-gradient(135deg, var(--vtf-orange-dark) 0%, #D97755 100%)",
    boxShadow: "0 18px 40px rgba(var(--vtf-orange-rgb),0.34)",
  },
};

export const landingHeroStatsSx: SxProps<Theme> = {
  mt: 6,
  display: "flex",
  justifyContent: "center",
  gap: 4,
  flexWrap: "wrap",
};

export const landingStatItemSx: SxProps<Theme> = {
  display: "flex",
  alignItems: "center",
  gap: 1.5,
};

export const landingStatLabelSx: SxProps<Theme> = {
  fontWeight: 800,
  color: "var(--vtf-navy)",
};

export const landingContentSx: SxProps<Theme> = {
  mt: -4,
  position: "relative",
  zIndex: 2,
  bgcolor: "var(--vtf-cream)",
};

export const landingDisclaimerSx: SxProps<Theme> = {
  color: "rgba(var(--vtf-navy-rgb),0.42)",
  fontWeight: 700,
  fontSize: 'var(--vtf-font-sm)',
  mt: 4,
  mb: 4,
  textAlign: "center",
  textTransform: "uppercase",
  letterSpacing: "1px",
};

export const landingSiteLinkSx: SxProps<Theme> = {
  color: "var(--vtf-orange)",
  textDecoration: "none",
  borderBottom: "1px solid",
  pb: 0.2,
};

export const landingFeaturesGridSx: SxProps<Theme> = {
  display: "grid",
  gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
  gap: 4,
  maxWidth: 980,
  mx: "auto",
};

export const landingFeatureCardSx: SxProps<Theme> = {
  borderRadius: 5,
  border: "1px solid rgba(var(--vtf-navy-rgb),0.06)",
  boxShadow: "0 16px 42px rgba(var(--vtf-navy-rgb),0.06)",
  bgcolor: "rgba(255,255,255,0.92)",
  backdropFilter: "blur(14px)",
  overflow: "hidden",
  transition: "all 0.3s ease",
  "&:hover": {
    transform: "translateY(-4px)",
    boxShadow: "0 22px 54px rgba(var(--vtf-navy-rgb),0.10)",
  },
};

export const landingFeatureIconSx = (iconBg: string): SxProps<Theme> => ({
  width: 64,
  height: 64,
  borderRadius: "20px",
  bgcolor: iconBg,
  display: "grid",
  placeItems: "center",
  color: "var(--vtf-navy)",
  flexShrink: 0,
  boxShadow: "inset 0 2px 10px rgba(255,255,255,0.35)",
});

export const landingFeatureTitleSx: SxProps<Theme> = {
  fontWeight: 900,
  color: "var(--vtf-navy)",
  fontSize: 'var(--vtf-font-lg)',
  mb: 1,
  textTransform: "uppercase",
  letterSpacing: "0.02em",
};

export const landingFeatureDescSx: SxProps<Theme> = {
  color: "rgba(var(--vtf-navy-rgb),0.72)",
  fontWeight: 500,
  fontSize: 'var(--vtf-font-md)',
  lineHeight: 1.75,
};

export const landingFeatureFooterSx: SxProps<Theme> = {
  borderTop: "1px solid rgba(var(--vtf-navy-rgb),0.08)",
  mt: 3,
  pt: 2.5,
};

export const landingBottomPillsSx: SxProps<Theme> = {
  mt: 6,
  mb: { xs: 1, md: 2 },
  display: "flex",
  justifyContent: "center",
  gap: 2,
  flexWrap: "wrap",
};

export const LANDING_CONTAINER_CLASS = "mx-auto w-full max-w-[1120px] px-4";
