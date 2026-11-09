import type { CarCostResult } from "../../../../../api/transport.api";
import type { FuelOption } from "../../../../../api/transport.api";
import type { FamilyState } from "../../../../../types/familyTab";
import type { SejourState } from "../../../../../types/stayTab";
import { formatEuro } from "../../_format";

export type TransportDetailRow = {
  key: string;
  label: string;
  value: string;
  note?: string;
};

type Translate = (key: string) => string;

export function buildTransportBudgetRows(args: {
  transport: SejourState["transport"];
  fuels: FuelOption[];
  amount: number;
  car?: CarCostResult | null;
  family?: Pick<FamilyState, "adultes" | "enfants">;
  trainAdultOneWay?: number;
  trainChildOneWay?: number;
  tt: Translate;
  trc?: Translate;
}): TransportDetailRow[] {
  const {
    transport,
    fuels,
    amount,
    car,
    family,
    trainAdultOneWay,
    trainChildOneWay,
    tt,
    trc,
  } = args;

  const fuelOption =
    fuels.find((f) => f.key === transport.fuel) ??
    ({
      key: transport.fuel,
      label: transport.fuel,
      costPerKm: 0,
    } as FuelOption);
  const fuelLabel = fuelOption.label;
  const costPerKmLabel = formatEuro(fuelOption.costPerKm, {
    compact: true,
    decimals: 2,
    suffix: "/km",
  });

  if (transport.mode === "car") {
    const kmAR = car?.kmAR ?? transport.distanceOneWayKm * 2;
    const rows: TransportDetailRow[] = [
      {
        key: "mode",
        label: tt("modeCar"),
        value: tt("carRoundTrip").replace("{{km}}", String(kmAR)),
      },
      {
        key: "distance",
        label: tt("distanceOneWay"),
        value: `${transport.distanceOneWayKm} km`,
      },
      {
        key: "fuel",
        label: tt("fuelTitle"),
        value: fuelLabel,
        note: costPerKmLabel,
      },
    ];

    if (car) {
      rows.push(
        {
          key: "fuelCost",
          label: tt("fuel"),
          value: `~${formatEuro(car.fuelCost)}`,
        },
        {
          key: "tolls",
          label: tt("tolls"),
          value: `~${formatEuro(car.tollCost)}`,
        },
      );
    } else if (amount > 0) {
      rows.push({
        key: "estimate",
        label: tt("total"),
        value: `~${formatEuro(amount)}`,
      });
    }

    return rows;
  }

  if (transport.mode === "train") {
    const adultLabel = trc
      ? family && family.adultes > 1
        ? trc("adultMany")
        : trc("adultOne")
      : "adult(s)";
    const childLabel = trc
      ? family && family.enfants.length > 1
        ? trc("childMany")
        : trc("childOne")
      : "child(ren)";

    const rows: TransportDetailRow[] = [
      {
        key: "mode",
        label: tt("modeTrain"),
        value: tt("trainTitle"),
      },
    ];

    if (family) {
      const passengers = [
        `${family.adultes} ${adultLabel}`,
        family.enfants.length > 0
          ? `${family.enfants.length} ${childLabel}`
          : null,
      ]
        .filter(Boolean)
        .join(" · ");
      rows.push({
        key: "passengers",
        label: tt("trainPassengers"),
        value: passengers,
      });
    }

    if (trainAdultOneWay != null && trainChildOneWay != null) {
      const ratesNote = tt("trainNote")
        .replace("{{adult}}", formatEuro(trainAdultOneWay))
        .replace("{{child}}", formatEuro(trainChildOneWay));
      const target = rows.find((r) => r.key === "passengers") ?? rows[0];
      if (target) {
        target.note = ratesNote;
      }
    }

    return rows;
  }

  return [
    {
      key: "mode",
      label: tt("modeOnSite"),
      value: "-",
      note: tt("onSiteNote"),
    },
  ];
}

/** Whether the transport expand panel should show a subtotal row. */
export function shouldShowTransportSubtotal(
  mode: SejourState["transport"]["mode"],
  amount: number,
): boolean {
  return mode !== "onSite" && amount > 0;
}
