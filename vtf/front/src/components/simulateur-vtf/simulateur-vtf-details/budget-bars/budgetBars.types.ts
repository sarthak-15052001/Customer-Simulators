import type { FamilyState } from "../../../../types/familyTab";
import type { SejourState } from "../../../../types/stayTab";
import type { VtfVillage } from "../../../../data/vtfStay";
import type { SejourEstimate } from "../../../../utils/stayEstimate";

export type BudgetBarKey =
  | "stay"
  | "activities"
  | "restoration"
  | "transport";

export type BudgetBarsCardProps = {
  estimate: SejourEstimate | null;
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
};

export type BudgetExpandPanelProps = {
  family: FamilyState;
  sejour: SejourState;
  estimate: SejourEstimate;
};

export type BudgetExpandPanelWithVillageProps = BudgetExpandPanelProps & {
  village: VtfVillage | null;
};
