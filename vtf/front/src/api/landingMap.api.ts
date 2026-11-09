import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";
import type { LandingMapData } from "../types/landingMap";

export const landingMapApi = {
  getMapData: async (lang: string): Promise<LandingMapData> => {
    const { data } = await apiClient.get<{
      success: boolean;
      message?: string;
      data: LandingMapData;
    }>(ENDPOINTS.LANDING.MAP, {
      params: { lang: lang.toLowerCase() },
    });

    return data.data;
  },
};

export default landingMapApi;
