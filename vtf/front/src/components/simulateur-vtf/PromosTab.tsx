import * as React from "react";
import type { PromosTabProps } from "../../types/promosTab";
import type { PromoChoice } from "../../data/vtfPromos";
import { formatEuro } from "../../utils/currency";
import { getQfBadgeKind, isQfReductionPeriod } from "../../utils/familyTab";
import { diffNuits, addDaysIso, todayIsoLocal } from "../../utils/stayTab";
import { promoRatesMatch } from "../../utils/bestPromo";
import { useSimulateurTabTranslation } from "../../hooks/useSimulateurTabTranslation";
import { usePromoCatalog, useAvailablePromos } from "../../hooks/promos.hooks";
import { PromosTabView } from "./promos/PromosTabView";
import { resolvePromosDiscountSummaryState } from "./promos/promosDiscountState";

export function PromosTab({
  family,
  sejour,
  onChange,
  onFamilyChange,
  serverEstimate,
}: PromosTabProps) {
  const tp = useSimulateurTabTranslation("promos");

  const hasStayDates = Boolean(sejour.dateDebut && sejour.dateFin);
  const hasVillage = Boolean(sejour.villageId);

  const availablePromosInput = React.useMemo(() => {
    const { villageId, formule } = sejour;
    if (!villageId) return null;
    const dateDebut = sejour.dateDebut ?? todayIsoLocal();
    const dateFin =
      sejour.dateFin ?? addDaysIso(dateDebut, Math.max(1, sejour.fNuits || 7));
    const isSoloParent =
      (family as unknown as { isSoloParent?: boolean }).isSoloParent ??
      (family.adultes === 1 && family.enfants.length > 0);
    const nuits = diffNuits(dateDebut, dateFin);
    const quinzaineFutee = formule === "PC" && (nuits ?? 0) >= 14;
    return { dateDebut, dateFin, villageId, formule, isSoloParent, quinzaineFutee };
  }, [sejour, family]);

  const {
    data: catalog = [],
    isLoading: isCatalogLoading,
    isError: isCatalogError,
    refetch: refetchCatalog,
  } = usePromoCatalog();

  const {
    data: availableFromApi = [],
    isLoading: isAvailableLoading,
    isError: isAvailableError,
    refetch: refetchAvailable,
  } = useAvailablePromos(availablePromosInput);

  const quinzaineFutee = availablePromosInput?.quinzaineFutee ?? false;

  const selectedPromoRate = sejour.promos?.promoSejourRate ?? 0;
  const selectedPromoKey = React.useMemo<PromoChoice["key"]>(() => {
    if (!selectedPromoRate || selectedPromoRate <= 0) return "none";
    const fromAvailable = availableFromApi.find((p) =>
      promoRatesMatch(p.rate, selectedPromoRate),
    );
    if (fromAvailable) return fromAvailable.key;
    const fromCatalog = catalog.find((p) =>
      promoRatesMatch(p.rate, selectedPromoRate),
    );
    return fromCatalog?.key ?? "none";
  }, [catalog, availableFromApi, selectedPromoRate]);

  const est = serverEstimate;

  const applyPromoRate = React.useCallback(
    (rate: number) => {
      onChange({
        ...sejour,
        promos: {
          ...sejour.promos,
          promoSejourRate: rate,
        },
      });
    },
    [onChange, sejour],
  );

  React.useEffect(() => {
    if (!availablePromosInput || isAvailableLoading) return;
    const rate = sejour.promos?.promoSejourRate ?? 0;
    if (rate <= 0) return;
    const stillEligible = availableFromApi.some(
      (p) => promoRatesMatch(p.rate, rate) || p.key === selectedPromoKey,
    );
    if (!stillEligible) {
      applyPromoRate(0);
    }
  }, [
    availableFromApi,
    availablePromosInput,
    isAvailableLoading,
    sejour.promos?.promoSejourRate,
    selectedPromoKey,
    applyPromoRate,
  ]);

  const discountedBudgetLabel = React.useMemo(() => {
    if (!est) return null;
    return formatEuro(est.total);
  }, [est]);

  const appliedLines = React.useMemo(() => {
    const lines: Array<{ icon: string; label: string; note?: string }> = [];
    if (!est) return lines;

    const isPeriodValid = isQfReductionPeriod(
      sejour.dateDebut,
      sejour.villageId,
      sejour.fSaison,
    );
    const qfKind = getQfBadgeKind(family.qfVal);
    const promoRate = sejour.promos?.promoSejourRate ?? 0;
    const qfCouldApply = qfKind === "r1" || qfKind === "r2";
    if (
      qfCouldApply &&
      isPeriodValid &&
      (promoRate === 0
        ? est.discountRate > 0.001
        : est.discountRate > promoRate + 0.001)
    ) {
      lines.push({
        icon: "🏠",
        label: tp("appliedFamilyQuotient"),
        note: tp("appliedFamilyQuotientNote"),
      });
    }

    if (promoRate > 0) {
      lines.push({
        icon: "🏷️",
        label: tp("appliedStayPromo").replace(
          "{{rate}}",
          String(Math.round(promoRate * 100)),
        ),
        note: tp("appliedStayPromoNote"),
      });
    }

    if (quinzaineFutee) {
      lines.push({
        icon: "📅",
        label: tp("appliedQuinzaine"),
        note: tp("appliedQuinzaineNote"),
      });
    }

    return lines;
  }, [
    est,
    family.qfVal,
    quinzaineFutee,
    sejour.promos?.promoSejourRate,
    sejour.dateDebut,
    sejour.villageId,
    sejour.fSaison,
    tp,
  ]);

  const qfKind = React.useMemo(
    () => getQfBadgeKind(family.qfVal),
    [family.qfVal],
  );
  const isPeriodValid = React.useMemo(
    () =>
      isQfReductionPeriod(
        sejour.dateDebut,
        sejour.villageId,
        sejour.fSaison,
      ),
    [sejour.dateDebut, sejour.villageId, sejour.fSaison],
  );

  const qfSelection =
    qfKind === "r1"
      ? "r1"
      : qfKind === "r2"
        ? "r2"
        : qfKind === "plein"
          ? "plein"
          : "empty";

  const qfValueLabel =
    family.qfVal == null ? tp("qfCurrentEmpty") : formatEuro(family.qfVal);

  const isStayConfigured = Boolean(
    sejour.villageId && sejour.dateDebut && sejour.dateFin,
  );
  const totalStayDiscountPct = est?.displayMetrics?.discountPct ?? null;
  const discountSummaryState = resolvePromosDiscountSummaryState({
    isStayConfigured,
    hasEstimate: est != null,
    discountPct: totalStayDiscountPct,
  });

  const handleUpdateQf = React.useCallback(
    (val: number | null) => {
      if (onFamilyChange) {
        onFamilyChange({
          ...family,
          qfVal: val,
        });
      }
    },
    [family, onFamilyChange],
  );

  return (
    <PromosTabView
      tp={tp}
      appliedLines={appliedLines}
      discountSummaryState={discountSummaryState}
      totalStayDiscountPct={totalStayDiscountPct}
      discountedBudgetLabel={discountedBudgetLabel}
      qfSelection={qfSelection}
      qfValueLabel={qfValueLabel}
      isQfPeriodValid={isPeriodValid}
      qfVal={family.qfVal}
      onUpdateQf={onFamilyChange ? handleUpdateQf : undefined}
      promoCatalog={catalog}
      availablePromos={availableFromApi}
      hasStayDates={hasStayDates}
      hasVillage={hasVillage}
      isCatalogLoading={isCatalogLoading}
      isCatalogError={isCatalogError}
      isAvailableLoading={hasStayDates && hasVillage && isAvailableLoading}
      isAvailableError={hasStayDates && hasVillage && isAvailableError}
      onRetryCatalog={() => void refetchCatalog()}
      onRetryAvailable={() => void refetchAvailable()}
      selectedPromoKey={selectedPromoKey}
      onSelectPromo={(choice) => {
        const availableItem = availableFromApi.find((p) => p.key === choice.key);
        applyPromoRate(availableItem ? availableItem.rate : choice.rate);
      }}
      onSelectNone={() => applyPromoRate(0)}
    />
  );
}
