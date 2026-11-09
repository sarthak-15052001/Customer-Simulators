import * as React from "react";
import type { FamilyState } from "../../types/familyTab";
import type { SejourState } from "../../types/stayTab";
import type { VtfVillage } from "../../data/vtfStay";
import type { FuelKey } from "../../data/vtfTransport";
import {
  VTF_TRANSPORT_DEFAULTS,
  type TransportMode,
} from "../../data/vtfTransport";
import { clampInt } from "../../utils/restoTab";
import { useSimulateurTabTranslation } from "../../hooks/useSimulateurTabTranslation";
import {
  useCarTransportCost,
  useFuels,
  useTrainTransportCost,
} from "../../hooks/transport.hooks";
import { usePricingRules } from "../../hooks/pricingRules.hooks";
import { TransportTabView } from "./transport/TransportTabView";

export type TransportTabProps = {
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
  onChange: (next: SejourState) => void;
};

const EMPTY_CAR = { kmAR: 0, fuelCost: 0, tollCost: 0, total: 0 };

export function TransportTab({ family, sejour, onChange }: TransportTabProps) {
  const tt = useSimulateurTabTranslation("transport");
  const transport = sejour.transport;

  const {
    data: fuels = [],
    isLoading: isFuelsLoading,
    isError: isFuelsError,
    refetch: refetchFuels,
  } = useFuels();

  const patchTransport = React.useCallback(
    (partial: Partial<typeof transport>) => {
      onChange({ ...sejour, transport: { ...transport, ...partial } });
    },
    [onChange, sejour, transport],
  );

  const onSetMode = React.useCallback(
    (mode: TransportMode) => patchTransport({ mode }),
    [patchTransport],
  );
  const onSetFuel = React.useCallback(
    (fuel: FuelKey) => patchTransport({ fuel }),
    [patchTransport],
  );
  const onSetDistance = React.useCallback(
    (distanceOneWayKm: number) =>
      patchTransport({
        distanceOneWayKm: clampInt(
          distanceOneWayKm,
          VTF_TRANSPORT_DEFAULTS.distanceMinKm,
          VTF_TRANSPORT_DEFAULTS.distanceMaxKm,
        ),
      }),
    [patchTransport],
  );

  const carEnabled = transport.mode === "car";
  const trainEnabled = transport.mode === "train";

  const {
    data: car,
    isFetching: isCarFetching,
    isError: isCarError,
    refetch: refetchCar,
  } = useCarTransportCost(
    transport.distanceOneWayKm,
    transport.fuel,
    carEnabled,
  );

  const { data: pricingRules } = usePricingRules();
  const trainAdultOneWay = pricingRules?.payload?.defaults?.trainAdultOneWay;
  const trainChildOneWay = pricingRules?.payload?.defaults?.trainChildOneWay;

  const {
    data: trainFromApi,
    isFetching: isTrainFetching,
    isError: isTrainError,
    refetch: refetchTrain,
  } = useTrainTransportCost(
    family.adultes,
    family.enfants.length,
    trainEnabled,
  );

  return (
    <TransportTabView
      tt={tt}
      mode={transport.mode}
      fuel={transport.fuel}
      distanceOneWayKm={transport.distanceOneWayKm}
      fuels={fuels}
      isFuelsLoading={isFuelsLoading}
      isFuelsError={isFuelsError}
      onRetryFuels={() => void refetchFuels()}
      onRetryCar={() => void refetchCar()}
      onRetryTrain={() => void refetchTrain()}
      onSetMode={onSetMode}
      onSetFuel={onSetFuel}
      onSetDistance={onSetDistance}
      car={car ?? EMPTY_CAR}
      trainTotal={trainFromApi?.total ?? 0}
      trainAdultOneWay={trainAdultOneWay}
      trainChildOneWay={trainChildOneWay}
      isCarEstimateLoading={carEnabled && isCarFetching && !car}
      isTrainEstimateLoading={
        trainEnabled && isTrainFetching && trainFromApi == null
      }
      isCarEstimateError={carEnabled && isCarError && !car}
      isTrainEstimateError={
        trainEnabled && isTrainError && trainFromApi == null
      }
    />
  );
}
