import client from "./client";
import ENDPOINTS from "./endpoints";
import type { RestoMeal } from "../data/vtfResto";

export const getMeals = async (): Promise<RestoMeal[]> => {
  const result = await client.get<{ data: RestoMeal[] }>(ENDPOINTS.MEALS);
  return result.data.data;
};

export default { getMeals };
