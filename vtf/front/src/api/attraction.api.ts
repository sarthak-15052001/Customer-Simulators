import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";
import type { SejourEnvKey } from "../utils/stayTab";

export type Attraction = {
  id: string;
  nom: string;
  type: string;
  icon: string;
  /** Distance in km to the nearest village. */
  minKm: number;
  /** List of village IDs near this attraction. */
  villageIds: string[];
};

export const attractionApi = {
  getAttractions: async (env: SejourEnvKey): Promise<Attraction[]> => {
    const { data } = await apiClient.get<{ success: boolean; data: Attraction[] }>(
      ENDPOINTS.ATTRACTIONS.BASE,
      { params: { env } },
    );
    return data.data;
  },
};

export default attractionApi;
