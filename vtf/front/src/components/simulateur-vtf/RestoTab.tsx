import * as React from "react";
import type { RestoTabProps, RestoMealId } from "../../types/restoTab";
import type { VtfFormule } from "../../data/vtfStay";
import { useMeals } from "../../hooks/meals.hooks";
import { useFormules } from "../../hooks/formules.hooks";
import { useSimulateurTabTranslation } from "../../hooks/useSimulateurTabTranslation";
import { familyAdultChildLabels } from "../../utils/familyCountLabels";
import {
  familyMealUnitPrice,
  restoLineTotal,
  restoNoteKey,
  sumQty,
  EMPTY_RESTO_QTY_MAP,
  type RestoQtyByMealId,
} from "../../utils/restoTab";
import {
  getFormuleLabelFromCatalog,
  resolveStayFormulePickerOptions,
} from "./stay/StayFormulePicker.shared";
import { RestoTabView, type RestoMealRow } from "./resto/RestoTabView";
import type { RestoVtfFormuleOption } from "./resto/RestoVtfFormuleSection";

export function RestoTab({
  family,
  sejour,
  village,
  onChange,
  serverEstimate,
  serverEstimateLoading = false,
}: RestoTabProps) {
  const tr = useSimulateurTabTranslation("resto");
  const { data: apiFormules } = useFormules();
  const {
    data: meals = [],
    isLoading: isMealsLoading,
    isError: isMealsError,
    refetch: refetchMeals,
  } = useMeals();
  const qtyByMealId = sejour.resto?.qtyByMealId ?? EMPTY_RESTO_QTY_MAP;

  const patchResto = React.useCallback(
    (qtyMap: RestoQtyByMealId) => {
      onChange({ ...sejour, resto: { ...sejour.resto, qtyByMealId: qtyMap } });
    },
    [onChange, sejour],
  );

  const onDec = React.useCallback(
    (id: RestoMealId) => {
      const current = qtyByMealId[id] ?? 0;
      if (current <= 0) return;
      const next = { ...qtyByMealId, [id]: current - 1 };
      if (next[id] === 0) delete next[id];
      patchResto(next);
    },
    [patchResto, qtyByMealId],
  );

  const onInc = React.useCallback(
    (id: RestoMealId) => {
      const current = qtyByMealId[id] ?? 0;
      patchResto({ ...qtyByMealId, [id]: current + 1 });
    },
    [patchResto, qtyByMealId],
  );

  const onReset = React.useCallback(() => {
    patchResto({});
  }, [patchResto]);

  const items = React.useMemo<RestoMealRow[]>(
    () =>
      meals.map((m) => {
        const qty = qtyByMealId[m.id] ?? 0;
        const unitFamily = familyMealUnitPrice({
          meal: m,
          adults: family.adultes,
          children: family.enfants.length,
        });
        const lineTotal = qty > 0 ? restoLineTotal({ qty, unitFamily }) : 0;
        return {
          id: m.id as RestoMealId,
          label: m.label,
          priceAdultRounded: Math.round(m.priceAdult),
          priceChildRounded: Math.round(m.priceChild),
          unitFamilyRounded: Math.round(unitFamily),
          qty,
          lineTotal,
        };
      }),
    [family.adultes, family.enfants.length, qtyByMealId, meals],
  );

  const totalMeals = React.useMemo(() => sumQty(qtyByMealId), [qtyByMealId]);

  const totalAmount = serverEstimate?.restoTotal ?? 0;

  const note = tr(restoNoteKey(sejour.formule as string));
  const { adultWord, childWord } = familyAdultChildLabels(
    tr,
    family.adultes,
    family.enfants.length,
  );

  const vtfFormuleOptions = React.useMemo((): RestoVtfFormuleOption[] => {
    if (!sejour.villageId) return [];

    const fromServer = serverEstimate?.formuleAlternatives ?? [];
    const pickerOptions = resolveStayFormulePickerOptions({
      apiFormules,
      villageFormules: village?.formules,
    });

    const boardFormules = (["PC", "DP"] as const);
    const villageBoardFormules = boardFormules.filter(
      (f) => village?.formules?.includes(f) ?? false,
    );

    if (!villageBoardFormules.length) return [];

    return villageBoardFormules.map((formule) => {
      const meta = pickerOptions.find((o) => o.k === formule);
      const isCurrentFormule = formule === sejour.formule;
      const serverAlt = fromServer.find((a) => a.formule === formule);

      const total = isCurrentFormule
        ? (serverEstimate?.total ?? null)
        : (serverAlt?.total ?? null);

      const isCurrentlyFetchingThis = isCurrentFormule && serverEstimateLoading;
      const isInitialLoading = !serverEstimate && total == null;

      return {
        formule,
        label: meta?.label ?? getFormuleLabelFromCatalog(formule, apiFormules),
        sub: meta?.sub ?? "",
        total,
        selected: isCurrentFormule,
        loading: isCurrentlyFetchingThis || isInitialLoading,
        error: Boolean(serverEstimate && total == null && !serverEstimateLoading),
      };
    });
  }, [
    apiFormules,
    village?.formules,
    sejour.formule,
    sejour.villageId,
    serverEstimate,
    serverEstimateLoading,
  ]);

  const showVtfFormuleOffer = vtfFormuleOptions.length > 0;

  const onSelectVtfFormule = React.useCallback(
    (formule: VtfFormule) => {
      if (sejour.formule === formule) {
        if (village?.formules?.includes("LOC")) {
          onChange({ ...sejour, formule: "LOC" });
          return;
        }
      }
      onChange({ ...sejour, formule });
    },
    [onChange, sejour, village?.formules],
  );

  return (
    <RestoTabView
      tr={tr}
      note={note}
      items={items}
      adultWord={adultWord}
      childWord={childWord}
      totalMeals={totalMeals}
      totalAmount={totalAmount}
      onDec={onDec}
      onInc={onInc}
      onReset={onReset}
      isLoading={isMealsLoading}
      loadError={isMealsError}
      onRetry={() => void refetchMeals()}
      vtfFormuleOptions={showVtfFormuleOffer ? vtfFormuleOptions : undefined}
      onSelectVtfFormule={onSelectVtfFormule}
    />
  );
}
