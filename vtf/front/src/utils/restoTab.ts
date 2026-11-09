import type { RestoMeal, RestoMealId } from "../data/vtfResto";

export type RestoQtyByMealId = Partial<Record<RestoMealId, number>>;

export const EMPTY_RESTO_QTY_MAP: RestoQtyByMealId = {};

export function clampInt(n: number, min: number, max: number): number {
  if (!Number.isFinite(n)) return min;
  return Math.max(min, Math.min(max, Math.trunc(n)));
}

export function sumQty(
  map: Partial<Record<string, number>> | undefined | null,
): number {
  if (!map) return 0;
  return Object.values(map).reduce<number>(
    (s, v) => s + (typeof v === "number" ? v : 0),
    0,
  );
}

export function restoNoteKey(formule: string | null | undefined): "notePC" | "noteDP" | "noteLOC" {
  const f = (formule ?? "").toLowerCase();
  if (f === "pc") return "notePC";
  if (f === "dp") return "noteDP";
  return "noteLOC";
}

export function familyMealUnitPrice(args: {
  meal: RestoMeal;
  adults: number;
  children: number;
}): number {
  const { meal, adults, children } = args;
  return (
    Math.max(0, meal.priceAdult) * Math.max(0, adults) +
    Math.max(0, meal.priceChild) * Math.max(0, children)
  );
}

export function restoLineTotal(args: {
  qty: number;
  unitFamily: number;
}): number {
  const qty = Math.max(0, args.qty);
  const unit = Math.max(0, args.unitFamily);
  return Math.round(qty * unit);
}

export function restoTotalAmount(args: {
  meals: RestoMeal[];
  qtyByMealId: RestoQtyByMealId;
  adults: number;
  children: number;
}): number {
  const { meals, qtyByMealId, adults, children } = args;
  return meals.reduce((sum, meal) => {
    const qty = qtyByMealId[meal.id] ?? 0;
    if (!qty || qty <= 0) return sum;
    const unitFamily = familyMealUnitPrice({ meal, adults, children });
    return sum + qty * unitFamily;
  }, 0);
}
