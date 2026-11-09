import * as React from "react";
import RestaurantMenuRoundedIcon from "@mui/icons-material/RestaurantMenuRounded";
import WbSunnyRoundedIcon from "@mui/icons-material/WbSunnyRounded";
import DinnerDiningRoundedIcon from "@mui/icons-material/DinnerDiningRounded";
import LunchDiningRoundedIcon from "@mui/icons-material/LunchDiningRounded";

export function budgetBarMealIcon(mealId: string): React.ReactNode {
  const k = mealId.toLowerCase();
  if (k.includes("petit") || k.includes("break") || k.includes("matin")) {
    return <WbSunnyRoundedIcon />;
  }
  if (k.includes("midi") || k.includes("lunch") || k.includes("dej")) {
    return <LunchDiningRoundedIcon />;
  }
  if (k.includes("soir") || k.includes("dinner") || k.includes("diner")) {
    return <DinnerDiningRoundedIcon />;
  }
  return <RestaurantMenuRoundedIcon />;
}
