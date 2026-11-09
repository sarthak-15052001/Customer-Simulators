import { getVtfOrigin } from "../../config/site";
import { Box, Link, Pill, Typography } from "../ui";
import { LandingFeatureCard } from "./LandingFeatureCard";
import { LANDING_FEATURE_CONFIGS } from "./landingFeatures";
import {
  LANDING_CONTAINER_CLASS,
  landingBottomPillsSx,
  landingContentSx,
  landingDisclaimerSx,
  landingFeaturesGridSx,
  landingSiteLinkSx,
} from "./landing.ui";

type Props = {
  indicative: string;
  siteLabel: string;
  reviews: string;
  history: string;
  cardText: (key: string, field: "title" | "desc" | "badge") => string;
};

export function LandingFeaturesSection({
  indicative,
  siteLabel,
  reviews,
  history,
  cardText,
}: Props) {
  return (
    <Box className={LANDING_CONTAINER_CLASS} sx={landingContentSx}>
      <Typography sx={landingDisclaimerSx}>
        {indicative}{" "}
        <Link
          href={getVtfOrigin()}
          target="_blank"
          rel="noreferrer"
          sx={landingSiteLinkSx}
        >
          {siteLabel}
        </Link>
      </Typography>

      <Box sx={landingFeaturesGridSx}>
        {LANDING_FEATURE_CONFIGS.map((cfg) => (
          <LandingFeatureCard
            key={cfg.key}
            title={cardText(cfg.key, "title")}
            desc={cardText(cfg.key, "desc")}
            badge={cardText(cfg.key, "badge")}
            badgeTone={cfg.badgeTone}
            Icon={cfg.Icon}
            iconBg={cfg.iconBg}
          />
        ))}
      </Box>

      <Box sx={landingBottomPillsSx}>
        <Pill label={reviews} vtfTone="softNavy" sx={{ fontWeight: 700 }} />
        <Pill label={history} vtfTone="softOrange" sx={{ fontWeight: 700 }} />
      </Box>
    </Box>
  );
}
