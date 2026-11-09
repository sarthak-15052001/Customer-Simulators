import apiClient from "./client";
import { ENDPOINTS } from "./endpoints";
import type { FuelKey } from "../data/vtfTransport";

export type FuelOption = {
  key: FuelKey;
  label: string;
  costPerKm: number;
};

/** Used only when `GET /fuels` fails — matches backend seed data. */
const FUELS_FALLBACK: FuelOption[] = [
  { key: "essence", label: "Essence", costPerKm: 0.12 },
  { key: "diesel", label: "Diesel", costPerKm: 0.09 },
  { key: "electrique", label: "Électrique", costPerKm: 0.04 },
];

export type CarCostResult = {
  kmAR: number;
  fuelCost: number;
  tollCost: number;
  total: number;
};

export type TrainCostResult = {
  total: number;
};

type ApiWrapped<T> = {
  success: boolean;
  message: string;
  data: T;
};

function unwrapData<T>(payload: unknown): T {
  if (payload && typeof payload === "object" && "data" in payload) {
    return (payload as ApiWrapped<T>).data;
  }
  return payload as T;
}

export async function fetchFuels(): Promise<FuelOption[]> {
  const { data } = await apiClient.get<ApiWrapped<FuelOption[]> | FuelOption[]>(
    ENDPOINTS.FUELS,
  );
  const items = unwrapData<FuelOption[]>(data);
  return Array.isArray(items) && items.length > 0 ? items : FUELS_FALLBACK;
}

export async function fetchCarCost(body: {
  distanceOneWayKm: number;
  fuel: FuelKey;
}): Promise<CarCostResult> {
  const { data } = await apiClient.post<ApiWrapped<CarCostResult> | CarCostResult>(
    ENDPOINTS.TRANSPORT.CAR,
    body,
  );
  return unwrapData<CarCostResult>(data);
}

export async function fetchTrainCost(body: {
  adults: number;
  children: number;
}): Promise<TrainCostResult> {
  const { data } = await apiClient.post<ApiWrapped<TrainCostResult> | TrainCostResult>(
    ENDPOINTS.TRANSPORT.TRAIN,
    body,
  );
  return unwrapData<TrainCostResult>(data);
}

export const transportApi = {
  fetchFuels,
  fetchCarCost,
  fetchTrainCost,
};
