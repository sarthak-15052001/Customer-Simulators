import * as React from "react";
import { useVillageById, useVillages } from "./village.hooks";
import { useStayEstimate } from "./useStayEstimate";
import { useDebouncedValue } from "./useDebouncedValue";
import { buildVillagesListQueryParams } from "../utils/villageListQuery";
import type { FamilyState } from "../types/familyTab";
import type { SejourState } from "../types/stayTab";

import { extractErrorMessage } from "../utils/stayEstimate";

const VILLAGES_API_LIMIT = 5;

const VILLAGES_SEARCH_DEBOUNCE_MS = 400;

interface UseSimulateurDataArgs {
  family: FamilyState;
  sejour: SejourState;
  activeStep: number;
}

export function useSimulateurData({
  family,
  sejour,
  activeStep,
}: UseSimulateurDataArgs) {
  // Gestion de la recherche textuelle des villages avec délai (debounce)
  const [villagesSearchInput, setVillagesSearchInput] = React.useState("");
  const villagesSearchDebounced = useDebouncedValue(
    villagesSearchInput,
    VILLAGES_SEARCH_DEBOUNCE_MS,
  );

  const villagesFilterKey = `${sejour.fEnv ?? ""}|${sejour.formuleFilter ?? ""}|${sejour.dateDebut ?? ""}|${sejour.dateFin ?? ""}|${sejour.regionFilter ?? ""}|${sejour.attractionId ?? ""}|${villagesSearchDebounced}`;
  const [villagesOffsetByFilter, setVillagesOffsetByFilter] = React.useState<
    Record<string, number>
  >({});
  const villagesOffset = villagesOffsetByFilter[villagesFilterKey] ?? 0;

  const setVillagesOffset = React.useCallback(
    (next: number) => {
      setVillagesOffsetByFilter((prev) => ({
        ...prev,
        [villagesFilterKey]: next,
      }));
    },
    [villagesFilterKey],
  );

  const villagesPayload = React.useMemo(() => {
    if (!sejour.fEnv) return {};
    return buildVillagesListQueryParams({
      fEnv: sejour.fEnv,
      formule: sejour.formuleFilter ?? null,
      dateDebut: sejour.dateDebut,
      dateFin: sejour.dateFin,
      limit: VILLAGES_API_LIMIT,
      offset: villagesOffset,
      region: sejour.regionFilter?.trim() || null,
      search: villagesSearchDebounced.trim() || null,
      attractionId: sejour.attractionId || null,
    });
  }, [
    sejour.fEnv,
    sejour.formuleFilter,
    sejour.dateDebut,
    sejour.dateFin,
    sejour.regionFilter,
    sejour.attractionId,
    villagesOffset,
    villagesSearchDebounced,
  ]);

  const {
    data: villagesData,
    isLoading: isLoadingVillages,
    isError: isVillagesError,
    refetch: refetchVillages,
  } = useVillages(villagesPayload, {
    enabled:
      sejour.fEnv != null &&
      (activeStep >= 1 || Boolean(sejour.villageId)),
  });

  const villages = React.useMemo(
    () => villagesData?.results ?? [],
    [villagesData?.results],
  );

  const selectedFromList = React.useMemo(
    () =>
      sejour.villageId
        ? (villages.find((v) => v.id === sejour.villageId) ?? null)
        : null,
    [sejour.villageId, villages],
  );

  // The detail call prioritizes the active list filter (formuleFilter), falling back to the selected quote formula (formule).
  const villageByIdParams = React.useMemo(
    () => ({
      dateDebut: sejour.dateDebut,
      dateFin: sejour.dateFin,
      formule: sejour.formuleFilter ?? sejour.formule ?? null,
    }),
    [sejour.dateDebut, sejour.dateFin, sejour.formuleFilter, sejour.formule],
  );

  const { data: villageById, isFetching: isVillageDetailFetching } =
    useVillageById(sejour.villageId, villageByIdParams, {
      enabled: Boolean(sejour.villageId && sejour.fEnv),
    });

  const selectedVillage = React.useMemo(() => {
    if (villageById && selectedFromList?.id === villageById.id) {
      return { ...selectedFromList, ...villageById };
    }
    return villageById ?? selectedFromList ?? null;
  }, [selectedFromList, villageById]);

  const stayEstimateResult = useStayEstimate(
    { family, sejour, enabled: !!sejour.fSaison },
    { refetchOnWindowFocus: false },
  );

  const canEstimateStay = Boolean(sejour.villageId && sejour.formule);

  const villagesPaging = React.useMemo(() => {
    if (sejour.fEnv == null) return undefined;
    return {
      totalCount: villagesData?.count ?? 0,
      pageSize: VILLAGES_API_LIMIT,
      offset: villagesOffset,
      onOffsetChange: setVillagesOffset,
    };
  }, [sejour.fEnv, villagesData?.count, villagesOffset, setVillagesOffset]);

  return {
    villages,
    isLoadingVillages,
    isVillagesError,
    refetchVillages,
    villagesSearchInput,
    setVillagesSearchInput,
    villagesSearchDebounced,
    villagesPaging,
    selectedVillage,
    isVillageDetailFetching,
    stayServerEstimate: canEstimateStay ? (stayEstimateResult.data ?? null) : null,
    isStayEstimateFetching: canEstimateStay ? stayEstimateResult.isFetching : false,
    isStayEstimatePending: canEstimateStay ? stayEstimateResult.isPending : false,
    isStayEstimateError: canEstimateStay ? stayEstimateResult.isError : false,
    stayEstimateError: canEstimateStay ? stayEstimateResult.error : null,
    stayEstimateErrorMessage: canEstimateStay
      ? extractErrorMessage(stayEstimateResult.error)
      : null,
    isStayEstimateInputDebouncing: canEstimateStay
      ? stayEstimateResult.isInputDebouncing
      : false,
    refetchEstimate: stayEstimateResult.refetch,
  };
}
