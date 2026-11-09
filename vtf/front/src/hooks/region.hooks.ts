import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

import regionApi, {
  type RegionSummary,
} from "../api/region.api";

export function useRegions(
  enabled: boolean,
  options?: Partial<UseQueryOptions<RegionSummary[]>>,
) {
  return useQuery({
    queryKey: ["regions"],
    queryFn: () => regionApi.getRegions(),
    enabled,
    staleTime: 5 * 60 * 1000,
    ...options,
  });
}
