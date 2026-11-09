import type { ComponentType } from "react";
import type { VtfPillTone } from "../ui/Pill";
import {
  VtfIconAdvantages,
  VtfIconAssistance,
  VtfIconEssentials,
  VtfIconSerenity,
} from "./VtfLandingIcons";

export type LandingFeatureKey =
  | "essentials"
  | "advantages"
  | "aids"
  | "serenity";

export type LandingFeatureIconProps = { size?: number };

export type LandingFeatureConfig = {
  key: LandingFeatureKey;
  badgeTone: VtfPillTone;
  iconBg: string;
  Icon: ComponentType<LandingFeatureIconProps>;
};

export const LANDING_FEATURE_CONFIGS = [
  {
    key: "essentials",
    badgeTone: "softOrange",
    iconBg: "var(--vtf-soft-orange)",
    Icon: VtfIconEssentials,
  },
  {
    key: "advantages",
    badgeTone: "softTeal",
    iconBg: "var(--vtf-soft-teal)",
    Icon: VtfIconAdvantages,
  },
  {
    key: "aids",
    badgeTone: "softGreen",
    iconBg: "var(--vtf-soft-green)",
    Icon: VtfIconAssistance,
  },
  {
    key: "serenity",
    badgeTone: "softNavy",
    iconBg: "var(--vtf-soft-navy)",
    Icon: VtfIconSerenity,
  },
] as const satisfies readonly LandingFeatureConfig[];
