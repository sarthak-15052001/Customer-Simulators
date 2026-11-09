import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

import pricingRulesApi, {
  type PricingRulesApiResponse,
} from "../api/pricingRules.api";

export function usePricingRules(
  options?: Partial<UseQueryOptions<PricingRulesApiResponse, Error>>,
) {
  return useQuery({
    queryKey: ["pricing-rules"],
    queryFn: () => pricingRulesApi.getPricingRules(),
    staleTime: 86_400_000,
    retry: 1,
    ...options,
  });
}
