import { useQuery } from "@tanstack/react-query";
import attractionApi from "../api/attraction.api";
import type { SejourEnvKey } from "../utils/stayTab";

export function useAttractions(env: SejourEnvKey | null, enabled: boolean = true) {
  return useQuery({
    queryKey: ["attractions", env],
    queryFn: () => attractionApi.getAttractions(env!),
    enabled: enabled && !!env,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}
