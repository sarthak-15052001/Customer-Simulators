import apiClient from "./client";
import ENDPOINTS from "./endpoints";
import type { PromoChoice } from "../data/vtfPromos";

type ApiWrapped<T> = {
  success?: boolean;
  message?: string;
  data?: T;
};

function unwrapData<T>(payload: unknown): T {
  if (payload && typeof payload === "object" && "data" in payload) {
    return (payload as ApiWrapped<T>).data as T;
  }
  return payload as T;
}

export async function fetchPromoCatalog(): Promise<PromoChoice[]> {
  const { data } = await apiClient.get<PromoChoice[] | ApiWrapped<PromoChoice[]>>(
    ENDPOINTS.PROMOS.CATALOG,
  );
  const items = unwrapData<PromoChoice[]>(data);
  return Array.isArray(items) ? items : [];
}

export type AvailablePromosInput = {
  dateDebut: string;
  dateFin: string;
  villageId: string;
  isSoloParent: boolean;
  quinzaineFutee: boolean;
  now?: string;
};

export async function computeAvailablePromos(
  input: AvailablePromosInput,
): Promise<PromoChoice[]> {
  const { data } = await apiClient.post<PromoChoice[] | ApiWrapped<PromoChoice[]>>(
    ENDPOINTS.PROMOS.AVAILABLE,
    input,
  );
  const items = unwrapData<PromoChoice[]>(data);
  return Array.isArray(items) ? items : [];
}

export const promosApi = {
  fetchPromoCatalog,
  computeAvailablePromos,
};

export default promosApi;
