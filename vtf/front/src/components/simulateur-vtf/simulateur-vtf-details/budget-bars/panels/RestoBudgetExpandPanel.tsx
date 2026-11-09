import { formatEuro } from "../../_format";
import { useSimulateurTabTranslation } from "../../../../../hooks/useSimulateurTabTranslation";
import { restoNoteKey, EMPTY_RESTO_QTY_MAP } from "../../../../../utils/restoTab";
import type { BudgetExpandPanelProps } from "../budgetBars.types";
import { BudgetDetailItemRow } from "../budgetBarDetailRow.ui";
import { budgetBarMealIcon } from "../icons/budgetBarMealIcon";
import { useSelectedRestoLines } from "../hooks/useSelectedRestoLines";
import {
  BudgetExpandPanelShell,
  BudgetPanelEmptyNote,
  BudgetPanelHeading,
  BudgetPanelSubtotal,
} from "../budgetBars.ui";
import { Typography } from "../../../../ui";
import { RECAP_META } from "../../recapCard.ui";

export function RestoBudgetExpandPanel({
  family,
  sejour,
  estimate,
}: BudgetExpandPanelProps) {
  const td = useSimulateurTabTranslation("details");
  const tr = useSimulateurTabTranslation("resto");
  const qtyByMealId = sejour.resto?.qtyByMealId ?? EMPTY_RESTO_QTY_MAP;
  const amount = estimate.budgetBreakdown?.restoration ?? estimate.restoTotal;
  const adultWord = family.adultes > 1 ? tr("adultPlural") : tr("adultSingular");
  const childWord =
    family.enfants.length > 1 ? tr("childPlural") : tr("childSingular");

  const { lines, isPending, hasSelection } = useSelectedRestoLines({
    family,
    qtyByMealId,
  });

  return (
    <BudgetExpandPanelShell theme="resto">
      <BudgetPanelHeading>{td("recapCard.details.restoration")}</BudgetPanelHeading>
      <Typography sx={{ ...RECAP_META.caption, mb: 1.25 }}>
        {tr(restoNoteKey(sejour.formule))}
      </Typography>

      {isPending && !hasSelection && amount <= 0 ? (
        <BudgetPanelEmptyNote>{td("bars.loadingDetails")}</BudgetPanelEmptyNote>
      ) : !hasSelection ? (
        <BudgetPanelEmptyNote>{td("bars.noMeals")}</BudgetPanelEmptyNote>
      ) : (
        <>
          {lines.map(({ meal, qty, lineTotal }) => {
            const subtitle = `${formatEuro(Math.round(meal.priceAdult), { compact: true })} /${adultWord} · ${formatEuro(Math.round(meal.priceChild), { compact: true })} /${childWord}`;
            return (
              <BudgetDetailItemRow
                key={meal.id}
                tone="resto"
                icon={budgetBarMealIcon(meal.id)}
                title={meal.label}
                subtitle={subtitle}
                qty={qty}
                amount={lineTotal}
              />
            );
          })}
          {amount > 0 && (
            <BudgetPanelSubtotal
              label={td("recapCard.details.restorationTotalLine")}
              value={formatEuro(amount)}
            />
          )}
        </>
      )}
    </BudgetExpandPanelShell>
  );
}
