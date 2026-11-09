import * as React from "react";
import { Box, Button } from "../ui";
import KeyboardArrowLeftRoundedIcon from "@mui/icons-material/KeyboardArrowLeftRounded";
import RestartAltRoundedIcon from "@mui/icons-material/RestartAltRounded";
import {
  SimulateurTabsList,
  type SimulateurStep,
} from "./shared/SimulateurTabsList";

import { RecapSummaryCard } from "./simulateur-vtf-details/RecapSummaryCard";
import { ComparatorCard } from "./simulateur-vtf-details/ComparatorCard";
import { BudgetBarsCard } from "./simulateur-vtf-details/budget-bars";
import { CtaActionsCard } from "./simulateur-vtf-details/CtaActionsCard";
import { PlanningAccordionCard } from "./simulateur-vtf-details/PlanningAccordionCard";
import { DetailsTabSkeleton } from "./simulateur-vtf-details/DetailsTabSkeleton";
import { DetailsEstimateErrorState } from "./simulateur-vtf-details/DetailsEstimateErrorState";
import { getStayDays } from "../../utils/planningTab";

import type { FamilyState } from "../../types/familyTab";
import type { SejourState } from "../../types/stayTab";
import type { VtfVillage } from "../../data/vtfStay";
import type { StayEstimateApiResult } from "../../api/stayEstimate.api";
import { useTranslation } from "../../contexts/LanguageContext";
import {
  buildVtfBookingUrl,
  isVtfVillageBookingUrl,
} from "../../utils/vtfBookingUrl";
import { saisonKeyFromSejour } from "../../utils/extrasTab";
import { useSimulationPdfDownload } from "../../hooks/useSimulationPdfDownload";

export function DetailsTab({
  family,
  sejour,
  village,
  estimate,
  estimateLoading = false,
  estimateError = false,
  estimateErrorMessage = null,
  onRetryEstimate,
  onBack,
  onReset,
  steps,
  activeStepIndex,
  maxEnabledIndex,
  onTabChange,
}: {
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
  estimate: StayEstimateApiResult | null;
  estimateLoading?: boolean;
  estimateError?: boolean;
  estimateErrorMessage?: string | null;
  onRetryEstimate?: () => void;
  onBack: () => void;
  onReset: () => void;
  steps: SimulateurStep[];
  activeStepIndex: number;
  maxEnabledIndex: number;
  onTabChange: (index: number) => void;
}) {
  const { t, language } = useTranslation();

  const bookingUrl = React.useMemo(
    () =>
      buildVtfBookingUrl(
        village,
        family,
        sejour.dateDebut,
        sejour.dateFin,
        estimate?.saisonKey ?? sejour.serverSeasonKey ?? saisonKeyFromSejour(sejour),
        language,
      ),
    [village, family, sejour, estimate?.saisonKey, language],
  );

  const bookingUrlReady = isVtfVillageBookingUrl(bookingUrl);

  const days = React.useMemo(
    () => getStayDays(sejour.dateDebut, sejour.dateFin),
    [sejour.dateDebut, sejour.dateFin],
  );

  const showEstimateSkeleton = estimateLoading;
  const showEstimateError = estimateError && !estimateLoading && !estimate;

  const { downloadPdf, isDownloading } = useSimulationPdfDownload({
    family,
    sejour,
    village,
    estimate,
    bookingUrl,
    disabled: !estimate || showEstimateSkeleton || showEstimateError,
  });

  return (
    <>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <SimulateurTabsList
          steps={steps}
          activeIndex={activeStepIndex}
          maxEnabledIndex={maxEnabledIndex}
          onChange={onTabChange}
        />
        <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
          {showEstimateSkeleton ? (
            <DetailsTabSkeleton />
          ) : showEstimateError ? (
            <DetailsEstimateErrorState
              onRetry={onRetryEstimate}
              errorMessage={estimateErrorMessage}
            />
          ) : estimate ? (
            <>
              <RecapSummaryCard
                family={family}
                sejour={sejour}
                village={village}
                estimate={estimate}
              />
              <BudgetBarsCard
                estimate={estimate}
                family={family}
                sejour={sejour}
                village={village}
              />
              <ComparatorCard estimate={estimate} />
              <PlanningAccordionCard
                sejour={sejour}
                village={village}
                days={days}
              />
              <CtaActionsCard
                family={family}
                sejour={sejour}
                village={village}
                estimate={estimate}
                bookingUrl={bookingUrl}
                bookingUrlReady={bookingUrlReady}
                onDownloadPdf={downloadPdf}
                pdfDownloading={isDownloading}
                pdfDisabled={!estimate}
              />
            </>
          ) : null}

          {!showEstimateSkeleton && (
            <Box
              component="nav"
              aria-label={t("simulateur.nav.ariaLabel")}
              className="vtf-glass-strong rounded-3xl"
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                p: { xs: 1.5, sm: 1.75 },
                mt: 1,
                mb: 4,
                border: "1px solid rgba(0, 68, 90, 0.08)",
                boxShadow: "0 18px 40px rgba(15, 23, 42, 0.08)",
              }}
            >
              <Button
                type="button"
                variant="text"
                vtfVariant="stepPrevious"
                onClick={() => {
                  window.scrollTo({ top: 0, behavior: "smooth" });
                  onBack();
                }}
                startIcon={<KeyboardArrowLeftRoundedIcon />}
                sx={{
                  minWidth: { xs: 140, sm: 160 },
                  width: "auto",
                  flexShrink: 0,
                }}
              >
                {t("simulateur.details.page.edit")}
              </Button>
              <Button
                type="button"
                variant="contained"
                vtfVariant="stepNext"
                onClick={onReset}
                endIcon={<RestartAltRoundedIcon />}
                sx={{
                  minWidth: { xs: 160, sm: 220 },
                  width: "auto",
                  flexShrink: 0,
                }}
              >
                {t("simulateur.nav.resetSimulation")}
              </Button>
            </Box>
          )}
        </Box>
      </Box>
    </>
  );
}
