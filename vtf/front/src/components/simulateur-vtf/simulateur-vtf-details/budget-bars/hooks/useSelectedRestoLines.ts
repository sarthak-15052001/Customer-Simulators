import * as React from "react";
import type { RestoMeal } from "../../../../../data/vtfResto";
import type { RestoMealId } from "../../../../../data/vtfResto";
import type { FamilyState } from "../../../../../types/familyTab";
import {
  familyMealUnitPrice,
  restoLineTotal,
  type RestoQtyByMealId,
} from "../../../../../utils/restoTab";
import { useMeals } from "../../../../../hooks/meals.hooks";

export type SelectedRestoLine = {
  meal: RestoMeal;
  qty: number;
  lineTotal: number;
};

export function useSelectedRestoLines(args: {
  family: FamilyState;
  qtyByMealId: RestoQtyByMealId;
}) {
  const { family, qtyByMealId } = args;
  const { data: meals = [], isPending } = useMeals();

  const lines = React.useMemo((): SelectedRestoLine[] => {
    return meals
      .map((meal) => {
        const qty = qtyByMealId[meal.id as RestoMealId] ?? 0;
        if (qty <= 0) return null;
        const unitFamily = familyMealUnitPrice({
          meal,
          adults: family.adultes,
          children: family.enfants.length,
        });
        return {
          meal,
          qty,
          lineTotal: restoLineTotal({ qty, unitFamily }),
        };
      })
      .filter((row): row is SelectedRestoLine => row != null);
  }, [meals, qtyByMealId, family.adultes, family.enfants.length]);

  return { lines, isPending, hasSelection: lines.length > 0 };
}
