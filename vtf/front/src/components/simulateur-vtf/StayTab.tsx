import { Box } from "../ui";
import type { SejourTabProps } from "../../types/stayTab";
import type { VtfVillage } from "../../data/vtfStay";
import {
  addDaysIso,
  isVillageOuvert,
  todayIsoLocal,
} from "../../utils/stayTab";
import {
  type MarketingSeason,
  pickCurrentSalesSeason,
} from "../../api/season.api";
import * as React from "react";
import { StaySeasonCard } from "./stay/StaySeasonCard";
import { StayNightsCard } from "./stay/StayNightsCard";
import { StayEnvironmentCard } from "./stay/StayEnvironmentCard";
import { StayResultsCard } from "./stay/StayResultsCard";
import { StayFormuleCard } from "./stay/StayFormuleCard";
import { useMarketingSeasons, useSeasons } from "../../hooks/season.hooks";
import { StaySeasonCardSkeleton } from "./stay/StaySeasonCardSkeleton";
import { StaySeasonDetailsSkeleton } from "./stay/StaySeasonDetailsSkeleton";
import { useTranslation } from "../../contexts/LanguageContext";
import { VtfErrorAlert } from "../shared/VtfErrorAlert";
import { useToast } from "../ui";
import { funnelSaisonKeyForRecap } from "../../utils/extrasTab";

interface StayTabProps extends SejourTabProps {
  villages: VtfVillage[];
  isLoading?: boolean;
  isVillagesError?: boolean;
  refetchVillages?: () => void;
  resultsSearchInput: string;
  resultsSearchDebounced: string;
  onResultsSearchInputChange: (value: string) => void;
  onResetResultsSearch: () => void;
  villagesPaging?: {
    totalCount: number;
    pageSize: number;
    offset: number;
    onOffsetChange: (nextOffset: number) => void;
  };
}

export function StayTab({
  value,
  villages,
  isLoading,
  resultsSearchInput,
  resultsSearchDebounced,
  onResultsSearchInputChange,
  onResetResultsSearch,
  villagesPaging,
  onChange,
  isVillagesError,
  refetchVillages,
}: StayTabProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const pendingPricingSeasonToast = React.useRef(false);
  const requestDate = value.dateDebut || todayIsoLocal();
  const {
    data: seasonsData,
    isLoading: isLoadingSeasons,
    isError: isSeasonsError,
    refetch: refetchSeasons,
  } = useSeasons(requestDate, !!value.fSaison);
  const {
    data: marketingSeasons,
    isLoading: isLoadingMarketingSeasons,
    isError: isMarketingSeasonsError,
    refetch: refetchMarketingSeasons,
  } = useMarketingSeasons();

  const patch = (partial: Partial<typeof value>) =>
    onChange({ ...value, ...partial });

  React.useEffect(() => {
    if (!marketingSeasons?.length || value.fSaison) return;

    const defaultSeason = pickCurrentSalesSeason(marketingSeasons);
    if (!defaultSeason) return;

    const defaultDate =
      typeof defaultSeason.defaultDate === "string" &&
      /^\d{4}-\d{2}-\d{2}$/.test(defaultSeason.defaultDate)
        ? defaultSeason.defaultDate
        : todayIsoLocal();

    onChange({
      ...value,
      fSaison: defaultSeason.key,
      dateDebut: defaultDate,
      dateFin: addDaysIso(defaultDate, value.fNuits),
      serverSeasonKey: null,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [marketingSeasons, value.fSaison]);

  React.useEffect(() => {
    if (!seasonsData?.saisonKey) return;
    const nextKey = seasonsData.saisonKey;
    if (nextKey === value.serverSeasonKey) {
      pendingPricingSeasonToast.current = false;
      return;
    }
    const prevKey = value.serverSeasonKey;
    onChange({ ...value, serverSeasonKey: nextKey });
    if (
      pendingPricingSeasonToast.current &&
      prevKey != null &&
      prevKey !== nextKey
    ) {
      toast.success(
        t("simulateur.toast.pricingSeasonUpdated").replace(
          "{{season}}",
          t(
            `simulateur.recap.pillSeason.${funnelSaisonKeyForRecap(value, nextKey)}`,
          ),
        ),
      );
    }
    pendingPricingSeasonToast.current = false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seasonsData?.saisonKey]);

  const onDatesApplied = React.useCallback(() => {
    pendingPricingSeasonToast.current = true;
    toast.success(t("simulateur.toast.datesApplied"));
  }, [t, toast]);

  const activeSeason = marketingSeasons?.find((s) => s.key === value.fSaison);

  const setSaison = (saison: MarketingSeason) => {
    onResetResultsSearch();
    const defaultDate =
      typeof saison.defaultDate === "string" &&
      /^\d{4}-\d{2}-\d{2}$/.test(saison.defaultDate)
        ? saison.defaultDate
        : todayIsoLocal();
    patch({
      fSaison: saison.key,
      dateDebut: defaultDate,
      dateFin: addDaysIso(defaultDate, value.fNuits),
      serverSeasonKey: null,
      fEnv: null,
      regionFilter: "",
      filterModalActivityIds: [],
      villageId: null,
      attractionNom: null,
    });
  };

  const selectedVillage = value.villageId
    ? villages.find((v) => v.id === value.villageId)
    : null;

  const onVillageMaybeInvalid = () => {
    if (!value.villageId) return;
    const v = villages.find((vv) => vv.id === value.villageId);
    if (!v) return;
    if (!isVillageOuvert(v.ouverture, value.dateDebut))
      patch({ villageId: null });
  };

  return (
    <Box className="vtf-tab-stack">
      {isLoadingMarketingSeasons ? (
        <StaySeasonCardSkeleton />
      ) : (
        <StaySeasonCard
          value={{ fSaison: value.fSaison }}
          onSelect={setSaison}
          seasons={marketingSeasons}
          isError={isMarketingSeasonsError}
          onRetry={() => refetchMarketingSeasons()}
        />
      )}

      {isLoadingSeasons && !isSeasonsError && value.fSaison && (
        <StaySeasonDetailsSkeleton />
      )}

      {isSeasonsError && !value.fSaison && (
        <VtfErrorAlert
          title={t("simulateur.sejour.errorDetailsLoad")}
          message={t("simulateur.sejour.errorSubtitle")}
          onRetry={() => refetchSeasons()}
          retryLabel={t("simulateur.family.retry")}
          sx={{ mt: 2 }}
        />
      )}

      {value.fSaison && !isLoadingSeasons && (
        <StayNightsCard
          value={{
            fNuits: value.fNuits,
            dateDebut: value.dateDebut,
            dateFin: value.dateFin,
          }}
          onChange={(next) => patch(next)}
          onVillageMaybeInvalid={onVillageMaybeInvalid}
          onApplied={onDatesApplied}
          activeSeason={activeSeason}
          isError={isSeasonsError}
          onRetry={() => refetchSeasons()}
        />
      )}

      {value.fSaison && !isLoadingSeasons && (
        <StayEnvironmentCard
          seasonKey={value.fSaison}
          value={{ fEnv: value.fEnv }}
          onSelect={(env) => {
            onResetResultsSearch();
            patch({
              fEnv: env,
              regionFilter: "",
              filterModalActivityIds: [],
              formuleFilter: "DP",
              villageId: null,
              formule: null,
              attractionNom: null,
            });
          }}
        />
      )}

      {value.fSaison && value.fEnv && (
        <StayResultsCard
          value={{
            mode: value.mode,
            attractionNom: value.attractionNom,
            attractionId: value.attractionId,
            villageId: value.villageId,
            formuleFilter: value.formuleFilter ?? null,
            fEnv: value.fEnv,
            dateDebut: value.dateDebut,
            regionFilter: value.regionFilter ?? "",
            filterModalActivityIds: value.filterModalActivityIds ?? [],
          }}
          villages={villages}
          isLoading={isLoading}
          isVillagesError={isVillagesError}
          refetchVillages={refetchVillages}
          villagesPaging={villagesPaging}
          resultsSearchInput={resultsSearchInput}
          resultsSearchDebounced={resultsSearchDebounced}
          onResultsSearchInputChange={onResultsSearchInputChange}
          onChange={(partial) => {
            if (partial.villageId) {
              const v = villages.find((vv) => vv.id === partial.villageId);
              patch({
                ...partial,
                formule:
                  value.formule && v?.formules.includes(value.formule)
                    ? value.formule
                    : null,
              });
              return;
            }
            patch(partial);
          }}
        />
      )}

      {selectedVillage && (
        <StayFormuleCard
          village={selectedVillage}
          value={{ formule: value.formule }}
          onSelect={(f) =>
            patch({ formule: value.formule === f ? null : f })
          }
        />
      )}
    </Box>
  );
}
