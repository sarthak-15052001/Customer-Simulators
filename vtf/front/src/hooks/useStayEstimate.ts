import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import * as React from "react";

import {
  buildEstimateStayRequestBody,
  stayEstimateApi,
  type EstimateStayRequestBody,
  type StayEstimateApiResult,
} from "../api/stayEstimate.api";
import type { FamilyState } from "../types/familyTab";
import type { SejourState } from "../types/stayTab";
import { useDebouncedValue } from "./useDebouncedValue";

/** Délai avant `POST /estimate/stay` (pour les curseurs / modifications rapides). */
const ESTIMATE_STAY_DEBOUNCE_MS = 400;

type Args = {
  family: FamilyState;
  sejour: SejourState;
  /** Barrière : on ne récupère les données que si l'utilisateur a choisi un village et que les dates sont valides. */
  enabled?: boolean;
};

/**
 * Calcul du total du séjour côté serveur (`POST /api/v1/estimate/stay`).
 * Se relance quand la famille ou un champ du séjour influençant le calcul change (avec délai).
 */
export function useStayEstimate(
  { family, sejour, enabled = true }: Args,
  options?: Partial<UseQueryOptions<StayEstimateApiResult, Error>>,
) {
  const childAgesKey = family.enfants.map((e) => e.age).join("|");
  const paidExtrasKey = JSON.stringify(
    sejour.extraActivities?.paidQtyById ?? {},
  );
  const restoKey = JSON.stringify(sejour.resto);
  const transportKey = JSON.stringify(sejour.transport);
  const promosKey = JSON.stringify(sejour.promos);

  const requestBody = React.useMemo(
    () =>
      buildEstimateStayRequestBody({
        villageId: sejour.villageId,
        family,
        sejour,
      }),
    [
      family.adultes,
      childAgesKey,
      family.qfVal,
      family.maxiFamily,
      sejour.villageId,
      sejour.dateDebut,
      sejour.dateFin,
      sejour.fNuits,
      sejour.formule,
      paidExtrasKey,
      restoKey,
      transportKey,
      promosKey,
    ],
  );

  const bodyKey = requestBody ? JSON.stringify(requestBody) : "";
  const debouncedBodyKey = useDebouncedValue(
    bodyKey,
    ESTIMATE_STAY_DEBOUNCE_MS,
  );

  const debouncedBody = React.useMemo((): EstimateStayRequestBody | null => {
    if (!debouncedBodyKey) return null;
    try {
      return JSON.parse(debouncedBodyKey) as EstimateStayRequestBody;
    } catch {
      return null;
    }
  }, [debouncedBodyKey]);

  const queryEnabled = Boolean(
    enabled && debouncedBody && debouncedBody.villageId === sejour.villageId,
  );

  const isInputDebouncing = bodyKey !== debouncedBodyKey;

  const query = useQuery({
    queryKey: ["estimate-stay", debouncedBodyKey],
    queryFn: () => stayEstimateApi.postEstimateStay(debouncedBody!),
    enabled: queryEnabled,
    staleTime: 60_000,
    retry: 1,
    ...options,
  });

  return { ...query, isInputDebouncing };
}
