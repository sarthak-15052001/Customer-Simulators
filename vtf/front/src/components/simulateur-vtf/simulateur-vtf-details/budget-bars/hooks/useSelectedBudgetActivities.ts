import * as React from "react";
import type { VtfSeasonKey } from "../../../../../data/vtfExtras";
import { useRegionActivities } from "../../../../../hooks/regionActivities.hooks";
import {
  filterPaidActivitiesBySeason,
  mapRegionActivitiesToFree,
  mapRegionActivitiesToPaid,
} from "../../../../../utils/regionActivitiesMap";

export function useSelectedBudgetActivities(args: {
  region: string | null;
  saisonKey: VtfSeasonKey;
  freeQtyById: Record<string, number>;
  paidQtyById: Record<string, number>;
}) {
  const { region, saisonKey, freeQtyById, paidQtyById } = args;

  const freeQuery = useRegionActivities(region, {
    kind: "free",
    season: saisonKey,
  });
  const paidQuery = useRegionActivities(region, {
    kind: "paid",
    season: saisonKey,
  });

  const freeCatalog = React.useMemo(
    () =>
      freeQuery.data ? mapRegionActivitiesToFree(freeQuery.data) : [],
    [freeQuery.data],
  );

  const paidCatalog = React.useMemo(() => {
    if (!paidQuery.data) return [];
    return filterPaidActivitiesBySeason(
      mapRegionActivitiesToPaid(paidQuery.data),
      saisonKey,
    );
  }, [paidQuery.data, saisonKey]);

  const selectedFree = React.useMemo(
    () => freeCatalog.filter((a) => (freeQtyById[a.id] ?? 0) > 0),
    [freeCatalog, freeQtyById],
  );

  const selectedPaid = React.useMemo(
    () => paidCatalog.filter((a) => (paidQtyById[a.id] ?? 0) > 0),
    [paidCatalog, paidQtyById],
  );

  const hasSelection = selectedFree.length > 0 || selectedPaid.length > 0;

  const isLoading =
    hasSelection &&
    ((freeQuery.isPending && selectedFree.length > 0) ||
      (paidQuery.isPending && selectedPaid.length > 0));

  return {
    selectedFree,
    selectedPaid,
    hasSelection,
    isLoading,
    freeQtyById,
    paidQtyById,
  };
}

export type SelectedBudgetActivities = ReturnType<
  typeof useSelectedBudgetActivities
>;
