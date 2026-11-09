import { useQuery } from "@tanstack/react-query";
import mealsApi from "../api/meals.api";

export function useMeals(enabled: boolean = true) {
  return useQuery({
    queryKey: ["meals"],
    queryFn: () => mealsApi.getMeals(),
    enabled,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}
