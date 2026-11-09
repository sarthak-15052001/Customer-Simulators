import { useQuery } from "@tanstack/react-query";
import { seasonApi } from "../api/season.api";

export const SEASON_KEYS = {
  all: ["seasons"] as const,
  retrieve: (date: string) => [...SEASON_KEYS.all, "retrieve", date] as const,
  marketing: () => [...SEASON_KEYS.all, "marketing"] as const,
};

/**
 * Hook to fetch seasons data for the simulator.
 */
export function useSeasons(date: string, enabled: boolean = true) {
  return useQuery({
    queryKey: SEASON_KEYS.retrieve(date),
    queryFn: () => seasonApi.fetchSeasons(date),
    enabled: enabled && !!date,
  });
}

/**
 * Hook to fetch dynamic marketing seasons for the simulator options.
 */
export function useMarketingSeasons() {
  return useQuery({
    queryKey: SEASON_KEYS.marketing(),
    queryFn: () => seasonApi.fetchMarketingSeasons(),
  });
}

export function useEnvironments(marketingSeasonKey?: string) {
  return useQuery({
    queryKey: [...SEASON_KEYS.all, "environments", marketingSeasonKey],
    queryFn: () => seasonApi.fetchEnvironments(marketingSeasonKey!),
    enabled: !!marketingSeasonKey,
  });
}
