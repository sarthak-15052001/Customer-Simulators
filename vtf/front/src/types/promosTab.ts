import type { FamilyState } from "./familyTab";
import type { SejourState } from "./stayTab";
import type { VtfVillage } from "../data/vtfStay";
import type { StayEstimateApiResult } from "../api/stayEstimate.api";

export type PromosTabProps = {
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
  onChange: (next: SejourState) => void;
  onFamilyChange?: (next: FamilyState) => void;
  serverEstimate?: StayEstimateApiResult | null;
};
