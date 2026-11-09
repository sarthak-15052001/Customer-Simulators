import AutoGraphRoundedIcon from "@mui/icons-material/AutoGraphRounded";
import EuroSymbol from "@mui/icons-material/EuroSymbol";
import { Link as RouterLink } from "react-router-dom";
import { Box, Button, Typography } from "../ui";
import { AnimatedText } from "./AnimatedText";
import { LandingHeroCurve } from "./LandingHeroCurve";
import {
  HEADLINE_RENDER_STAGGER_MS,
  HEADLINE_TITLE2_RENDER_DELAY_MS,
} from "../../utils/landing.constants";
import {
  LANDING_CONTAINER_CLASS,
  landingHeroBlob,
  landingHeroCtaSx,
  landingHeroDescSx,
  landingHeroGlowSx,
  landingHeroScriptSx,
  landingHeroStatsSx,
  landingHeroSx,
  landingHeroTitleSx,
  landingStatItemSx,
  landingStatLabelSx,
} from "./landing.ui";

type Props = {
  script: string;
  title1: string;
  title2: string;
  desc: string;
  cta: string;
  precision: string;
  offers: string;
  headlineCycle: number;
};

export function LandingHero({
  script,
  title1,
  title2,
  desc,
  cta,
  precision,
  offers,
  headlineCycle,
}: Props) {
  return (
    <Box sx={landingHeroSx}>
      <Box sx={landingHeroGlowSx} />
      <Box
        sx={landingHeroBlob(-100, "left", "rgba(var(--vtf-orange-rgb),0.14)")}
      />
      <Box
        sx={landingHeroBlob(60, "right", "rgba(var(--vtf-teal-rgb),0.12)")}
      />

      <Box className={LANDING_CONTAINER_CLASS}>
        <Box sx={{ textAlign: "center", maxWidth: 850, mx: "auto" }}>
          <Typography className="vtf-script-font" sx={landingHeroScriptSx}>
            {script}
          </Typography>

          <Typography variant="h1" sx={landingHeroTitleSx}>
            <Box component="span" sx={{ display: "block", mb: 1 }}>
              <AnimatedText
                text={title1}
                staggerMs={HEADLINE_RENDER_STAGGER_MS}
                cycleKey={headlineCycle}
              />
            </Box>
            <Box
              component="span"
              sx={{ display: "block", color: "var(--vtf-orange)" }}
            >
              <AnimatedText
                text={title2}
                startDelayMs={HEADLINE_TITLE2_RENDER_DELAY_MS}
                staggerMs={HEADLINE_RENDER_STAGGER_MS}
                cycleKey={headlineCycle}
              />
            </Box>
          </Typography>

          <Typography sx={landingHeroDescSx}>{desc}</Typography>

          <RouterLink to="/simulateur-vtf" style={{ textDecoration: "none" }}>
            <Button
              variant="contained"
              vtfVariant="orangeFill"
              className="vtf-pill vtf-button-animation"
              sx={landingHeroCtaSx}
            >
              {cta}
            </Button>
          </RouterLink>

          <Box sx={landingHeroStatsSx}>
            <Box sx={landingStatItemSx}>
              <AutoGraphRoundedIcon
                sx={{ color: "var(--vtf-orange)", fontSize: 22 }}
              />
              <Typography variant="body2" sx={landingStatLabelSx}>
                {precision}
              </Typography>
            </Box>
            <Box sx={landingStatItemSx}>
              <EuroSymbol sx={{ color: "var(--vtf-green)", fontSize: 22 }} />
              <Typography variant="body2" sx={landingStatLabelSx}>
                {offers}
              </Typography>
            </Box>
          </Box>
        </Box>
      </Box>

      <LandingHeroCurve />
    </Box>
  );
}
