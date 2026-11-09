import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";
import type { VtfSeasonKey } from "../data/vtfExtras";

/** `GET /api/v1/regions/{region}/activities` row — matches `ActivitySerializer`. */
export type RegionActivityDto = {
  id: string;
  region?: string;
  kind?: string;
  nom: string;
  type: string;
  ad: number;
  enf: number;
  saisons: VtfSeasonKey[];
};

export type RegionActivitiesQuery = {
  kind?: "free" | "paid";
  season?: VtfSeasonKey | null;
};

function unwrapActivitiesPayload(data: unknown): unknown {
  if (Array.isArray(data)) return data;
  if (data && typeof data === "object") {
    const o = data as Record<string, unknown>;
    if (Array.isArray(o.data)) return o.data;
  }
  return data;
}

export const regionActivitiesApi = {
  getActivities: async (
    regionKey: string,
    query: RegionActivitiesQuery = {},
  ): Promise<RegionActivityDto[]> => {
    const path = ENDPOINTS.REGIONS.ACTIVITIES(regionKey);
    const params: Record<string, string> = {};
    if (query.kind) params.kind = query.kind;
    if (query.season) params.season = query.season;
    const { data } = await apiClient.get<unknown>(path, { params });
    const raw = unwrapActivitiesPayload(data);
    return Array.isArray(raw) ? (raw as RegionActivityDto[]) : [];
  },
};

export default regionActivitiesApi;
