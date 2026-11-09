import * as React from "react";
/**
 * Onglet Famille
 * Gère la composition de la famille et l'estimation du Quotient Familial (QF).
 */
import { Box } from "../ui";

import { useTranslation } from "../../contexts/LanguageContext";
import type {
  AgeOption,
  FamilyState,
  FamilyTabProps,
} from "../../types/familyTab";
import {
  FAMILY_TAB_LIMITS,
  getQfBadgeKind,
  FAMILY_AGE_OPTIONS,
  DEFAULT_NEW_CHILD_AGE,
  clamp,
  suggestedFiscalParts,
} from "../../utils/familyTab";

import { FamilyCompositionCard } from "./family/FamilyCompositionCard";
import { FamilyCompositionCardSkeleton } from "./family/FamilyCompositionCardSkeleton";
import { FamilyQuotientCard } from "./family/FamilyQuotientCard";
import { FamilyQuotientCardSkeleton } from "./family/FamilyQuotientCardSkeleton";
import { useFamilyQfMutation } from "../../hooks/family.hooks";
import { usePricingRules } from "../../hooks/pricingRules.hooks";
export type { FamilyState } from "../../types/familyTab";

export function FamilyTab({ value, onChange }: FamilyTabProps) {
  const { t } = useTranslation();
  const tf = React.useCallback(
    (key: string) => t(`simulateur.family.${key}`),
    [t],
  );

  const valueRef = React.useRef(value);
  React.useEffect(() => {
    valueRef.current = value;
  }, [value]);

  const badgeKind = getQfBadgeKind(value.qfVal);

  const suggestedParts = React.useMemo(
    () => suggestedFiscalParts(value.adultes, value.enfants.length),
    [value.adultes, value.enfants.length],
  );

  const patch = (partial: Partial<FamilyState>) =>
    onChange({ ...value, ...partial });

  const qfFromApi = useFamilyQfMutation({
    onSuccess: (data) => {
      const v = valueRef.current;
      onChange({
        ...v,
        qfVal: clamp(
          data.qfVal,
          FAMILY_TAB_LIMITS.qfMin,
          FAMILY_TAB_LIMITS.qfMax,
        ),
      });
    },
  });

  const pricingRulesQuery = usePricingRules({
    refetchOnWindowFocus: false,
  });
  const childDiscounts = pricingRulesQuery.data?.payload.childDiscounts ?? null;

  const setAdultes = (next: number) =>
    patch({
      adultes: clamp(
        next,
        FAMILY_TAB_LIMITS.adultesMin,
        FAMILY_TAB_LIMITS.adultesMax,
      ),
    });

  const setEnfantAge = (idx: number, age: number) =>
    patch({ enfants: value.enfants.map((e, i) => (i === idx ? { age } : e)) });

  const removeEnfant = (idx: number) => {
    const enfants = value.enfants.filter((_, i) => i !== idx);
    patch({
      enfants,
      maxiFamily: enfants.length < 3 ? false : value.maxiFamily,
    });
  };

  const addEnfant = () => {
    if (value.enfants.length >= FAMILY_TAB_LIMITS.enfantsMax) return;
    patch({ enfants: [...value.enfants, { age: DEFAULT_NEW_CHILD_AGE }] });
  };

  const ageOptions = React.useMemo(
    () =>
      FAMILY_AGE_OPTIONS.map((age) => ({
        value: age.toString(),
        label: age === 0 ? tf("ageUnderOne") : `${age} ${tf("ageYears")}`,
        icon: age < 3 ? "👶" : age < 12 ? "🧒" : "👦",
      })),
    [tf],
  );

  return (
    <Box
      className="vtf-tab-stack"
      sx={{
        display: "flex",
        flexDirection: "column",
        gap: { xs: 2, sm: 2.5 },
      }}
    >
      {pricingRulesQuery.isPending ? (
        <FamilyCompositionCardSkeleton />
      ) : (
        <FamilyCompositionCard
          value={value}
          tf={tf}
          ageOptions={ageOptions as AgeOption[]}
          onSetAdultes={setAdultes}
          onSetEnfantAge={setEnfantAge}
          onAddEnfant={addEnfant}
          onRemoveEnfant={removeEnfant}
          limits={{
            adultesMin: FAMILY_TAB_LIMITS.adultesMin,
            adultesMax: FAMILY_TAB_LIMITS.adultesMax,
            enfantsMax: FAMILY_TAB_LIMITS.enfantsMax,
          }}
          childDiscounts={childDiscounts}
          childDiscountsLoading={pricingRulesQuery.isFetching}
          childDiscountsError={pricingRulesQuery.isError}
          onRetry={() => pricingRulesQuery.refetch()}
        />
      )}

      {qfFromApi.isPending ? (
        <FamilyQuotientCardSkeleton />
      ) : (
        <FamilyQuotientCard
          key={`qf-${value.adultes}-${value.enfants.length}-${suggestedParts}`}
          value={value}
          tf={tf}
          badgeKind={badgeKind}
          onToggleMaxiFamily={(checked) => patch({ maxiFamily: checked })}
          qfEstimate={{
            suggestedParts,
            isPending: qfFromApi.isPending,
            error: qfFromApi.error,
            onSubmit: (netMonthlyIncome, parts) =>
              qfFromApi.mutate({ netMonthlyIncome, parts }),
            onClear: () => patch({ qfVal: undefined }),
          }}
        />
      )}
    </Box>
  );
}
