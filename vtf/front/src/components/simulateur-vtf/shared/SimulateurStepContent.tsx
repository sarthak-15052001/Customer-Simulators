import * as React from "react";
import { Box, Card, CardContent, Typography } from "../../ui";
import { useTranslation } from "../../../contexts/LanguageContext";
import type { FamilyState } from "../../../types/familyTab";
import type { SejourState } from "../../../types/stayTab";
import type { SimulateurStep } from "./SimulateurTabsList";
import { SimulateurVtfPageSkeleton } from "./SimulateurVtfPageSkeleton";
import type { VtfVillage } from "../../../data/vtfStay";
import type { StayEstimateApiResult } from "../../../api/stayEstimate.api";

const FamilyTab = React.lazy(() =>
  import("../FamilyTab").then((m) => ({
    default: m.FamilyTab,
  })),
);
const StayTab = React.lazy(() =>
  import("../StayTab").then((m) => ({
    default: m.StayTab,
  })),
);
const ExtrasTab = React.lazy(() =>
  import("../ExtrasTab").then((m) => ({
    default: m.ExtrasTab,
  })),
);
const RestoTab = React.lazy(() =>
  import("../RestoTab").then((m) => ({
    default: m.RestoTab,
  })),
);
const TransportTab = React.lazy(() =>
  import("../TransportTab").then((m) => ({
    default: m.TransportTab,
  })),
);
const PromosTab = React.lazy(() =>
  import("../PromosTab").then((m) => ({
    default: m.PromosTab,
  })),
);
const PlanningTab = React.lazy(() =>
  import("../PlanningTab").then((m) => ({
    default: m.PlanningTab,
  })),
);

interface SimulateurStepContentProps {
  step: SimulateurStep | undefined;
  family: FamilyState;
  setFamily: React.Dispatch<React.SetStateAction<FamilyState>>;
  sejour: SejourState;
  setSejour: React.Dispatch<React.SetStateAction<SejourState>>;
  villages: VtfVillage[];
  isLoadingVillages: boolean;
  isVillagesError: boolean;
  refetchVillages: () => void;
  villagesSearchInput: string;
  setVillagesSearchInput: (value: string) => void;
  villagesSearchDebounced: string;
  villagesPaging?: {
    totalCount: number;
    pageSize: number;
    offset: number;
    onOffsetChange: (next: number) => void;
  };
  selectedVillage: VtfVillage | null;
  stayServerEstimate: StayEstimateApiResult | null | undefined;
  isStayEstimateLoading?: boolean;
  isStayEstimateError?: boolean;
  stayEstimateErrorMessage?: string | null;
  onRetryEstimate?: () => void;
}

export const SimulateurStepContent: React.FC<SimulateurStepContentProps> = ({
  step,
  family,
  setFamily,
  sejour,
  setSejour,
  villages,
  isLoadingVillages,
  isVillagesError,
  refetchVillages,
  villagesSearchInput,
  setVillagesSearchInput,
  villagesSearchDebounced,
  villagesPaging,
  selectedVillage,
  stayServerEstimate,
  isStayEstimateLoading = false,
  isStayEstimateError = false,
  stayEstimateErrorMessage = null,
  onRetryEstimate,
}) => {
  const { t } = useTranslation();

  return (
    <Box sx={{ width: "100%" }}>
      <React.Suspense fallback={<SimulateurVtfPageSkeleton />}>
        {step?.key === "famille" ? (
          <FamilyTab value={family} onChange={setFamily} />
        ) : step?.key === "sejour" ? (
          <StayTab
            value={sejour}
            villages={villages}
            isLoading={isLoadingVillages}
            isVillagesError={isVillagesError}
            refetchVillages={refetchVillages}
            resultsSearchInput={villagesSearchInput}
            resultsSearchDebounced={villagesSearchDebounced}
            onResultsSearchInputChange={setVillagesSearchInput}
            onResetResultsSearch={() => setVillagesSearchInput("")}
            villagesPaging={villagesPaging}
            onChange={setSejour}
          />
        ) : step?.key === "extras" ? (
          <ExtrasTab
            family={family}
            sejour={sejour}
            village={selectedVillage}
            onChange={setSejour}
            serverEstimate={stayServerEstimate ?? null}
            serverEstimateLoading={isStayEstimateLoading}
            serverEstimateError={isStayEstimateError}
            serverEstimateErrorMessage={stayEstimateErrorMessage}
            onRetryEstimate={onRetryEstimate}
          />
        ) : step?.key === "resto" ? (
          <RestoTab
            family={family}
            sejour={sejour}
            village={selectedVillage}
            serverEstimate={stayServerEstimate ?? null}
            serverEstimateLoading={isStayEstimateLoading}
            onChange={setSejour}
          />
        ) : step?.key === "transport" ? (
          <TransportTab
            family={family}
            sejour={sejour}
            village={selectedVillage}
            onChange={setSejour}
          />
        ) : step?.key === "promos" ? (
          <PromosTab
            family={family}
            sejour={sejour}
            village={selectedVillage}
            onChange={setSejour}
            onFamilyChange={setFamily}
            serverEstimate={stayServerEstimate ?? null}
          />
        ) : step?.key === "planning" ? (
          <PlanningTab
            family={family}
            sejour={sejour}
            village={selectedVillage}
            onChange={setSejour}
          />
        ) : (
          <Card
            className="rounded-3xl border-0 shadow-2xl shadow-slate-200/50"
            sx={{ background: "white" }}
          >
            <CardContent className="p-12 text-center">
              <Box className="mx-auto w-16 h-16 rounded-2xl bg-vtf-cream flex items-center justify-center mb-6">
                {step?.icon}
              </Box>
              <Typography
                variant="h5"
                sx={{
                  fontWeight: 900,
                  color: "var(--vtf-navy)",
                  mb: 2,
                }}
              >
                {step?.label}
              </Typography>
              <Typography
                sx={{
                  color: "text.secondary",
                  fontWeight: 500,
                  fontSize: 'var(--vtf-font-md)',
                  maxWidth: 400,
                  mx: "auto",
                }}
              >
                {t("simulateur.stepSoon")}
              </Typography>
            </CardContent>
          </Card>
        )}
      </React.Suspense>
    </Box>
  );
};
