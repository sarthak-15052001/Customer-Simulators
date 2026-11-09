import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

import villageApi, { type VillageQueryParams } from "../api/village.api";
import type { PaginatedResponse } from "../types/api";
import type { VtfVillage } from "../data/vtfStay";

/**
 * Fetch villages list (`GET /villages`).
 */
export const useVillages = (
  queryParams?: VillageQueryParams,
  options?: Partial<UseQueryOptions<PaginatedResponse<VtfVillage>>>,
) => {
  return useQuery({
    queryKey: ["villages", queryParams],
    queryFn: () => villageApi.getVillages(queryParams),
    ...options,
  });
};

/** Resolves a selected village when it is not in the current paginated list (e.g. details refresh). */
export function useVillageById(
  villageId: string | null | undefined,
  params?: {
    dateDebut?: string | null;
    dateFin?: string | null;
    formule?: string | null;
  },
  options?: Partial<UseQueryOptions<VtfVillage>> & { enabled?: boolean },
) {
  const { enabled = true, ...queryOptions } = options ?? {};
  const queryParams =
    params?.dateDebut || params?.formule
      ? {
          ...(params.dateDebut
            ? {
                openOn: params.dateDebut,
                dateDebut: params.dateDebut,
              }
            : {}),
          ...(params.dateFin ? { dateFin: params.dateFin } : {}),
          ...(params.formule ? { formule: params.formule } : {}),
        }
      : undefined;

  return useQuery({
    queryKey: ["village", villageId, queryParams],
    queryFn: () => villageApi.getVillageById(villageId!, queryParams),
    enabled: Boolean(villageId && enabled),
    staleTime: 10 * 60 * 1000,
    ...queryOptions,
  });
}
