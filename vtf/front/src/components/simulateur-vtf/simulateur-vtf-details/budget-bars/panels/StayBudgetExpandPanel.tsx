import { StayBudgetBreakdownContent } from "../../StayBudgetBreakdownContent";
import { useSimulateurTabTranslation } from "../../../../../hooks/useSimulateurTabTranslation";
import type { BudgetExpandPanelProps } from "../budgetBars.types";
import {
  BudgetExpandPanelShell,
  BudgetPanelHeading,
} from "../budgetBars.ui";

export function StayBudgetExpandPanel({
  family,
  estimate,
}: BudgetExpandPanelProps) {
  const td = useSimulateurTabTranslation("details");

  return (
    <BudgetExpandPanelShell theme="budget">
      <BudgetPanelHeading>{td("recapCard.details.budget")}</BudgetPanelHeading>
      <StayBudgetBreakdownContent family={family} estimate={estimate} />
    </BudgetExpandPanelShell>
  );
}
