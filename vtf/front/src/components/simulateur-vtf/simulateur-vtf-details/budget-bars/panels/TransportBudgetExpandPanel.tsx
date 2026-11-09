import { RecapBreakdownRow } from "../../recapBreakdown.ui";
import { formatEuro } from "../../_format";
import { useTranslation } from "../../../../../contexts/LanguageContext";
import { useSimulateurTabTranslation } from "../../../../../hooks/useSimulateurTabTranslation";
import {
  useCarTransportCost,
  useFuels,
  useTrainTransportCost,
} from "../../../../../hooks/transport.hooks";
import { usePricingRules } from "../../../../../hooks/pricingRules.hooks";
import type { BudgetExpandPanelProps } from "../budgetBars.types";
import {
  BudgetExpandPanelShell,
  BudgetPanelHeading,
  BudgetPanelSubtotal,
} from "../budgetBars.ui";
import {
  buildTransportBudgetRows,
  shouldShowTransportSubtotal,
} from "./transportBudgetRows";

export function TransportBudgetExpandPanel({
  family,
  sejour,
  estimate,
}: Pick<BudgetExpandPanelProps, "family" | "sejour" | "estimate">) {
  const { t } = useTranslation();
  const td = useSimulateurTabTranslation("details");
  const tt = useSimulateurTabTranslation("transport");
  const trc = (k: string) => t(`simulateur.recap.${k}`);
  const { data: fuels = [] } = useFuels();
  const { data: pricingRules } = usePricingRules();

  const transport = sejour.transport;
  const amount = estimate.budgetBreakdown?.transport ?? estimate.transportTotal;
  const carEnabled = transport.mode === "car";
  const trainEnabled = transport.mode === "train";

  const { data: car } = useCarTransportCost(
    transport.distanceOneWayKm,
    transport.fuel,
    carEnabled,
  );

  const { data: trainCost } = useTrainTransportCost(
    family.adultes,
    family.enfants.length,
    trainEnabled,
  );

  const trainAdultOneWay = pricingRules?.payload?.defaults?.trainAdultOneWay;
  const trainChildOneWay = pricingRules?.payload?.defaults?.trainChildOneWay;

  const rows = buildTransportBudgetRows({
    transport,
    fuels,
    amount: trainEnabled ? (trainCost?.total ?? amount) : amount,
    car: carEnabled ? car : null,
    family,
    trainAdultOneWay,
    trainChildOneWay,
    tt,
    trc,
  });

  const showSubtotal = shouldShowTransportSubtotal(transport.mode, amount);

  return (
    <BudgetExpandPanelShell theme="transport">
      <BudgetPanelHeading>
        {td("recapCard.details.transportation")}
      </BudgetPanelHeading>
      {rows.map((row) => (
        <RecapBreakdownRow
          key={row.key}
          label={row.label}
          value={row.value}
          note={row.note}
        />
      ))}
      {showSubtotal && (
        <BudgetPanelSubtotal
          label={td("recapCard.details.transportTotalLine")}
          value={formatEuro(amount)}
        />
      )}
    </BudgetExpandPanelShell>
  );
}
