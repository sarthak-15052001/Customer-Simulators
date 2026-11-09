import * as React from "react";
import { useTranslation } from "../../../contexts/LanguageContext";
import type { VtfFormule, VtfVillage } from "../../../data/vtfStay";
import type { SejourEnvKey } from "../../../utils/stayTab";
import type { SejourMode, SejourState } from "../../../types/stayTab";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";
import { Box, Pill } from "../../ui";
import { StayResultsSkeleton } from "./StayResultsSkeleton";
import { StayResultsFiltersModal } from "./StayResultsFiltersModal";
import type { VillagesPaging } from "./stayResultsCardModel";
import { useStayResultsDerived } from "./useStayResultsDerived";
import { useAttractions } from "../../../hooks/attraction.hooks";
import { useFormules } from "../../../hooks/formules.hooks";
import { getFormuleLabelFromCatalog } from "./StayFormulePicker.shared";
import {
  StayResultsActivitySection,
  StayResultsCardHeader,
  StayResultsEmptyDataset,
  StayResultsVillageListSection,
} from "./StayResultsCard.sections";

export type StayResultsCardProps = {
  value: {
    mode: SejourMode;
    attractionNom: string | null;
    attractionId?: string | null;
    villageId: string | null;
    formuleFilter: VtfFormule | null;
    fEnv: SejourEnvKey | null;
    dateDebut: string | null;
    regionFilter: string;
    filterModalActivityIds: string[];
  };
  villages: VtfVillage[];
  isLoading?: boolean;
  isVillagesError?: boolean;
  refetchVillages?: () => void;
  villagesPaging?: VillagesPaging;
  resultsSearchInput: string;
  resultsSearchDebounced: string;
  onResultsSearchInputChange: (value: string) => void;
  onChange: (
    partial: Partial<StayResultsCardProps["value"]> &
      Partial<Pick<SejourState, "formule">>,
  ) => void;
};

export function StayResultsCard({
  value,
  villages,
  isLoading,
  isVillagesError,
  refetchVillages,
  villagesPaging,
  resultsSearchInput,
  resultsSearchDebounced,
  onResultsSearchInputChange,
  onChange,
}: StayResultsCardProps) {
  const { t } = useTranslation();
  const ts = React.useCallback((k: string) => t(`simulateur.sejour.${k}`), [t]);
  const {
    data: attractions = [],
    isLoading: isAttractionsLoading,
    isError: isAttractionsError,
    refetch: refetchAttractions,
  } = useAttractions(
    value.fEnv,
    value.mode === "activite" || !!value.attractionNom || !!value.attractionId,
  );
  const { data: apiFormules } = useFormules();
  const [filterModalOpen, setFilterModalOpen] = React.useState(false);

  const attractionFilterLabel = React.useMemo(() => {
    if (value.attractionNom) return value.attractionNom;
    if (!value.attractionId) return null;
    return attractions.find((a) => a.id === value.attractionId)?.nom ?? null;
  }, [value.attractionNom, value.attractionId, attractions]);

  const derived = useStayResultsDerived({
    value: {
      dateDebut: value.dateDebut,
      fEnv: value.fEnv,
      formule: value.formuleFilter,
      attractionNom: value.attractionNom,
    },
    villages,
    attractions,
    villagesPaging,
    resultsSearchDebounced,
  });

  const selectVillage = (v: VtfVillage) => {
    onChange({ villageId: v.id });
  };

  if (isLoading || isAttractionsLoading) {
    return <StayResultsSkeleton mode={value.mode} />;
  }

  const hasActiveFilters =
    resultsSearchInput.trim() !== "" ||
    (value.regionFilter || "") !== "" ||
    (value.filterModalActivityIds || []).length > 0 ||
    value.attractionNom !== null ||
    !!value.attractionId ||
    value.formuleFilter !== null;

  const clearAllFilters = () => {
    onResultsSearchInputChange("");
    onChange({
      mode: "village",
      regionFilter: "",
      filterModalActivityIds: [],
      attractionNom: null,
      attractionId: null,
      formuleFilter: null,
      formule: null,
      villageId: null,
    });
  };

  const activeFilterPills: Array<{
    key: string;
    label: string;
    onDelete: () => void;
  }> = [];
  if (value.formuleFilter) {
    const formLabel = getFormuleLabelFromCatalog(value.formuleFilter, apiFormules);
    activeFilterPills.push({
      key: "formule",
      label: ts("filterFormule").replace("{{value}}", formLabel),
      onDelete: () => onChange({ formuleFilter: null }),
    });
  }
  if (value.regionFilter) {
    activeFilterPills.push({
      key: "region",
      label: ts("filterRegion").replace("{{value}}", value.regionFilter),
      onDelete: () => onChange({ regionFilter: "" }),
    });
  }
  if (attractionFilterLabel) {
    activeFilterPills.push({
      key: "attraction",
      label: ts("filterActivity").replace("{{value}}", attractionFilterLabel),
      onDelete: () => onChange({ attractionNom: null, attractionId: null }),
    });
  }
  if (value.filterModalActivityIds && value.filterModalActivityIds.length > 0) {
    activeFilterPills.push({
      key: "activities",
      label: ts("filterActivitiesCount").replace(
        "{{count}}",
        String(value.filterModalActivityIds.length),
      ),
      onDelete: () => onChange({ filterModalActivityIds: [] }),
    });
  }

  return (
    <VtfGlassCard>
      <StayResultsCardHeader
        mode={value.mode}
        ts={ts}
        searchValue={resultsSearchInput}
        onSearchChange={onResultsSearchInputChange}
        hasActiveFilters={hasActiveFilters}
        onClearFilters={clearAllFilters}
        onVillageMode={() => {
          onResultsSearchInputChange("");
          onChange({
            mode: "village",
            attractionNom: null,
            attractionId: null,
          });
        }}
        onActivityMode={() => {
          onResultsSearchInputChange("");
          onChange({ mode: "activite", villageId: null, attractionId: null });
        }}
        onOpenFilters={() => setFilterModalOpen(true)}
      />

      {(isVillagesError &&
        !(
          value.mode === "activite" &&
          !isAttractionsError &&
          derived.displayAttractions.length > 0
        )) ||
      (isAttractionsError && value.mode === "activite") ? (
        <VtfErrorAlert
          title={
            isAttractionsError && value.mode === "activite"
              ? ts("resultsActivitiesErrorTitle")
              : ts("resultsErrorTitle")
          }
          message={
            isAttractionsError && value.mode === "activite"
              ? ts("envErrorSubtitle")
              : ts("errorSubtitle")
          }
          onRetry={() => {
            refetchVillages?.();

            if (isAttractionsError) {
              refetchAttractions();
            }
          }}
          retryLabel={t("simulateur.family.retry")}
          sx={{ m: 4 }}
        />
      ) : (
        <>
          {activeFilterPills.length > 0 && (
            <Box
              sx={{
                display: "flex",
                flexWrap: "wrap",
                gap: 0.75,
                mb: 1.5,
                px: 0.5,
              }}
            >
              {activeFilterPills.map((p) => (
                <Pill
                  key={p.key}
                  label={p.label}
                  vtfTone="softTeal"
                  onDelete={p.onDelete}
                />
              ))}
            </Box>
          )}

          {value.mode === "activite" ? (
            <StayResultsActivitySection
              searchQNorm={derived.searchQNorm}
              displayAttractions={derived.displayAttractions}
              attractionNom={value.attractionNom}
              displayActivityVillages={derived.displayActivityVillages}
              villageId={value.villageId}
              formuleFilter={value.formuleFilter}
              ts={ts}
              onAttractionClick={(nom, id, sel) =>
                onChange({
                  mode: "village",
                  attractionNom: sel ? null : nom,
                  attractionId: sel ? null : id,
                  villageId: null,
                })
              }
              onSelectVillage={selectVillage}
            />
          ) : derived.isVillageListEmpty ? (
            <StayResultsEmptyDataset ts={ts} />
          ) : (
            <StayResultsVillageListSection
              searchQNorm={derived.searchQNorm}
              displayVillageItems={derived.displayVillageItems}
              villageId={value.villageId}
              formuleFilter={value.formuleFilter}
              mode={value.mode}
              villagesPaging={villagesPaging}
              ts={ts}
              onSelectVillage={selectVillage}
            />
          )}
        </>
      )}

      <StayResultsFiltersModal
        open={filterModalOpen}
        onClose={() => setFilterModalOpen(false)}
        committedRegionFilter={value.regionFilter ?? ""}
        committedFormule={value.formuleFilter}
        selectedActivityIds={value.filterModalActivityIds ?? []}
        onSubmit={({ region, activityIds, formule }) => {
          onChange({
            regionFilter: region,
            filterModalActivityIds: activityIds,
            formuleFilter: formule,
            villageId: null,
            formule: null,
          });
          setFilterModalOpen(false);
        }}
      />
    </VtfGlassCard>
  );
}
