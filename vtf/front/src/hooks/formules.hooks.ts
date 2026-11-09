import { useQuery } from "@tanstack/react-query";

import { getFormules } from "../api/formules.api";

export function useFormules(enabled: boolean = true) {
  return useQuery({
    queryKey: ["formules"],
    queryFn: () => getFormules(),
    enabled,
    staleTime: 10 * 60 * 1000,
  });
}
