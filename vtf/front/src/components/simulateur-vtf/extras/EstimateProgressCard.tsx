import * as React from "react";
import { Box, Pill, Typography } from "../../ui";

import type { FamilyState } from "../../../types/familyTab";
import type { SejourEstimate } from "../../../utils/stayEstimate";
import { recapSeasonPillKey } from "../../../utils/extrasTab";
import type { SejourState } from "../../../types/stayTab";
import type { VtfVillage } from "../../../data/vtfStay";
import { formatEuro } from "../../../utils/currency";
import { useTranslation } from "../../../contexts/LanguageContext";
import InsightsRoundedIcon from "@mui/icons-material/InsightsRounded";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";
import { pillCompactCapsSx } from "../../ui/vtfCardPresets";
import { EstimateProgressCardSkeletonBody } from "./EstimateProgressCardSkeleton";

type Props = {
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
  estimate: SejourEstimate | null;
  estimateLoading?: boolean;
  estimateError?: boolean;
  estimateErrorMessage?: string | null;
  onRetryEstimate?: () => void;
};

const pillSx = {
  fontSize: "var(--vtf-font-sm)",
  fontWeight: 950,
  height: "auto",
  py: 0.25,
  color: "rgba(0, 68, 90, 0.92)",
  border: "1px solid rgba(0, 68, 90, 0.12)",
} as const;

function StatRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        py: 0.4,
      }}
    >
      <Typography
        sx={{
          fontSize: "var(--vtf-font-sm)",
          fontWeight: 700,
          color: "rgba(0, 68, 90, 0.65)",
        }}
      >
        {label}
      </Typography>
      <Typography
        sx={{
          fontSize: "var(--vtf-font-sm)",
          fontWeight: 900,
          color: highlight ? "var(--vtf-navy)" : "rgba(0, 68, 90, 0.85)",
        }}
      >
        {value}
      </Typography>
    </Box>
  );
}

export function EstimateProgressCard({
  family,
  sejour,
  village,
  estimate,
  estimateLoading = false,
  estimateError = false,
  estimateErrorMessage = null,
  onRetryEstimate,
}: Props) {
  const { t } = useTranslation();
  const tr = React.useCallback((k: string) => t(`simulateur.recap.${k}`), [t]);
  const te = React.useCallback((k: string) => t(`simulateur.extras.${k}`), [t]);

  const showSkeleton = !!sejour.villageId && estimateLoading && !estimateError;
  const showEstimateError =
    !!sejour.villageId && estimateError && !estimateLoading;

  const nightWord = sejour.fNuits > 1 ? tr("nightPlural") : tr("nightSingular");
  const adultWord = family.adultes > 1 ? tr("adultMany") : tr("adultOne");
  const childWord =
    family.enfants.length > 1 ? tr("childMany") : tr("childOne");
  const seasonLabel = sejour.fSaison || sejour.serverSeasonKey
    ? t(`simulateur.recap.pillSeason.${recapSeasonPillKey(sejour)}`)
    : null;
  const hasDate = Boolean(sejour.dateDebut && sejour.dateFin);

  const metaPills = (
    <Box sx={{ mt: 1, display: "flex", flexWrap: "wrap", gap: 0.75 }}>
      {seasonLabel ? (
        <Pill size="small" label={seasonLabel} vtfTone="softNavy" sx={pillSx} />
      ) : null}
      <Pill
        size="small"
        label={`${sejour.fNuits} ${nightWord}`}
        vtfTone="softNavy"
        sx={pillSx}
      />
      {hasDate && sejour.dateDebut ? (
        <Pill
          size="small"
          label={new Intl.DateTimeFormat("en-GB", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
          }).format(new Date(sejour.dateDebut))}
          vtfTone="softNavy"
          sx={pillSx}
        />
      ) : null}
    </Box>
  );

  const villageSummary =
    village != null ? (
      <Box
        sx={{
          mt: 1,
          px: 1,
          py: 0.75,
          borderRadius: "10px",
          background: "rgba(0, 68, 90, 0.04)",
          border: "1px solid rgba(0, 68, 90, 0.08)",
        }}
      >
        <Typography
          sx={{
            fontWeight: 950,
            color: "var(--vtf-navy)",
            fontSize: "var(--vtf-font-sm)",
            lineHeight: 1.25,
          }}
        >
          {village.env} {village.nom}
          {village.nom2 ? ` · ${village.nom2}` : ""}
        </Typography>
        <Typography
          sx={{
            fontWeight: 800,
            color: "rgba(0, 68, 90, 0.72)",
            fontSize: "var(--vtf-font-sm)",
            mt: 0.2,
          }}
        >
          {family.adultes} {adultWord}
          {family.enfants.length > 0 &&
            ` + ${family.enfants.length} ${childWord}`}
        </Typography>
      </Box>
    ) : null;

  return (
    <VtfGlassCard
      title={t("simulateur.extras.estimateInProgress")}
      headingIcon={<InsightsRoundedIcon />}
      headingAccent="teal"
      rightSlot={
        showSkeleton ? (
          <Pill
            size="small"
            label={t("simulateur.extras.estimateLoadingPill")}
            vtfTone="softTeal"
            sx={{ ...pillCompactCapsSx, opacity: 0.9 }}
          />
        ) : estimate && !showEstimateError ? (
          <Pill
            size="small"
            label={t("simulateur.extras.live")}
            vtfTone="softTeal"
            sx={pillCompactCapsSx}
          />
        ) : null
      }
    >
      {showEstimateError ? (
        <VtfErrorAlert
          title={tr("estimateErrorTitle")}
          message={estimateErrorMessage || tr("estimateErrorMessage")}
          onRetry={onRetryEstimate}
          retryLabel={t("simulateur.family.retry")}
          sx={{ mb: 1 }}
        />
      ) : null}

      {showSkeleton ? (
        <EstimateProgressCardSkeletonBody />
      ) : estimate ? (
        <Box sx={{ minWidth: 0 }}>
          <Typography
            sx={{
              fontWeight: 980,
              color: "var(--vtf-navy)",
              fontSize: { xs: 28, sm: 32 },
              lineHeight: 1,
              letterSpacing: "-0.03em",
            }}
          >
            {`~${formatEuro(estimate.total)}`}
          </Typography>
          <Typography
            sx={{
              fontSize: "var(--vtf-font-sm)",
              fontWeight: 850,
              color: "rgba(0, 68, 90, 0.6)",
              mt: 0.4,
            }}
          >
            ~{formatEuro(estimate.perAdultBase)}{" "}
            <Box component="span" sx={{ opacity: 0.75, fontWeight: 800 }}>
              {te("perAdult")}
            </Box>
          </Typography>
        </Box>
      ) : showEstimateError ? null : (
        <Typography
          sx={{
            fontWeight: 980,
            color: "rgba(0, 68, 90, 0.35)",
            fontSize: { xs: 28, sm: 32 },
            lineHeight: 1,
          }}
        >
          -
        </Typography>
      )}

      {metaPills}
      {villageSummary}

      {!showSkeleton && estimate ? (
        <Box
          sx={{
            mt: 1,
            borderTop: "1px solid rgba(0, 68, 90, 0.08)",
            pt: 1,
            display: "flex",
            flexDirection: "column",
            gap: 0,
          }}
        >
          {showEstimateError ? (
            <Typography
              sx={{
                fontSize: "var(--vtf-font-sm)",
                fontWeight: 800,
                color: "rgba(180, 60, 40, 0.92)",
                mb: 0.75,
              }}
            >
              {tr("serverEstimateFallback")}
            </Typography>
          ) : null}
          <StatRow
            label={`${family.adultes} ${adultWord}`}
            value={formatEuro(estimate.totalAdults)}
          />
          {family.enfants.length > 0 && (
            <StatRow
              label={`${family.enfants.length} ${childWord}`}
              value={formatEuro(estimate.totalChildren)}
            />
          )}
          {estimate.adhesion > 0 && (
            <StatRow
              label={te("adhesion")}
              value={formatEuro(estimate.adhesion)}
            />
          )}
          {estimate.activitiesTotal > 0 && (
            <StatRow
              label={te("activities")}
              value={formatEuro(estimate.activitiesTotal)}
            />
          )}
          {estimate.restoTotal > 0 && (
            <StatRow
              label={te("restoration")}
              value={formatEuro(estimate.restoTotal)}
            />
          )}
          {estimate.transportTotal > 0 && (
            <StatRow
              label={te("transport")}
              value={formatEuro(estimate.transportTotal)}
            />
          )}
          <Box
            sx={{
              borderTop: "1px solid rgba(0, 68, 90, 0.1)",
              mt: 0.5,
              pt: 0.75,
            }}
          >
            <StatRow
              label={te("totalEstimated")}
              value={`~${formatEuro(estimate.total)}`}
              highlight
            />
          </Box>
        </Box>
      ) : null}
    </VtfGlassCard>
  );
}
