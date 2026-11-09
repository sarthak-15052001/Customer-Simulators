import * as React from "react";
import LocalActivityRoundedIcon from "@mui/icons-material/LocalActivityRounded";
import ParkRoundedIcon from "@mui/icons-material/ParkRounded";
import SportsRoundedIcon from "@mui/icons-material/SportsRounded";
import PoolRoundedIcon from "@mui/icons-material/PoolRounded";
import MuseumRoundedIcon from "@mui/icons-material/MuseumRounded";
import HikingRoundedIcon from "@mui/icons-material/HikingRounded";
import AttractionsRoundedIcon from "@mui/icons-material/AttractionsRounded";

/** Heuristic icon from activity type label (catalog `type` field). */
export function budgetBarActivityIcon(type: string): React.ReactNode {
  const t = type.toLowerCase();
  if (
    t.includes("parc") ||
    t.includes("nature") ||
    t.includes("jardin") ||
    t.includes("plage")
  ) {
    return <ParkRoundedIcon />;
  }
  if (
    t.includes("sport") ||
    t.includes("vélo") ||
    t.includes("velo") ||
    t.includes("ski")
  ) {
    return <SportsRoundedIcon />;
  }
  if (t.includes("piscine") || t.includes("aquat")) {
    return <PoolRoundedIcon />;
  }
  if (t.includes("musée") || t.includes("musee") || t.includes("culture")) {
    return <MuseumRoundedIcon />;
  }
  if (t.includes("randonn") || t.includes("sentier")) {
    return <HikingRoundedIcon />;
  }
  if (t.includes("attraction") || t.includes("loisir")) {
    return <AttractionsRoundedIcon />;
  }
  return <LocalActivityRoundedIcon />;
}
