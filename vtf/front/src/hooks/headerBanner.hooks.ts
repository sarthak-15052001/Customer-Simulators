import { useQuery } from "@tanstack/react-query";
import { headerBannerApi } from "../api/headerBanner.api";

export const HEADER_BANNER_KEYS = {
  all: ["header-banner"] as const,
  banner: (lang?: string) => [...HEADER_BANNER_KEYS.all, lang] as const,
};

/**
 * Hook to fetch dynamic header banner marketing links.
 */
export function useHeaderBanner(lang?: string) {
  return useQuery({
    queryKey: HEADER_BANNER_KEYS.banner(lang),
    queryFn: () => headerBannerApi.getHeaderBanner(lang),
    staleTime: 5 * 60 * 1000,
  });
}
