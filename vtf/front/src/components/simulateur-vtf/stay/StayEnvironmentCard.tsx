import * as React from "react";
import { Box, Button, Pill, Typography } from "../../ui";
import PlaceRoundedIcon from "@mui/icons-material/PlaceRounded";

import { useTranslation } from "../../../contexts/LanguageContext";
import { type SejourEnvKey } from "../../../utils/stayTab";
import { SelectedBadge } from "../../ui";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { VtfSectionHeading } from "../../shared/VtfSectionHeading";
import { StayEnvironmentSkeleton } from "./StayEnvironmentSkeleton";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";

import { useEnvironments } from "../../../hooks/season.hooks";

type Props = {
  seasonKey: string | null;
  value: { fEnv: SejourEnvKey | null };
  onSelect: (env: SejourEnvKey) => void;
};

export function StayEnvironmentCard({ seasonKey, value, onSelect }: Props) {
  const { t } = useTranslation();
  const ts = React.useCallback((k: string) => t(`simulateur.sejour.${k}`), [t]);

  const {
    data: envOptions = [],
    isLoading,
    isError,
    refetch,
  } = useEnvironments(seasonKey ?? undefined);

  if (isLoading) {
    return <StayEnvironmentSkeleton />;
  }

  return (
    <VtfGlassCard>
      <VtfSectionHeading
        accent="orange"
        icon={<PlaceRoundedIcon />}
        title={ts("environmentTitle")}
        rightSlot={
          <Pill
            size="small"
            label={
              value.fEnv
                ? `✓ ${ts("cardHintSelected")}`
                : `• ${ts("cardHintPick")}`
            }
            vtfTone={value.fEnv ? "softOrange" : "softNavy"}
            sx={{
              fontWeight: 900,
              height: "auto",
              py: 0.35,
              opacity: 0.95,
              fontSize: { xs: "var(--vtf-font-xs)", sm: "var(--vtf-font-sm)" },
            }}
          />
        }
      />

      <Box
        className={`grid gap-3 ${seasonKey === "hiver" ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1 sm:grid-cols-2 xl:grid-cols-3"}`}
      >
        {!isError &&
          envOptions.map((o) => {
            const sel = value.fEnv === (o.key as SejourEnvKey);
            return (
              <Button
                key={o.key}
                vtfVariant="selectableTileOrange"
                tileSelected={sel}
                onClick={() => onSelect(o.key as SejourEnvKey)}
                sx={{
                  minHeight: { xs: 124, sm: 152 },
                  px: { xs: 1.75, sm: 2 },
                  py: { xs: 1.5, sm: 2 },
                  borderRadius: "22px",
                  borderColor: sel
                    ? "rgba(var(--vtf-orange-rgb), 0.95)"
                    : "rgba(148, 163, 184, 0.35)",
                  bgcolor: sel
                    ? "rgba(var(--vtf-orange-rgb), 0.07)"
                    : "rgba(15, 23, 42, 0.025)",
                  alignItems: "stretch",
                  "&:hover": {
                    bgcolor: sel
                      ? "rgba(var(--vtf-orange-rgb), 0.085)"
                      : "rgba(15, 23, 42, 0.03)",
                    transform: "translateY(-2px)",
                  },
                }}
              >
                {sel && <SelectedBadge accent="orange" />}
                <Box
                  sx={{
                    width: "100%",
                    display: "flex",
                    flexDirection: { xs: "row", sm: "column" },
                    alignItems: { xs: "center", sm: "center" },
                    gap: { xs: 1.25, sm: 0 },
                    textAlign: { xs: "left", sm: "center" },
                  }}
                >
                  <Box
                    sx={{
                      width: { xs: 46, sm: 44 },
                      height: { xs: 46, sm: 44 },
                      borderRadius: "16px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      mb: { xs: 0, sm: 1.25 },
                      flex: "0 0 auto",
                      bgcolor: sel
                        ? "rgba(var(--vtf-orange-rgb), 0.10)"
                        : "rgba(255,255,255,0.55)",
                      border: "1px solid rgba(148, 163, 184, 0.30)",
                      boxShadow: sel
                        ? "0 14px 28px rgba(242,166,128,0.18)"
                        : "0 10px 20px rgba(2,8,23,0.05)",
                    }}
                  >
                    <Box sx={{ fontSize: 22, lineHeight: 1 }}>{o.icon}</Box>
                  </Box>
                  <Box sx={{ minWidth: 0, width: "100%" }}>
                    <Typography
                      sx={{
                        fontSize: {
                          xs: "var(--vtf-font-sm)",
                          sm: "var(--vtf-font-md)",
                        },
                        fontWeight: 950,
                        color: sel ? "var(--vtf-orange)" : "var(--vtf-navy)",
                        whiteSpace: "pre-line",
                        textAlign: { xs: "left", sm: "center" },
                        width: "100%",
                        lineHeight: 1.1,
                      }}
                    >
                      {o.label}
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: {
                          xs: "var(--vtf-font-sm)",
                          sm: "var(--vtf-font-sm)",
                        },
                        fontWeight: 750,
                        color: "var(--vtf-navy)",
                        opacity: 0.55,
                        lineHeight: 1.25,
                        textAlign: { xs: "left", sm: "center" },
                        width: "100%",
                        mt: 0.75,
                      }}
                    >
                      {o.sub}
                    </Typography>
                  </Box>
                </Box>
              </Button>
            );
          })}
      </Box>

      {isError && (
        <VtfErrorAlert
          title={ts("envErrorTitle")}
          message={ts("envErrorSubtitle")}
          onRetry={() => refetch()}
          retryLabel={t("simulateur.family.retry")}
          sx={{ mt: 2 }}
        />
      )}
    </VtfGlassCard>
  );
}
