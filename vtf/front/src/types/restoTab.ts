import type { FamilyState } from "./familyTab";
import type { SejourState } from "./stayTab";
import type { VtfVillage } from "../data/vtfStay";
import type { SejourEstimate } from "../utils/stayEstimate";

export type RestoMealId = string;

export type RestoTabProps = {
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
  serverEstimate?: SejourEstimate | null;
  serverEstimateLoading?: boolean;
  onChange: (next: SejourState) => void;
};
