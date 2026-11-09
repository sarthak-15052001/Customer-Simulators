import { Typography } from "../../../../ui";
import { formatEuro } from "../../_format";
import { RECAP_META } from "../../recapCard.ui";
import { useTranslation } from "../../../../../contexts/LanguageContext";
import { useSimulateurTabTranslation } from "../../../../../hooks/useSimulateurTabTranslation";
import type { VtfSeasonKey } from "../../../../../data/vtfExtras";
import { saisonKeyFromSejour } from "../../../../../utils/extrasTab";
import {
  activityDisplayTitle,
  paidActivityUnitPrice,
} from "../../../../../utils/regionActivitiesMap";
import type { BudgetExpandPanelWithVillageProps } from "../budgetBars.types";
import {
  BudgetDetailItemRow,
  BudgetDetailSectionLabel,
} from "../budgetBarDetailRow.ui";
import { budgetBarActivityIcon } from "../icons/budgetBarActivityIcon";
import { useSelectedBudgetActivities } from "../hooks/useSelectedBudgetActivities";
import {
  BudgetExpandPanelShell,
  BudgetPanelEmptyNote,
  BudgetPanelHeading,
  BudgetPanelSubtotal,
} from "../budgetBars.ui";

export function ActivitiesBudgetExpandPanel({
  family,
  sejour,
  village,
  estimate,
}: BudgetExpandPanelWithVillageProps) {
  const td = useSimulateurTabTranslation("details");
  const { t } = useTranslation();
  const te = (k: string) => t(`simulateur.extras.${k}`);
  const adultWord = family.adultes > 1 ? te("adultPlural") : te("adultSingular");
  const childWord =
    family.enfants.length > 1 ? te("childPlural") : te("childSingular");

  const region = village?.region?.trim() || null;
  const saisonKey =
    (sejour.serverSeasonKey as VtfSeasonKey) || saisonKeyFromSejour(sejour);
  const extra = sejour.extraActivities;

  const {
    selectedFree,
    selectedPaid,
    hasSelection,
    isLoading,
    freeQtyById,
    paidQtyById,
  } = useSelectedBudgetActivities({
    region,
    saisonKey,
    freeQtyById: extra?.freeQtyById ?? {},
    paidQtyById: extra?.paidQtyById ?? {},
  });

  const amount =
    estimate.budgetBreakdown?.activities ?? estimate.activitiesTotal;

  return (
    <BudgetExpandPanelShell theme="activities">
      <BudgetPanelHeading>{td("recapCard.details.activities")}</BudgetPanelHeading>

      {isLoading ? (
        <BudgetPanelEmptyNote>{td("bars.loadingDetails")}</BudgetPanelEmptyNote>
      ) : !hasSelection ? (
        <BudgetPanelEmptyNote>
          {td("bars.noActivitiesSelected")}
        </BudgetPanelEmptyNote>
      ) : (
        <>
          {selectedFree.length > 0 && (
            <>
              <BudgetDetailSectionLabel>{te("freeTitle")}</BudgetDetailSectionLabel>
              {selectedFree.map((a) => (
                <BudgetDetailItemRow
                  key={`free-${a.id}`}
                  tone="free"
                  icon={budgetBarActivityIcon(a.type)}
                  title={activityDisplayTitle(a.type, a.nom)}
                  subtitle={te("freePill")}
                  qty={freeQtyById[a.id] ?? 0}
                  amount={0}
                  amountLabel={te("freePill")}
                />
              ))}
            </>
          )}

          {selectedPaid.length > 0 && (
            <>
              <BudgetDetailSectionLabel>{te("paidTitle")}</BudgetDetailSectionLabel>
              <Typography sx={{ ...RECAP_META.caption, mb: 1 }}>
                {te("paidDisclaimer")}
              </Typography>
              {selectedPaid.map((a) => {
                const qty = paidQtyById[a.id] ?? 0;
                const unit = paidActivityUnitPrice(
                  a,
                  family.adultes,
                  family.enfants.length,
                );
                const subtitle = `${formatEuro(a.ad, { compact: true })} /${adultWord} · ${formatEuro(a.enf, { compact: true })} /${childWord}`;
                return (
                  <BudgetDetailItemRow
                    key={`paid-${a.id}`}
                    tone="paid"
                    icon={budgetBarActivityIcon(a.type)}
                    title={activityDisplayTitle(a.type, a.nom)}
                    subtitle={subtitle}
                    qty={qty}
                    amount={unit * qty}
                  />
                );
              })}
            </>
          )}

          {amount > 0 && (
            <BudgetPanelSubtotal
              label={td("recapCard.details.activitiesTotalLine")}
              value={formatEuro(amount)}
            />
          )}
        </>
      )}
    </BudgetExpandPanelShell>
  );
}
