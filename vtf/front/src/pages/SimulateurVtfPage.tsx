/* eslint-disable @typescript-eslint/no-explicit-any */
import * as React from "react";
import { Box, useToast } from "../components/ui";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import type { FamilyState } from "../types/familyTab";
import type { SejourState } from "../types/stayTab";
import { useTranslation } from "../contexts/LanguageContext";

import { SimulateurTabsList } from "../components/simulateur-vtf/shared/SimulateurTabsList";
import { SimulateurVtfPageSkeleton } from "../components/simulateur-vtf/shared/SimulateurVtfPageSkeleton";
import {
  type SimulateurStep,
  type SimulateurStepKey,
} from "../components/simulateur-vtf/shared/SimulateurTabsList";

import { SimulateurStepFooter } from "../components/simulateur-vtf/shared/SimulateurStepFooter";
import { SimulateurHeader } from "../components/simulateur-vtf/shared/SimulateurHeader";
import { SimulateurStepContent } from "../components/simulateur-vtf/shared/SimulateurStepContent";

const DetailsTab = React.lazy(() =>
  import("../components/simulateur-vtf/DetailsTab").then((m) => ({
    default: m.DetailsTab,
  })),
);

import { useMarketingSeasons } from "../hooks/season.hooks";
import { pickCurrentSalesSeason } from "../api/season.api";
import { useSimulateurData } from "../hooks/useSimulateurData";
import {
  getInitialSimulatorState,
  hasSimulateurDraftInStorage,
  resetSimulateurDraft,
  saveSimulateurDraft,
} from "../utils/simulateurStateStorage";
import {
  computeFurthestUnlockedStep,
  stepStateFingerprint,
  validateSimulatorStep,
} from "../utils/simulateurStepValidation";
import {
  addDaysIso,
  pickQuickSearchStay,
} from "../utils/stayTab";

import PeopleAltRoundedIcon from "@mui/icons-material/PeopleAltRounded";
import HolidayVillageRoundedIcon from "@mui/icons-material/HolidayVillageRounded";
import AddCircleOutlineRoundedIcon from "@mui/icons-material/AddCircleOutlineRounded";
import RestaurantRoundedIcon from "@mui/icons-material/RestaurantRounded";
import DirectionsCarRoundedIcon from "@mui/icons-material/DirectionsCarRounded";
import LocalOfferRoundedIcon from "@mui/icons-material/LocalOfferRounded";
import EventNoteRoundedIcon from "@mui/icons-material/EventNoteRounded";
import SummarizeRoundedIcon from "@mui/icons-material/SummarizeRounded";

const STEP_ORDER: SimulateurStepKey[] = [
  "famille",
  "sejour",
  "extras",
  "resto",
  "transport",
  "promos",
  "planning",
  "details",
];

const PLANNING_STEP_INDEX = STEP_ORDER.indexOf("planning");

function isValidSimulatorStep(
  step: string | undefined,
): step is SimulateurStepKey {
  if (!step) return false;
  return STEP_ORDER.includes(step as SimulateurStepKey);
}

const STEP_ICONS: Record<SimulateurStepKey, React.ReactElement> = {
  famille: <PeopleAltRoundedIcon fontSize="small" />,
  sejour: <HolidayVillageRoundedIcon fontSize="small" />,
  extras: <AddCircleOutlineRoundedIcon fontSize="small" />,
  resto: <RestaurantRoundedIcon fontSize="small" />,
  transport: <DirectionsCarRoundedIcon fontSize="small" />,
  promos: <LocalOfferRoundedIcon fontSize="small" />,
  planning: <EventNoteRoundedIcon fontSize="small" />,
  details: <SummarizeRoundedIcon fontSize="small" />,
};

interface LocationState {
  autoSelectVillage?: {
    id: string;
    env: string;
  };
}

export default function SimulateurVtfPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { step: urlStep } = useParams<{ step: string }>();
  const { t } = useTranslation();
  const toast = useToast();

  const initialDraft = React.useMemo(() => getInitialSimulatorState(), []);
  const { data: globalMarketingSeasons } = useMarketingSeasons();

  const isDetailsView = urlStep === "details";
  const detailsStepIndex = STEP_ORDER.indexOf("details");

  const activeStep = React.useMemo(() => {
    if (!urlStep) return 0;
    const idx = STEP_ORDER.indexOf(urlStep as SimulateurStepKey);
    return idx === -1 ? 0 : idx;
  }, [urlStep]);

  const [family, setFamily] = React.useState<FamilyState>(
    () => initialDraft.family,
  );
  const [sejour, setSejour] = React.useState<SejourState>(
    () => initialDraft.sejour,
  );
  const [furthestUnlocked, setFurthestUnlocked] = React.useState(() =>
    computeFurthestUnlockedStep(initialDraft.family, initialDraft.sejour),
  );
  const stepEnterSnapshot = React.useRef("");

  React.useEffect(() => {
    saveSimulateurDraft(family, sejour);
  }, [family, sejour]);

  // Use modular data hook
  const {
    villages,
    isLoadingVillages,
    isVillagesError,
    villagesSearchInput,
    setVillagesSearchInput,
    villagesSearchDebounced,
    villagesPaging,
    selectedVillage,
    stayServerEstimate,
    isStayEstimateFetching,
    isStayEstimatePending,
    isStayEstimateError,
    stayEstimateErrorMessage,
    isStayEstimateInputDebouncing,
    refetchEstimate,
    refetchVillages,
  } = useSimulateurData({
    family,
    sejour,
    activeStep,
  });

  const steps = React.useMemo<SimulateurStep[]>(
    () =>
      STEP_ORDER.map((key) => ({
        key,
        label: t(`simulateur.tabs.${key}`),
        icon: STEP_ICONS[key],
      })),
    [t],
  );

  const lastIndex = steps.length - 1;

  const isStayEstimateLoading =
    isStayEstimateFetching ||
    isStayEstimatePending ||
    isStayEstimateInputDebouncing;
  const isStayEstimateFailed = isStayEstimateError && !stayServerEstimate;
  const step = steps[activeStep];

  const selectStep = React.useCallback(
    (index: number) => {
      const targetStep = STEP_ORDER[index];
      if (targetStep) navigate(`/simulateur-vtf/${targetStep}`);
    },
    [navigate],
  );

  const isCurrentStepDirty = React.useCallback(() => {
    const stepKey = STEP_ORDER[activeStep];
    if (!stepKey) return false;
    return (
      stepStateFingerprint(stepKey, family, sejour) !==
      stepEnterSnapshot.current
    );
  }, [activeStep, family, sejour]);

  React.useEffect(() => {
    if (isDetailsView) return;
    const stepKey = STEP_ORDER[activeStep];
    if (!stepKey) return;
    stepEnterSnapshot.current = stepStateFingerprint(stepKey, family, sejour);
  }, [activeStep, isDetailsView]);

  const tryNavigateStep = React.useCallback(
    (targetIndex: number, options?: { showSuccess?: boolean }) => {
      if (
        targetIndex === activeStep ||
        targetIndex < 0 ||
        targetIndex > lastIndex
      )
        return;

      const showSuccess = options?.showSuccess ?? targetIndex > activeStep;
      const currentKey = STEP_ORDER[activeStep];

      if (targetIndex < activeStep) {
        selectStep(targetIndex);
        return;
      }

      for (let i = activeStep; i < targetIndex; i++) {
        const stepKey = STEP_ORDER[i];
        if (!stepKey) continue;
        const validation = validateSimulatorStep(stepKey, family, sejour);
        if (!validation.valid) {
          toast.error(t(validation.messageKey));
          return;
        }
      }

      if (targetIndex <= furthestUnlocked || targetIndex === activeStep + 1) {
        if (targetIndex === activeStep + 1)
          setFurthestUnlocked((prev) => Math.max(prev, targetIndex));
        if (showSuccess && currentKey && isCurrentStepDirty()) {
          toast.success(
            t("simulateur.toast.stepSaved").replace(
              "{{step}}",
              steps[activeStep]?.label ?? "",
            ),
          );
        }
        selectStep(targetIndex);
        return;
      }

      toast.error(t("simulateur.validation.completePrevious"));
    },
    [
      activeStep,
      family,
      furthestUnlocked,
      isCurrentStepDirty,
      lastIndex,
      sejour,
      selectStep,
      steps,
      t,
      toast,
    ],
  );

  const resetSimulation = React.useCallback(() => {
    const fresh = resetSimulateurDraft();
    setFamily(fresh.family);
    setSejour(fresh.sejour);
    setFurthestUnlocked(0);
    navigate(`/simulateur-vtf/${STEP_ORDER[0]}`, { replace: true });
    window.scrollTo({ top: 0, behavior: "smooth" });
    toast.success(t("simulateur.toast.resetSimulation"));
  }, [navigate, t, toast]);

  const sessionRedirectPending = React.useRef(false);

  const redirectToFamilleWithoutDraft = React.useCallback(() => {
    const fresh = resetSimulateurDraft();
    setFamily(fresh.family);
    setSejour(fresh.sejour);
    setFurthestUnlocked(0);
    navigate(`/simulateur-vtf/${STEP_ORDER[0]}`, { replace: true });
    toast.info(t("simulateur.toast.sessionCleared"));
  }, [navigate, t, toast]);

  React.useLayoutEffect(() => {
    if (!urlStep || !isValidSimulatorStep(urlStep)) {
      navigate(`/simulateur-vtf/${STEP_ORDER[0]}`, { replace: true });
      return;
    }
    const stepIdx = STEP_ORDER.indexOf(urlStep as SimulateurStepKey);
    if (stepIdx > 0 && !hasSimulateurDraftInStorage()) {
      resetSimulateurDraft();
      sessionRedirectPending.current = true;
      navigate(`/simulateur-vtf/${STEP_ORDER[0]}`, { replace: true });
      return;
    }
    if ("scrollRestoration" in window.history)
      window.history.scrollRestoration = "manual";
    window.scrollTo(0, 0);
  }, [urlStep, navigate]);

  React.useEffect(() => {
    if (!sessionRedirectPending.current) return;
    sessionRedirectPending.current = false;
    setFurthestUnlocked(0);
    toast.info(t("simulateur.toast.sessionCleared"));
  }, [urlStep, t, toast]);

  React.useEffect(() => {
    const onStorageMissing = () => {
      if (activeStep > 0 && !hasSimulateurDraftInStorage()) {
        redirectToFamilleWithoutDraft();
      }
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") onStorageMissing();
    };
    window.addEventListener("storage", onStorageMissing);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("storage", onStorageMissing);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [activeStep, redirectToFamilleWithoutDraft]);

  React.useEffect(() => {
    const state = location.state as LocationState;
    const v = state?.autoSelectVillage as any;
    if (v && globalMarketingSeasons?.length) {
      if (setVillagesSearchInput) {
        setVillagesSearchInput(v.nom);
      }

      setTimeout(() => {
        const fallbackSeason = pickCurrentSalesSeason(globalMarketingSeasons);
        const { seasonKey, dateDebut: defaultDate, fEnv } = pickQuickSearchStay(
          v,
          globalMarketingSeasons,
          fallbackSeason?.key ?? "ete",
        );

        setSejour((prev) => ({
          ...prev,
          fSaison: seasonKey,
          dateDebut: defaultDate,
          dateFin: addDaysIso(defaultDate, prev.fNuits || 7),
          fEnv,
          villageId: v.id,
          formule: null,
          formuleFilter: "DP",
          mode: "village",
          attractionNom: null,
          attractionId: null,
        }));
        window.history.replaceState({}, document.title);
      }, 0);
    }
  }, [location.state, globalMarketingSeasons, setVillagesSearchInput]);

  return (
    <Box
      sx={{
        background:
          "linear-gradient(180deg, var(--vtf-cream) 0%, #ffffff 100%)",
        pb: { xs: 2, sm: 2.5 },
        minHeight: "calc(100vh - 160px)",
      }}
    >
      <Box className="mx-auto w-full max-w-[1120px] px-4 sm:px-6">
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            gap: { xs: 1.25, sm: 1.5 },
            pt: { xs: 1.5, sm: 2 },
          }}
        >
            <SimulateurHeader />

            {isDetailsView ? (
              <>
                <React.Suspense fallback={<SimulateurVtfPageSkeleton />}>
                  <DetailsTab
                    family={family}
                    sejour={sejour}
                    village={selectedVillage}
                    estimate={stayServerEstimate ?? null}
                    estimateLoading={isStayEstimateLoading}
                    estimateError={isStayEstimateFailed}
                    estimateErrorMessage={stayEstimateErrorMessage}
                    onRetryEstimate={() => void refetchEstimate()}
                    onBack={() =>
                      navigate(
                        `/simulateur-vtf/${STEP_ORDER[PLANNING_STEP_INDEX]}`,
                        { replace: true },
                      )
                    }
                    onReset={resetSimulation}
                    steps={steps}
                    activeStepIndex={detailsStepIndex}
                    maxEnabledIndex={lastIndex}
                    onTabChange={tryNavigateStep}
                  />
                </React.Suspense>
              </>
            ) : (
              <>
                <SimulateurTabsList
                  steps={steps}
                  activeIndex={activeStep}
                  maxEnabledIndex={furthestUnlocked}
                  onChange={tryNavigateStep}
                />

                <SimulateurStepContent
                  step={step}
                  family={family}
                  setFamily={setFamily}
                  sejour={sejour}
                  setSejour={setSejour}
                  villages={villages}
                  isLoadingVillages={isLoadingVillages}
                  isVillagesError={isVillagesError}
                  refetchVillages={refetchVillages}
                  villagesSearchInput={villagesSearchInput}
                  setVillagesSearchInput={setVillagesSearchInput}
                  villagesSearchDebounced={villagesSearchDebounced}
                  selectedVillage={selectedVillage}
                  stayServerEstimate={stayServerEstimate}
                  isStayEstimateLoading={isStayEstimateLoading}
                  isStayEstimateError={isStayEstimateFailed}
                  stayEstimateErrorMessage={stayEstimateErrorMessage}
                  onRetryEstimate={() => void refetchEstimate()}
                  villagesPaging={villagesPaging}
                />

                <SimulateurStepFooter
                  onPrevious={() =>
                    activeStep > 0 &&
                    tryNavigateStep(activeStep - 1, { showSuccess: false })
                  }
                  onNext={() =>
                    activeStep < lastIndex && tryNavigateStep(activeStep + 1)
                  }
                  disablePrevious={activeStep <= 0}
                  disableNext={activeStep >= lastIndex}
                  previousLabel={t("simulateur.nav.previous")}
                  nextLabel={t("simulateur.nav.next")}
                  family={family}
                  sejour={sejour}
                  village={selectedVillage}
                  serverEstimate={stayServerEstimate ?? null}
                  serverEstimateLoading={isStayEstimateLoading}
                  serverEstimateError={isStayEstimateFailed}
                  serverEstimateErrorMessage={stayEstimateErrorMessage}
                  onRetryEstimate={() => void refetchEstimate()}
                />
              </>
            )}
        </Box>
      </Box>
    </Box>
  );
}
