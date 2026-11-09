import { useCallback } from "react";
import { Box, Button, Pill, Typography, SelectedBadge } from "../../ui";
import LandscapeRoundedIcon from "@mui/icons-material/LandscapeRounded";

import { useTranslation } from "../../../contexts/LanguageContext";
import type { MarketingSeason } from "../../../api/season.api";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { VtfSectionHeading } from "../../shared/VtfSectionHeading";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";

// Formate les mois de la saison (ex: "Juil - Août") en fonction de la locale actuelle.
function formatSeasonMonths(
  startDate?: string,
  endDate?: string,
  fallbackKey?: string,
  ts?: (k: string) => string,
  currentLocale: string = "fr-FR",
) {
  if (startDate && endDate) {
    try {
      const start = new Date(startDate);
      const end = new Date(endDate);
      const fmt = new Intl.DateTimeFormat(currentLocale, { month: "short" });
      const m1 = fmt.format(start).replace(/\.$/, "");
      const m2 = fmt.format(end).replace(/\.$/, "");
      return `${m1.charAt(0).toUpperCase() + m1.slice(1)} - ${m2.charAt(0).toUpperCase() + m2.slice(1)}`;
    } catch {
      // Repli en cas d'erreur de parsing
    }
  }
  return ts && fallbackKey ? ts(`season.${fallbackKey}.sub`) : "";
}

type Props = {
  value: {
    fSaison: string | null;
  };
  onSelect: (s: MarketingSeason) => void;
  seasons?: MarketingSeason[];
  isError?: boolean;
  onRetry?: () => void;
};

export function StaySeasonCard({
  value,
  onSelect,
  seasons = [],
  isError,
  onRetry,
}: Props) {
  const { t, language } = useTranslation();
  const ts = useCallback((k: string) => t(`simulateur.sejour.${k}`), [t]);

  // Détermine la locale système à partir de la langue de l'application
  const localeMap: Record<string, string> = {
    fr: "fr-FR",
    en: "en-GB",
    es: "es-ES",
    nl: "nl-NL",
  };
  const currentLocale = localeMap[language] || "fr-FR";

  return (
    <VtfGlassCard>
      <VtfSectionHeading
        accent="teal"
        icon={<LandscapeRoundedIcon />}
        title={ts("seasonTitle")}
        rightSlot={
          <Pill
            size="small"
            label={
              value.fSaison
                ? `✓ ${ts("cardHintSelected")}`
                : `• ${ts("cardHintPick")}`
            }
            vtfTone={value.fSaison ? "softTeal" : "softNavy"}
            sx={{
              fontSize: "var(--vtf-font-sm)",
              fontWeight: 900,
              height: "auto",
              py: 0.35,
              opacity: 0.95,
            }}
          />
        }
      />

      <Box className="grid grid-cols-2 gap-3">
        {seasons.map((s) => {
          const sel = value.fSaison === s.key;
          return (
            <Button
              key={s.key}
              vtfVariant="selectableTileTeal"
              tileSelected={sel}
              onClick={() => onSelect(s)}
              sx={{
                color: "var(--vtf-navy)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 0.5,
                bgcolor: sel
                  ? "rgba(var(--vtf-teal-rgb), 0.09)"
                  : "rgba(255,255,255,0.55)",
                borderColor: sel ? "var(--vtf-teal)" : "rgba(15, 23, 42, 0.08)",
                "&:hover": {
                  bgcolor: sel
                    ? "rgba(var(--vtf-teal-rgb), 0.1)"
                    : "rgba(var(--vtf-cream-rgb), 0.5)",
                  transform: "translateY(-2px)",
                },
              }}
            >
              {sel && <SelectedBadge accent="teal" />}

              <Box
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: "16px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  mb: 1.25,
                  bgcolor: sel
                    ? "rgba(var(--vtf-teal-rgb), 0.10)"
                    : "rgba(255,255,255,0.55)",
                  border: "1px solid rgba(148, 163, 184, 0.30)",
                  boxShadow: sel
                    ? "0 14px 28px rgba(0,168,181,0.16)"
                    : "0 10px 20px rgba(2,8,23,0.05)",
                }}
              >
                <Box sx={{ fontSize: 22, lineHeight: 1 }}>{s.icon}</Box>
              </Box>

              <Typography
                sx={{
                  fontSize: "var(--vtf-font-md)",
                  fontWeight: 950,
                  color: sel ? "var(--vtf-teal)" : "var(--vtf-navy)",
                  textAlign: "center",
                  lineHeight: 1.1,
                }}
              >
                {s.label || ts(`season.${s.key}.label`)}
              </Typography>
              <Typography
                sx={{
                  fontSize: "var(--vtf-font-sm)",
                  fontWeight: 750,
                  color: "var(--vtf-navy)",
                  opacity: 0.6,
                  lineHeight: 1.25,
                  textAlign: "center",
                  mt: 0.75,
                }}
              >
                {formatSeasonMonths(
                  s.startDate,
                  s.endDate,
                  s.key,
                  ts,
                  currentLocale,
                )}
              </Typography>
            </Button>
          );
        })}
      </Box>

      {isError && (
        <VtfErrorAlert
          title={ts("errorSeasonsLoad")}
          message={ts("errorSubtitle")}
          onRetry={onRetry}
          retryLabel={t("simulateur.family.retry")}
          sx={{ mt: 2 }}
        />
      )}
    </VtfGlassCard>
  );
}
