import type { FamilyState } from "./familyTab";
import type { SejourState } from "./stayTab";
import type { VtfVillage } from "../data/vtfStay";
import type { SejourEstimate } from "../utils/stayEstimate";

export type ExtrasTabProps = {
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
  onChange: (next: SejourState) => void;
  serverEstimate?: SejourEstimate | null;
  serverEstimateLoading?: boolean;
  serverEstimateError?: boolean;
  serverEstimateErrorMessage?: string | null;
  onRetryEstimate?: () => void;
};
