import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

import regionActivitiesApi, {
  type RegionActivityDto,
  type RegionActivitiesQuery,
} from "../api/regionActivities.api";

const STALE_MS = 5 * 60 * 1000;

export function useRegionActivities(
  regionKey: string | null | undefined,
  query: RegionActivitiesQuery,
  options?: Partial<UseQueryOptions<RegionActivityDto[]>>,
) {
  const region = regionKey?.trim() || null;
  return useQuery({
    queryKey: ["regionActivities", region, query.kind ?? "all", query.season ?? ""],
    queryFn: () => regionActivitiesApi.getActivities(region!, query),
    enabled: !!region,
    staleTime: STALE_MS,
    ...options,
  });
}
