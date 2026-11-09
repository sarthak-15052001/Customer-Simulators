import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";

export type RegionSummary = {
  key: string;
  villageCount: number;
  freeActivityCount: number;
  paidActivityCount: number;
};

/** Many catalog endpoints return either `T[]` or `{ data: T[] }`. */
function unwrapEnvelopeArray<T>(data: unknown): T[] {
  const root = data as { data?: T[] } | T[];
  if (Array.isArray(root)) return root;
  const rows = (root as { data?: T[] }).data;
  return Array.isArray(rows) ? rows : [];
}

export const regionApi = {
  getRegions: async (): Promise<RegionSummary[]> => {
    const { data } = await apiClient.get<unknown>(ENDPOINTS.REGIONS.BASE);
    return unwrapEnvelopeArray<RegionSummary>(data);
  },
};

export default regionApi;
