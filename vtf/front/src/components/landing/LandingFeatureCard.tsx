import type { ComponentType } from "react";
import { Box, Card, CardContent, Pill, Typography } from "../ui";
import type { VtfPillTone } from "../ui/Pill";
import type { LandingFeatureIconProps } from "./landingFeatures";
import {
  landingFeatureCardSx,
  landingFeatureDescSx,
  landingFeatureFooterSx,
  landingFeatureIconSx,
  landingFeatureTitleSx,
} from "./landing.ui";

type Props = {
  title: string;
  desc: string;
  badge: string;
  badgeTone: VtfPillTone;
  Icon: ComponentType<LandingFeatureIconProps>;
  iconBg: string;
};

export function LandingFeatureCard({
  title,
  desc,
  badge,
  badgeTone,
  Icon,
  iconBg,
}: Props) {
  return (
    <Card className="vtf-card-hover" sx={landingFeatureCardSx}>
      <CardContent sx={{ p: 4 }}>
        <Box sx={{ display: "flex", alignItems: "flex-start", gap: 3 }}>
          <Box sx={landingFeatureIconSx(iconBg)}>
            <Icon size={32} />
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography sx={landingFeatureTitleSx}>{title}</Typography>
            <Typography sx={landingFeatureDescSx}>{desc}</Typography>
          </Box>
        </Box>
        <Box sx={landingFeatureFooterSx}>
          <Pill size="small" label={badge} vtfTone={badgeTone} />
        </Box>
      </CardContent>
    </Card>
  );
}
