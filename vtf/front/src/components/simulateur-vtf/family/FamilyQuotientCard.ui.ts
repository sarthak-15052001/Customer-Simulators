import type {
  FamilyTabTranslations,
  QfBadgeKind,
} from "../../../types/familyTab";
import { fillQfTemplate } from "../../../utils/familyTab";

export const S = {
  hint: {
    fontSize: 'var(--vtf-font-sm)',
    color: "rgba(0, 68, 90, 0.72)",
    mb: 0.75,
    lineHeight: 1.35,
  },
  hint2: {
    fontSize: 'var(--vtf-font-sm)',
    fontWeight: 700,
    color: "rgba(0, 68, 90, 0.5)",
    mb: 1,
    lineHeight: 1.35,
  },
  link: {
    fontWeight: 800,
    color: "var(--vtf-teal)",
    textDecoration: "none",
  },
  inputWrap: {
    display: "grid",
    gridTemplateColumns: {
      xs: "1fr",
      sm: "minmax(0, 1fr) 110px auto",
    },
    alignItems: { xs: "stretch", sm: "end" },
    gap: { xs: 1.25, sm: 1 },
    p: 1.25,
    borderRadius: "16px",
    border: "1px solid rgba(15,23,42,0.09)",
    bgcolor: "rgba(var(--vtf-cream-rgb), 0.22)",
    boxShadow: "0 10px 26px rgba(0, 24, 38, 0.06)",
  },
  incomeWrap: { display: "grid", gap: 0.5, width: "100%", minWidth: 0 },
  fieldLabel: {
    fontSize: 'var(--vtf-font-xs)',
    fontWeight: 950,
    letterSpacing: "0.12em",
    textTransform: "uppercase",
    color: "rgba(0, 68, 90, 0.50)",
    pl: 0.25,
    display: "block",
  },
  fieldLabelGhost: {
    fontSize: 'var(--vtf-font-xs)',
    fontWeight: 950,
    letterSpacing: "0.12em",
    textTransform: "uppercase",
    pl: 0.25,
    opacity: 0,
    userSelect: "none",
  },
  partsWrap: { display: "grid", gap: 0.5, width: "100%", minWidth: 0 },
  btn: {
    py: 0.65,
    px: 1.75,
    fontWeight: 900,
    fontSize: 'var(--vtf-font-sm)',
    minHeight: 38,
    borderRadius: "14px",
    boxShadow: "0 10px 22px rgba(var(--vtf-orange-rgb), 0.18)",
    whiteSpace: { xs: "normal", sm: "nowrap" },
    width: { xs: "100%", sm: "auto" },
  },
  pillBox: (bg: string, border: string) => ({
    mt: 1,
    px: 1.25,
    py: 0.9,
    borderRadius: "14px",
    bgcolor: bg,
    border,
  }),
  errText: {
    fontSize: 'var(--vtf-font-sm)',
    fontWeight: 800,
    color: "error.main",
    lineHeight: 1.35,
  },
  okText: {
    fontSize: 'var(--vtf-font-sm)',
    fontWeight: 900,
    color: "var(--vtf-teal)",
    lineHeight: 1.25,
  },
  solCard: {
    background: "var(--vtf-navy)",
    boxShadow: "0 18px 40px #00445a2e",
    border: "1px solid #ffffff29",
  },
  solGlow: {
    position: "absolute",
    inset: 0,
    pointerEvents: "none",
    boxShadow: "inset 0 1px 0 #ffffff1f",
  },

  solTitle: { fontSize: 'var(--vtf-font-sm)', fontWeight: 900, mb: 1, position: "relative" },
  solBody: {
    fontSize: 'var(--vtf-font-sm)',
    opacity: 0.8,
    lineHeight: 1.4,
    position: "relative",
  },
} as const;

export const pillBaseSx = {
  fontSize: 'var(--vtf-font-sm)',
  fontWeight: 950,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  height: 24,
  px: 1.25,
} as const;

export const inputBaseSx = {
  "& .MuiOutlinedInput-root": {
    borderRadius: "14px",
    bgcolor: "rgba(255,255,255,0.78)",
    fontWeight: 900,
    fontSize: 'var(--vtf-font-sm)',
    height: 38,
    color: "var(--vtf-navy)",
    backdropFilter: "blur(6px)",
    "& fieldset": { borderColor: "rgba(0, 68, 90, 0.14)" },
    "&:hover fieldset": { borderColor: "rgba(0, 125, 140, 0.32)" },
    "&.Mui-focused fieldset": { borderColor: "rgba(0, 125, 140, 0.62)" },
  },
} as const;

export function getQfBadge(badgeKind: QfBadgeKind, tf: FamilyTabTranslations) {
  switch (badgeKind) {
    case "empty":
      return { tone: "softNavy" as const, label: tf("qfBadgeEmpty") };
    case "r1":
      return {
        tone: "softGreen" as const,
        label: `✓ ${fillQfTemplate(tf("qfBadgeR1"))}`,
      };
    case "r2":
      return {
        tone: "softTeal" as const,
        label: `✓ ${fillQfTemplate(tf("qfBadgeR2"))}`,
      };
    case "plein":
      return {
        tone: "softNavy" as const,
        label: fillQfTemplate(tf("qfBadgeHigh")),
      };
    default:
      return null;
  }
}

export function parseLocaleNumber(raw: string): number | null {
  const n = Number.parseFloat(raw.replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

export function getEstimateErrorMessage(
  err: Error,
  tf: FamilyTabTranslations,
): string {
  const e = err as Error & {
    response?: { data?: { detail?: unknown; message?: string } };
  };
  const detail = e.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (typeof e.response?.data?.message === "string")
    return e.response.data.message;
  if (
    Array.isArray(detail) &&
    detail[0] &&
    typeof detail[0] === "object" &&
    "msg" in detail[0]
  ) {
    return String((detail[0] as { msg: string }).msg);
  }
  return tf("qfEstimateError");
}

