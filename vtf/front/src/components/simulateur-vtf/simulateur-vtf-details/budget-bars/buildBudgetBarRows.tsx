import * as React from "react";
import HolidayVillageRoundedIcon from "@mui/icons-material/HolidayVillageRounded";
import LocalActivityRoundedIcon from "@mui/icons-material/LocalActivityRounded";
import RestaurantRoundedIcon from "@mui/icons-material/RestaurantRounded";
import DirectionsCarRoundedIcon from "@mui/icons-material/DirectionsCarRounded";
import type { StayBudgetBreakdown } from "../../../../utils/stayEstimate";
import type { BudgetBarKey } from "./budgetBars.types";

export type BudgetBarRowConfig = {
  key: BudgetBarKey;
  label: string;
  value: number;
  color: string;
  icon: React.ReactNode;
};

type TranslateDetails = (key: string) => string;

export function buildBudgetBarRows(
  bd: StayBudgetBreakdown,
  td: TranslateDetails,
): BudgetBarRowConfig[] {
  const rows: BudgetBarRowConfig[] = [];
  const push = (
    key: BudgetBarKey,
    label: string,
    value: number,
    color: string,
    icon: React.ReactNode,
  ) => {
    if (value > 0) rows.push({ key, label, value, color, icon });
  };

  push(
    "stay",
    td("bars.stay"),
    bd.stay,
    "var(--vtf-orange)",
    <HolidayVillageRoundedIcon />,
  );
  push(
    "activities",
    td("bars.activities"),
    bd.activities,
    "var(--vtf-green)",
    <LocalActivityRoundedIcon />,
  );
  push(
    "restoration",
    td("bars.resto"),
    bd.restoration,
    "var(--vtf-teal)",
    <RestaurantRoundedIcon />,
  );
  push(
    "transport",
    td("bars.transport"),
    bd.transport,
    "rgba(0, 68, 90, 0.85)",
    <DirectionsCarRoundedIcon />,
  );

  return rows;
}
