import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";
import type { PaginatedResponse } from "../types/api";
import type { VtfVillage } from "../data/vtfStay";

export interface VillageQueryParams {
  limit?: number;
  offset?: number;
  region?: string | null;
  /** Server-side name / text filter (`GET /villages?search=…`). */
  search?: string | null;
  fEnv?: string | null;
  formule?: string | null;
  openOn?: string | null;
  dateDebut?: string | null;
  dateFin?: string | null;
  [key: string]: unknown;
}

function unwrapVillagePayload(data: unknown): VtfVillage {
  if (!data || typeof data !== "object") {
    throw new Error("Invalid village response");
  }
  const root = data as Record<string, unknown>;
  const node =
    root.data != null && typeof root.data === "object" ? root.data : root;
  return node as VtfVillage;
}

export const villageApi = {
  getVillageById: async (
    id: string,
    params?: {
      dateDebut?: string | null;
      dateFin?: string | null;
      openOn?: string | null;
      formule?: string | null;
    },
  ): Promise<VtfVillage> => {
    const { data } = await apiClient.get<unknown>(ENDPOINTS.VILLAGES.DETAILS(id), {
      params,
    });
    return unwrapVillagePayload(data);
  },

  getVillages: async (
    params?: VillageQueryParams,
  ): Promise<PaginatedResponse<VtfVillage>> => {
    const { data } = await apiClient.get(ENDPOINTS.VILLAGES.BASE, {
      params,
    });

    const root = data as { data?: PaginatedResponse<VtfVillage> } & Partial<
      PaginatedResponse<VtfVillage>
    >;

    const page = (root.data ?? root) as Partial<PaginatedResponse<VtfVillage>>;

    return {
      count: Number(page.count) || 0,
      next: page.next ?? null,
      previous: page.previous ?? null,
      results: Array.isArray(page.results) ? page.results : [],
    };
  },
};

export default villageApi;
