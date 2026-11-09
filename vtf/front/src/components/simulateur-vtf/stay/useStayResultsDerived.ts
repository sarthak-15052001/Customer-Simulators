import * as React from "react";
import type { VtfFormule, VtfVillage } from "../../../data/vtfStay";
import type { SejourEnvKey } from "../../../utils/stayTab";
import { dateToSaisonIdx } from "../../../utils/stayTab";
import type { Attraction } from "../../../api/attraction.api";
import {
  attractionMatchesResultsSearch,
  normalizeResultsSearch,
  type VillagesPaging,
  villageMatchesResultsSearch,
  type MergedAttraction,
} from "./stayResultsCardModel";

type ValueSlice = {
  dateDebut: string | null;
  fEnv: SejourEnvKey | null;
  formule: VtfFormule | null;
  attractionNom: string | null;
};

export function useStayResultsDerived(args: {
  value: ValueSlice;
  villages: VtfVillage[];
  attractions: Attraction[];
  villagesPaging?: VillagesPaging;
  resultsSearchDebounced: string;
}) {
  const {
    value,
    villages,
    attractions,
    resultsSearchDebounced,
  } = args;

  const searchQNorm = React.useMemo(
    () => normalizeResultsSearch(resultsSearchDebounced),
    [resultsSearchDebounced],
  );

  const allAttractions = React.useMemo((): MergedAttraction[] => {
    return attractions.map((a) => ({
      id: a.id,
      nom: a.nom,
      type: a.type,
      icon: a.icon,
      minKm: a.minKm,
    }));
  }, [attractions]);

  const displayVillageItems = villages;

  const isVillageListEmpty = villages.length === 0;

  const displayAttractions = React.useMemo(
    () =>
      allAttractions.filter((a) =>
        attractionMatchesResultsSearch(a, searchQNorm),
      ),
    [allAttractions, searchQNorm],
  );

  const displayActivityVillages = React.useMemo(
    () =>
      villages.filter((v) =>
        villageMatchesResultsSearch(v, searchQNorm),
      ),
    [villages, searchQNorm],
  );

  const saisonIdx = dateToSaisonIdx(value.dateDebut);

  return {
    searchQNorm,
    displayVillageItems,
    isVillageListEmpty,
    displayAttractions,
    displayActivityVillages,
    saisonIdx,
  };
}
