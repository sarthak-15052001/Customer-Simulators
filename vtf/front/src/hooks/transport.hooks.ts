import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { transportApi } from "../api/transport.api";
import type { FuelKey } from "../data/vtfTransport";

export const TRANSPORT_KEYS = {
  all: ["transport"] as const,
  fuels: () => [...TRANSPORT_KEYS.all, "fuels"] as const,
  car: (distanceOneWayKm: number, fuel: FuelKey) =>
    [...TRANSPORT_KEYS.all, "car", distanceOneWayKm, fuel] as const,
  train: (adults: number, children: number) =>
    [...TRANSPORT_KEYS.all, "train", adults, children] as const,
};

export function useFuels() {
  return useQuery({
    queryKey: TRANSPORT_KEYS.fuels(),
    queryFn: () => transportApi.fetchFuels(),
    staleTime: 10 * 60 * 1000,
  });
}

export function useCarTransportCost(
  distanceOneWayKm: number,
  fuel: FuelKey,
  enabled: boolean,
) {
  return useQuery({
    queryKey: TRANSPORT_KEYS.car(distanceOneWayKm, fuel),
    queryFn: () =>
      transportApi.fetchCarCost({ distanceOneWayKm, fuel }),
    enabled,
    staleTime: 60 * 1000,
    placeholderData: keepPreviousData,
  });
}

export function useTrainTransportCost(
  adults: number,
  children: number,
  enabled: boolean,
) {
  return useQuery({
    queryKey: TRANSPORT_KEYS.train(adults, children),
    queryFn: () =>
      transportApi.fetchTrainCost({ adults, children }),
    enabled,
    staleTime: 60 * 1000,
    placeholderData: keepPreviousData,
  });
}
