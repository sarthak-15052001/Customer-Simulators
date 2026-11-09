import type { SxProps, Theme } from "@mui/material/styles";

import { LANDING_INDEX_MAP_VIEWBOX } from "../../../utils/landingIndexMapCoords";
import { vtfFloralPatternOverlaySx } from "../../layout/vtfFloralPattern";
import { VTF_FONT } from "../../ui/vtfTypography";

export const landingIndexMapSectionSx: SxProps<Theme> = {
  position: "relative",
  overflow: "hidden",
  isolation: "isolate",
  bgcolor: "var(--vtf-mint)",
  px: { xs: 2, md: 3, lg: 4 },
  pt: { xs: 5, md: 7, lg: 8 },
  pb: { xs: 5, md: 7, lg: 8 },
};

export const landingIndexMapPatternSx: SxProps<Theme> = {
  ...vtfFloralPatternOverlaySx({ opacity: 0.22, tileSize: 96 }),
};

export const landingIndexMapInnerSx: SxProps<Theme> = {
  position: "relative",
  zIndex: 1,
  mx: "auto",
  width: "100%",
  maxWidth: 1320,
};

export const landingIndexMapLayoutSx: SxProps<Theme> = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "flex-start",
  justifyContent: "flex-start",
  gap: { xs: 2, md: 2, lg: 4 },
};

export const landingIndexMapContentSx: SxProps<Theme> = {
  position: "relative",
  zIndex: 3,
  width: { xs: "100%", lg: "56%" },
  flex: { lg: "1 1 56%" },
  minWidth: 0,
  pl: 0,
};

export const landingIndexMapHeadSx: SxProps<Theme> = {
  mb: { xs: 2, md: 2.5 },
};

export const landingIndexMapEyebrowSx: SxProps<Theme> = {
  display: "block",
  mb: 2.5,
  color: "var(--vtf-white)",
  fontFamily: "var(--hustle)",
  fontWeight: 300,
  fontSize: { xs: "1.875rem", md: "2.5rem" },
  lineHeight: { xs: 1.5, md: 1.475 },
  letterSpacing: { xs: "0.38px", md: "0.5px" },
  transform: "rotate(-4deg)",
  transformOrigin: "left center",
};

export const landingIndexMapTitleSx: SxProps<Theme> = {
  display: "block",
  fontWeight: 900,
  textTransform: "uppercase",
  color: "var(--vtf-navy)",
  fontFamily: "var(--heading)",
  fontSize: VTF_FONT.display,
  lineHeight: 1.15,
  letterSpacing: "-0.02em",
};

export const landingIndexMapRegionsRootSx: SxProps<Theme> = {
  position: "relative",
};

export const landingIndexMapMobileTogglerSx: SxProps<Theme> = {
  display: { xs: "flex", md: "none" },
  width: "100%",
  justifyContent: "flex-start",
  borderRadius: "999px",
  py: 1,
  px: 2,
  fontSize: VTF_FONT.md,
  fontWeight: 600,
  color: "#fff",
  bgcolor: "var(--vtf-navy)",
  boxShadow: "0 8px 20px rgba(var(--vtf-navy-rgb), 0.15)",
  textTransform: "none",
  "&:hover": { bgcolor: "var(--vtf-navy-light)" },
};

export const landingIndexMapRegionsMenuSx = (
  open: boolean,
): SxProps<Theme> => ({
  "@media (max-width:999px)": {
    position: "absolute",
    left: 0,
    right: 0,
    zIndex: 999,
    display: open ? "block" : "none",

    bgcolor: "var(--vtf-white)",
    borderRadius: 3,
    mt: 1,
    pt: 1,
    pb: 4,

    border: "1px solid rgba(var(--vtf-navy-rgb), 0.08)",
    boxShadow: "0 12px 28px rgba(var(--vtf-navy-rgb), 0.1)",

    maxHeight: "70vh",
    overflowY: "auto",
    overflowX: "hidden",

    WebkitOverflowScrolling: "touch",

    "&::-webkit-scrollbar": {
      width: "6px",
    },

    "&::-webkit-scrollbar-thumb": {
      background: "rgba(var(--vtf-navy-rgb),0.25)",
      borderRadius: "999px",
    },

    "&::-webkit-scrollbar-track": {
      background: "transparent",
    },
  },
});

export const landingIndexMapRegionsListSx: SxProps<Theme> = {
  m: 0,
  p: 0,
  listStyle: "none",
  display: "grid",
  gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0, 1fr))" },
  columnGap: { md: 2, lg: 2.5 },
  rowGap: { xs: 0, md: 1.5, lg: 2 },
};

export const landingIndexMapRegionColSx: SxProps<Theme> = {
  minWidth: 0,
  position: "relative",
};

export const landingIndexMapRegionLabelSx: SxProps<Theme> = {
  fontSize: VTF_FONT.md,
  lineHeight: 1.2,
  fontWeight: 500,
  color: "var(--vtf-navy)",
  whiteSpace: "normal",
  wordBreak: "break-word",
  flex: "1 1 auto",
  minWidth: 0,
  pr: 0.5,
  "@media (max-width:999px)": {
    flex: "none",
    width: "100%",
    px: 2.5,
    py: 1.5,
    pr: 6,
  },
};

export const landingIndexMapRegionItemSx: SxProps<Theme> = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: 0.75,
  minHeight: 48,
  height: "auto",
  py: { md: 0.5, lg: 0.75 },
  px: { md: 1.75, lg: 2 },
  width: "100%",
  borderRadius: "30px",
  cursor: "pointer",
  fontWeight: 500,
  lineHeight: 1.375,
  color: "var(--vtf-navy)",
  bgcolor: "transparent",
  "@media (max-width:999px)": {
    position: "relative",
    mb: 0,
    py: 0,
    px: 0,
    borderRadius: 0,
  },
};

export const landingIndexMapRegionIconSx: SxProps<Theme> = {
  position: "relative",
  width: 20,
  height: 20,
  flexShrink: 0,
  borderRadius: "50%",
  bgcolor: "#fff",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  pointerEvents: "none",
  alignSelf: "flex-start",
  mt: "0.2em",
  color: "var(--vtf-navy)",
  "@media (max-width:999px)": {
    position: "absolute",
    top: "50%",
    right: 20,
    transform: "translateY(-50%)",
    bgcolor: "#fff",
  },
};

export const landingIndexMapAreaSx: SxProps<Theme> = {
  position: "relative",
  zIndex: 2,
  overflow: "hidden",
  flex: { lg: "1 1 40%" },
  ml: { lg: "auto" },
  mt: { xs: 2, md: 0 },
  alignSelf: { lg: "stretch" },
  display: "flex",
  alignItems: "center",
  justifyContent: { xs: "center", lg: "flex-end" },
};

export const landingIndexMapSvgHostSx: SxProps<Theme> = {
  position: "relative",
  width: "100%",
  maxWidth: { xs: 400, md: 480, lg: 560 },
  mx: { xs: "auto", lg: 0 },
  "& svg": { width: "100%", height: "auto", display: "block" },
  "& [data-id-zone], & [data-id-zone] > path": {
    transition: "fill 0.25s ease-out",
  },
  '& [data-id-zone][data-selected="true"]': { fill: "var(--vtf-navy)" },
  '& [data-id-zone][data-selected="true"] > path': { fill: "var(--vtf-navy)" },
  '& [data-id-zone][data-selected="true"] ellipse': { fill: "#003040" },
  '& [data-id-zone][data-selected="true"] path[fill="#00445A"]': {
    fill: "var(--vtf-orange)",
  },
  '& [data-id-zone][data-selected="true"] [data-id-town]': {
    cursor: "pointer",
  },
  '& [data-id-town][data-selected="true"] path[fill="#00445A"]': {
    fill: "var(--vtf-mint)",
  },
};

export const landingIndexMapPopoverSx = (
  x: number,
  y: number,
): SxProps<Theme> => ({
  position: "absolute",
  left: `clamp(12px, ${x}px, calc(100% - 245px))`,
  top: `clamp(12px, ${y}px, calc(100% - 180px))`,
  transform: "translateY(-50%)",
  zIndex: 20,
  width: 275,
  backgroundColor: "#fff",
  border: "1px solid rgba(var(--vtf-navy-rgb), 0.12)",
  borderRadius: "16px",
  padding: "20px",
  boxShadow: "0 12px 48px rgba(var(--vtf-navy-rgb), 0.14)",
  animation: "landingMapFadeIn 0.3s ease-out",
  pointerEvents: "auto",
});

export const landingIndexMapPopoverRegionSx: SxProps<Theme> = {
  color: "var(--vtf-green)",
  fontWeight: 800,
  fontSize: VTF_FONT.md,
  textTransform: "uppercase",
  letterSpacing: "0.12em",
  mb: 1.5,
  fontFamily: "var(--body)",
};

export const landingIndexMapPopoverQuoteSx: SxProps<Theme> = {
  color: "var(--vtf-navy)",
  fontStyle: "italic",
  fontWeight: 500,
  fontSize: VTF_FONT.md,
  lineHeight: 1.55,
  mb: 2.5,
  borderLeft: "2.5px solid var(--vtf-orange)",
  pl: 1.5,
};

export const landingIndexMapPopoverDetailsSx: SxProps<Theme> = {
  color: "var(--vtf-navy)",
  fontWeight: 800,
  fontSize: VTF_FONT.md,
  fontFamily: "var(--heading)",
};

export const landingIndexMapPopoverPlaceSx: SxProps<Theme> = {
  color: "rgba(var(--vtf-navy-rgb), 0.54)",
  fontSize: VTF_FONT.md,
  mt: 0.5,
  fontWeight: 600,
  textTransform: "capitalize",
};

export const landingIndexMapMarkerSx = (
  x: number,
  y: number,
  selected: boolean,
): SxProps<Theme> => ({
  position: "absolute",
  left: `${(x / LANDING_INDEX_MAP_VIEWBOX.width) * 100}%`,
  top: `${(y / LANDING_INDEX_MAP_VIEWBOX.height) * 100}%`,
  /* Pin tip (bottom center) sits on the coordinate, not the marker bbox center */
  transform: "translate(-50%, -100%)",
  width: 20,
  height: 24,
  cursor: "pointer",
  zIndex: selected ? 10 : 5,
  transition: "transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275)",
  "&:hover": {
    transform: "translate(-50%, -100%) scale(1.15)",
  },
  "& svg": {
    width: "100%",
    height: "100%",
    filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.15))",
    "& [data-marker-pin]": {
      fill: selected ? "var(--vtf-mint)" : "var(--vtf-navy)",
      transition: "fill 0.25s ease",
    },
    "& [data-marker-dot]": {
      fill: "#fff",
    },
  },
});
