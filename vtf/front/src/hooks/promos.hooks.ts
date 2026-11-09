import { useQuery } from "@tanstack/react-query";
import promosApi, { type AvailablePromosInput } from "../api/promos.api";
import type { PromoChoice } from "../data/vtfPromos";

export function usePromoCatalog() {
  return useQuery<PromoChoice[]>({
    queryKey: ["promos", "catalog"],
    queryFn: () => promosApi.fetchPromoCatalog(),
    staleTime: 15 * 60 * 1000, // 15 minutes
  });
}

/** Fetches eligible promos for the current stay (dates + village). */
export function useAvailablePromos(
  input: AvailablePromosInput | null,
  enabled = true,
) {
  const hasDates = Boolean(input?.dateDebut && input?.dateFin);
  const hasVillage = Boolean(input?.villageId);

  return useQuery<PromoChoice[]>({
    queryKey: [
      "promos",
      "available",
      input?.dateDebut ?? "",
      input?.dateFin ?? "",
      input?.villageId ?? "",
      String(input?.quinzaineFutee ?? false),
      String(input?.isSoloParent ?? false),
    ],
    queryFn: () =>
      promosApi.computeAvailablePromos({
        dateDebut: input!.dateDebut,
        dateFin: input!.dateFin,
        villageId: input!.villageId,
        isSoloParent: Boolean(input!.isSoloParent),
        quinzaineFutee: Boolean(input!.quinzaineFutee),
      }),
    enabled: enabled && hasDates && hasVillage,
    staleTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}
