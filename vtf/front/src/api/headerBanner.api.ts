import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";
import API_CONFIG from "../config/api";
import type { HeaderBannerData, HeaderBannerResponse } from "../types/headerBanner";

export const headerBannerApi = {
  getHeaderBanner: async (lang?: string): Promise<HeaderBannerData | null> => {
    try {
      const { data } = await apiClient.get<HeaderBannerResponse>(
        ENDPOINTS.HEADER_BANNER,
        {
          baseURL: API_CONFIG.HOST || "",
          params: lang ? { lang } : undefined,
        },
      );
      if (data && data.success && data.data) {
        return data.data;
      }
      return null;
    } catch {
      return null;
    }
  },
};

export default headerBannerApi;
