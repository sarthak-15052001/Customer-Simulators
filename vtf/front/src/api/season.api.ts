import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";

/** Shape returned by GET /api/v1/season?date=... */
type SeasonApiWrapped = {
  success: boolean;
  message: string;
  data: {
    saisonKey: string;
    saisonIdx: number;
  };
};

export type SeasonRetrieveResponse = {
  saisonKey: string;
  saisonIdx: number;
};

/**
 * Fetches season details for the stay simulator.
 * Requires a date to determine the seasonal configuration.
 * API returns { success, message, data: { saisonKey, saisonIdx } }
 */
export const fetchSeasons = async (date: string): Promise<SeasonRetrieveResponse> => {
  const { data } = await apiClient.get<SeasonApiWrapped>(
    ENDPOINTS.SEASON.RETRIEVE,
    { params: { date } }
  );
  // Unwrap: response is { success, message, data: { saisonKey, saisonIdx } }
  return data.data ?? (data as unknown as SeasonRetrieveResponse);
};

export type MarketingSeason = {
  key: string;
  label: string;
  icon: string;
  defaultDate: string;
  startDate: string;
  endDate: string;
  sortOrder: number;
  currentSalesSeason?: boolean;
};

/** Picks the API-designated sales season, or the first item as fallback. */
export function pickCurrentSalesSeason(
  seasons: MarketingSeason[],
): MarketingSeason | undefined {
  if (!seasons.length) return undefined;
  return seasons.find((s) => s.currentSalesSeason) ?? seasons[0];
}

type MarketingSeasonsWrapped = {
  success: boolean;
  message: string;
  data: {
    items: MarketingSeason[];
  };
};

export const fetchMarketingSeasons = async (): Promise<MarketingSeason[]> => {
  const { data } = await apiClient.get<MarketingSeasonsWrapped>(
    ENDPOINTS.MARKETING_SEASONS
  );
  return data.data?.items ?? [];
};

export type EnvironmentItem = {
  key: string;
  icon: string;
  label: string;
  sub: string;
};

export type EnvironmentsWrapped = {
  success: boolean;
  message: string;
  data: {
    marketing_season_key: string;
    items: EnvironmentItem[];
  };
};

export const fetchEnvironments = async (marketingSeasonKey: string): Promise<EnvironmentItem[]> => {
  const { data } = await apiClient.get<EnvironmentsWrapped>(ENDPOINTS.ENVIRONMENTS, {
    params: { marketing_season_key: marketingSeasonKey },
  });
  return data.data?.items ?? [];
};

export const seasonApi = {
  fetchSeasons,
  fetchMarketingSeasons,
  fetchEnvironments,
};
