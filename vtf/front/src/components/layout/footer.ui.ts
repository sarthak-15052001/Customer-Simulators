import type { SxProps, Theme } from "@mui/material/styles";

import { vtfFloralPatternOverlaySx } from "./vtfFloralPattern";

export const footerMainSx: SxProps<Theme> = {
  position: "relative",
  overflow: "hidden",
  bgcolor: "#044D65",
  color: "#fff",
};

export const footerMainPatternSx: SxProps<Theme> = vtfFloralPatternOverlaySx();

export const footerMainInnerSx: SxProps<Theme> = {
  position: "relative",
  zIndex: 1,
  maxWidth: 1320,
  mx: "auto",
  display: "flex",
  flexDirection: { xs: "column", lg: "row" },
  alignItems: "stretch",
  justifyContent: "space-between",
  px: { xs: 2.5, lg: 4 },
};

export const footerColumnsSx: SxProps<Theme> = {
  order: { xs: 2, lg: 1 },
  flex: 1,
  display: "flex",
  flexDirection: { xs: "column", lg: "row" },
  justifyContent: "space-between",
  gap: { xs: 0, lg: 3 },
  py: { xs: 5, lg: 10 },
  pr: { lg: 3 },
  width: { lg: "calc(100% - 400px)" },
  minWidth: 0,
};

export const footerColumnSx: SxProps<Theme> = {
  color: "#fff",
  fontSize: "var(--vtf-font-sm)",
  lineHeight: "1.875rem",
  flex: { lg: "1 1 0" },
  minWidth: 0,
  borderBottom: { xs: "1px solid rgba(255,255,255,0.2)", lg: "none" },
  pb: { xs: 3, lg: 0 },
  mb: { xs: 3, lg: 0 },
  pr: { lg: 1 },
  "&:last-of-type": {
    borderBottom: { xs: "none", lg: "none" },
    mb: { xs: 0, lg: 0 },
    pb: { xs: 0, lg: 0 },
  },
};

export const footerColumnTitleSx: SxProps<Theme> = {
  color: "#fff",
  fontWeight: 700,
  fontSize: "var(--vtf-font-sm)",
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  mb: 0,
  fontFamily: "var(--heading)",
};

export const footerLinkSx: SxProps<Theme> = {
  color: "#fff",
  fontSize: "inherit",
  lineHeight: "inherit",
  fontWeight: 400,
  textDecoration: "none",
  display: "block",
  "&:hover": { textDecoration: "underline" },
};

export const footerPaymentsTitleSx: SxProps<Theme> = {
  ...footerColumnTitleSx,
  mt: { xs: 0, lg: 5 },
  mb: { lg: 2 },
  display: { xs: "none", lg: "block" },
};

export const footerPaymentsSx: SxProps<Theme> = {
  display: { xs: "none", lg: "flex" },
  alignItems: "center",
  flexWrap: "wrap",
  gap: 2,
  opacity: 0.5,
  "& img": { width: 45, height: "auto", objectFit: "contain" },
};

export const footerContactSx: SxProps<Theme> = {
  order: { xs: 1, lg: 2 },
  position: "relative",
  width: { xs: "100%", lg: 360 },
  flexShrink: 0,
  maxWidth: "100%",
  alignSelf: "stretch",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  py: { xs: 6, lg: 0 },
  px: { lg: 2 },
  minHeight: { xs: "auto", lg: 0 },
  "&::before": {
    content: '""',
    display: "block",
    bgcolor: "var(--vtf-navy)",
    borderRadius: "100%",
    width: { xs: "calc(100vw + 400px)", lg: 900 },
    height: { xs: 900, lg: 900 },
    position: "absolute",
    top: { xs: -475, lg: "50%" },
    left: { xs: "50%", lg: "auto" },
    right: { lg: -500 },
    transform: {
      xs: "translateX(-50%)",
      lg: "translateY(-50%)",
    },
    zIndex: 0,
  },
};

export const footerContactInnerSx: SxProps<Theme> = {
  position: "relative",
  zIndex: 1,
  textAlign: "center",
  minWidth: 230,
  width: "100%",
  maxWidth: 320,
  mx: "auto",
  py: { xs: 0, lg: 2 },
};

export const footerContactTaglineSx: SxProps<Theme> = {
  color: "#fff",
  fontWeight: 300,
  fontSize: "var(--vtf-font-lg)",
  lineHeight: 1.2,
  mb: 2,
};

export const footerSocialLinkSx: SxProps<Theme> = {
  width: 40,
  height: 40,
  borderRadius: "50%",
  bgcolor: "#044D65",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: "#fff",
  transition: "background-color 0.3s ease",
  "&:hover": { bgcolor: "#003040" },
};

export const footerPhoneSx: SxProps<Theme> = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "5px",
  color: "var(--vtf-orange)",
  fontWeight: 500,
  fontSize: "var(--vtf-font-md)",
  lineHeight: 1.2,
  textDecoration: "none",
  my: 1,
  "&:hover": { textDecoration: "underline" },
};

export const footerHoursSx: SxProps<Theme> = {
  display: "block",
  fontSize: "var(--vtf-font-sm)",
  lineHeight: 1.57,
  fontWeight: 300,
  color: "#fff",
  mb: 1.25,
};

export const footerContactCtaSx: SxProps<Theme> = {
  display: "inline-block",
  position: "relative",
  mt: 1,
  color: "#fff",
  fontFamily: "var(--hustle)",
  fontSize: { xs: "1.5rem", md: "1.75rem" },
  textDecoration: "none",
  "&::after": {
    content: '""',
    position: "absolute",
    left: 0,
    bottom: -4,
    width: "100%",
    height: 2,
    bgcolor: "#fff",
    transition: "all 0.3s ease",
  },
  "&:hover": {
    color: "var(--vtf-orange)",
    "&::after": {
      width: "calc(100% - 30px)",
      left: 15,
      bgcolor: "var(--vtf-orange)",
    },
  },
};

export const footerBottomSx: SxProps<Theme> = {
  bgcolor: "#003040",
  color: "#fff",
  py: 1.5,
  fontSize: "var(--vtf-font-xs)",
  lineHeight: 1.375,
  fontWeight: 300,
};

export const footerBottomInnerSx: SxProps<Theme> = {
  maxWidth: 1320,
  mx: "auto",
  px: { xs: 2.5, lg: 4 },
  py: 0.5,
  display: "flex",
  flexDirection: { xs: "column", md: "row" },
  alignItems: "center",
  justifyContent: "space-between",
  gap: { xs: 2, md: 2 },
  textAlign: { xs: "center", md: "left" },
};

export const footerBottomLinkSx: SxProps<Theme> = {
  color: "inherit",
  textDecoration: "none",
  "&:hover": { textDecoration: "underline" },
};
