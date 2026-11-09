import { VTF_FONT } from '../ui/vtfTypography'

export const VTF_HEADER = {
  topbar: {
    bg: "#00445A",
    textColor: "#ffffff",
    minHeight: 41,
    paddingTop: "12px",
    paddingBottom: "12px",
    fontSize: VTF_FONT.sm,
    lineHeight: "17px",
    fontWeight: 300,
    linkFontWeight: 400,
    patternSize: 64,
    patternOpacity: 0.1,
    langPaddingRight: 80,
  },
  main: {
    minHeight: 80,
  },
  logo: {
    height: 60,
    heightSm: 40,
  },
  search: {
    width: { sm: 200, md: 220 },
    height: 40,
    borderRadius: "20px",
    border: "1px solid #000000",
    fontSize: VTF_FONT.sm,
    lineHeight: "17px",
    placeholderColor: "#606060",
    color: "#000000",
    pl: "15px",
    pr: "40px",
    iconRight: 11,
    iconTop: 11,
    iconSize: 18,
    iconFontSize: VTF_FONT.lg,
  },
  accountBtn: {
    height: 40,
    minWidth: 40,
    px: "15px",
    py: "8px",
    fontSize: VTF_FONT.sm,
    lineHeight: "24px",
    fontWeight: 500,
    borderRadius: "45px",
    bg: "#00445A",
    hoverBg: "#003040",
  },
  contact: {
    linkFontSize: VTF_FONT.sm,
    linkLineHeight: "18px",
    linkColor: "#606060",
    linkWeight: 300,
    phoneFontSize: VTF_FONT.sm,
    phoneLineHeight: "17px",
    phoneColor: "#00445A",
    phoneWeight: 500,
    iconSize: 20,
    flagSize: 16,
  },
  flags: {
    france: "/icon-france.png",
    belgique: "/icon-belgique.png",
  },
} as const

export const headerSearchFieldSx = {
  position: "relative" as const,
  width: VTF_HEADER.search.width,
  height: VTF_HEADER.search.height,
}

export const headerSearchInputSx = {
  width: "100%",
  height: VTF_HEADER.search.height,
  borderRadius: VTF_HEADER.search.borderRadius,
  border: VTF_HEADER.search.border,
  bgcolor: "#ffffff",
  pl: VTF_HEADER.search.pl,
  pr: VTF_HEADER.search.pr,
  fontFamily: "var(--sans)",
  fontSize: VTF_HEADER.search.fontSize,
  lineHeight: VTF_HEADER.search.lineHeight,
  fontWeight: 400,
  color: VTF_HEADER.search.color,
  outline: "none",
  boxSizing: "border-box" as const,
  "&::placeholder": {
    color: VTF_HEADER.search.placeholderColor,
    opacity: 1,
  },
}

export const headerSearchIconBtnSx = {
  position: "absolute" as const,
  right: `${VTF_HEADER.search.iconRight}px`,
  top: `${VTF_HEADER.search.iconTop}px`,
  p: 0,
  minWidth: 0,
  width: VTF_HEADER.search.iconSize,
  height: VTF_HEADER.search.iconSize,
  color: "#000000",
  "&:hover": { bgcolor: "transparent" },
}
