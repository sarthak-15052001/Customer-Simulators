import * as React from "react";
import { Box } from "../ui";

import type { SejourState } from "../../types/stayTab";
import type { VtfSeasonKey } from "../../data/vtfExtras";
import { useRegionActivities } from "../../hooks/regionActivities.hooks";
import {
  filterPaidActivitiesBySeason,
  mapRegionActivitiesToFree,
  mapRegionActivitiesToPaid,
} from "../../utils/regionActivitiesMap";

import type { ExtrasTabProps } from "../../types/extrasTab";
import { clampInt, saisonKeyFromSejour } from "../../utils/extrasTab";
import { EstimateProgressCard } from "./extras/EstimateProgressCard";
import { IncludedActivitiesCard } from "./extras/IncludedActivitiesCard";
import { FreeOutingsCard } from "./extras/FreeOutingsCard";
import { PaidActivitiesCard } from "./extras/PaidActivitiesCard";
import { OutingsRecapCard } from "./extras/OutingsRecapCard";

export function ExtrasTab({
  family,
  sejour,
  village,
  onChange,
  serverEstimate,
  serverEstimateLoading = false,
  serverEstimateError = false,
  serverEstimateErrorMessage = null,
  onRetryEstimate,
}: ExtrasTabProps) {
  const patch = (partial: Partial<SejourState>) =>
    onChange({ ...sejour, ...partial });

  const region = village?.region?.trim() || null;
  const saisonKey =
    (sejour.serverSeasonKey as VtfSeasonKey) || saisonKeyFromSejour(sejour);
  // Dynamically prefer backend API infra payload data
  const villageInfra = village?.infra ?? null;

  const freeActivitiesQuery = useRegionActivities(region, {
    kind: "free",
    season: saisonKey,
  });
  const paidActivitiesQuery = useRegionActivities(region, {
    kind: "paid",
    season: saisonKey,
  });

  const freeList = React.useMemo(() => {
    if (!region) return [];
    if (freeActivitiesQuery.data !== undefined)
      return mapRegionActivitiesToFree(freeActivitiesQuery.data);
    return [];
  }, [region, freeActivitiesQuery.data]);

  const paidListRaw = React.useMemo(() => {
    if (!region) return [];
    if (paidActivitiesQuery.data !== undefined)
      return filterPaidActivitiesBySeason(
        mapRegionActivitiesToPaid(paidActivitiesQuery.data),
        saisonKey,
      );
    return [];
  }, [region, paidActivitiesQuery.data]);

  const freeActivitiesLoading =
    !!region &&
    freeActivitiesQuery.data === undefined &&
    freeActivitiesQuery.isPending;
  const paidActivitiesLoading =
    !!region &&
    paidActivitiesQuery.data === undefined &&
    paidActivitiesQuery.isPending;

  const freeActivitiesError = !!region && freeActivitiesQuery.isError;
  const paidActivitiesError = !!region && paidActivitiesQuery.isError;

  /** Hide included block until free/paid list requests have finished (success or error). */
  const anyActivitiesListLoading =
    !!region &&
    ((freeActivitiesQuery.data === undefined &&
      freeActivitiesQuery.isPending) ||
      (paidActivitiesQuery.data === undefined &&
        paidActivitiesQuery.isPending));

  const isWinter = saisonKey === "hs" || saisonKey === "fetes";
  const animKey: "ete" | "hiver" = isWinter ? "hiver" : "ete";

  const est = serverEstimate ?? null;

  const paidList = paidListRaw;

  const extraActivities = sejour.extraActivities ?? {
    freeQtyById: {},
    paidQtyById: {},
  };

  const setFreeQty = (id: string, qty: number) => {
    const nextQty = clampInt(qty, 0, 99);
    const next = { ...extraActivities.freeQtyById };
    if (nextQty <= 0) delete next[id];
    else next[id] = nextQty;
    patch({ extraActivities: { ...extraActivities, freeQtyById: next } });
  };

  const setPaidQty = (id: string, qty: number) => {
    const nextQty = clampInt(qty, 0, 99);
    const next = { ...extraActivities.paidQtyById };
    if (nextQty <= 0) delete next[id];
    else next[id] = nextQty;
    patch({ extraActivities: { ...extraActivities, paidQtyById: next } });
  };

  const paidTotal = est?.activitiesTotal ?? 0;

  const paidPlanned = React.useMemo(
    () =>
      Object.values(extraActivities.paidQtyById).reduce(
        (s, v) => s + (typeof v === "number" ? v : 0),
        0,
      ),
    [extraActivities.paidQtyById],
  );
  const freePlanned = React.useMemo(
    () =>
      Object.values(extraActivities.freeQtyById).reduce(
        (s, v) => s + (typeof v === "number" ? v : 0),
        0,
      ),
    [extraActivities.freeQtyById],
  );

  return (
    <Box className="vtf-tab-stack">
      {/* Récapitulatif du devis en cours */}
      <EstimateProgressCard
        family={family}
        sejour={sejour}
        village={village}
        estimate={est}
        estimateLoading={serverEstimateLoading}
        estimateError={serverEstimateError}
        estimateErrorMessage={serverEstimateErrorMessage}
        onRetryEstimate={onRetryEstimate}
      />

      {/* Activités incluses dans la formule */}
      {!anyActivitiesListLoading ? (
        <IncludedActivitiesCard
          sejour={sejour}
          villageInfra={villageInfra}
          animKey={animKey}
        />
      ) : null}

      {/* Sorties gratuites à proximité */}
      <FreeOutingsCard
        region={region}
        freeList={freeList}
        freeQtyById={extraActivities.freeQtyById}
        onToggle={(id) =>
          setFreeQty(id, (extraActivities.freeQtyById[id] ?? 0) > 0 ? 0 : 1)
        }
        onDec={(id) =>
          setFreeQty(
            id,
            Math.max(1, (extraActivities.freeQtyById[id] ?? 1) - 1),
          )
        }
        onInc={(id) =>
          setFreeQty(id, (extraActivities.freeQtyById[id] ?? 0) + 1)
        }
        freePlanned={freePlanned}
        isLoading={freeActivitiesLoading}
        loadError={freeActivitiesError}
        onRetry={() => freeActivitiesQuery.refetch()}
      />

      {/* Activités payantes avec prestataires */}
      <PaidActivitiesCard
        region={region}
        paidList={paidList}
        paidQtyById={extraActivities.paidQtyById}
        familyAdults={family.adultes}
        familyChildren={family.enfants.length}
        onToggle={(id) =>
          setPaidQty(id, (extraActivities.paidQtyById[id] ?? 0) > 0 ? 0 : 1)
        }
        onDec={(id) =>
          setPaidQty(
            id,
            Math.max(1, (extraActivities.paidQtyById[id] ?? 1) - 1),
          )
        }
        onInc={(id) =>
          setPaidQty(id, (extraActivities.paidQtyById[id] ?? 0) + 1)
        }
        paidTotal={paidTotal}
        isLoading={paidActivitiesLoading}
        loadError={paidActivitiesError}
        onRetry={() => paidActivitiesQuery.refetch()}
      />

      {/* Sommaire final des extras */}
      <OutingsRecapCard
        freePlanned={freePlanned}
        paidPlanned={paidPlanned}
        paidTotal={paidTotal}
      />
    </Box>
  );
}
