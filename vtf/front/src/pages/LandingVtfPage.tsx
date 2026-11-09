import { useCallback } from "react";
import { Box } from "../components/ui";
import { LandingFeaturesSection } from "../components/landing/LandingFeaturesSection";
import { LandingHero } from "../components/landing/LandingHero";
import { landingPageSx } from "../components/landing/landing.ui";
import { useHeadlineCycle } from "../components/landing/useHeadlineCycle";
import { useTranslation } from "../contexts/LanguageContext";
import { LandingHeroCurve } from "../components/landing/LandingHeroCurve";
import { LandingIndexMap } from "../components/landing/index-map/LandingIndexMap";
export default function LandingVtfPage() {
  const { t } = useTranslation();

  const title1 = t("landing.hero.title1");
  const title2 = t("landing.hero.title2");
  const headlineCycle = useHeadlineCycle(title1, title2);

  const cardText = useCallback(
    (key: string, field: "title" | "desc" | "badge") =>
      t(`landing.cards.${key}.${field}`),
    [t],
  );

  return (
    <Box>
      <Box sx={landingPageSx}>
        <Box sx={{ position: "relative" }}>
          <LandingHero
            script={t("landing.hero.script")}
            title1={title1}
            title2={title2}
            desc={t("landing.hero.desc")}
            cta={t("landing.hero.cta")}
            precision={t("landing.hero.precision")}
            offers={t("landing.hero.offers")}
            headlineCycle={headlineCycle}
          />
          <LandingHeroCurve />
        </Box>

        <Box
          sx={{
            position: "relative",
            overflow: "hidden",
          }}
        >
          <LandingFeaturesSection
            indicative={t("landing.info.indicative")}
            siteLabel={t("footer.links.site")}
            reviews={t("landing.info.reviews")}
            history={t("landing.info.history")}
            cardText={cardText}
          />
        </Box>
      </Box>

      <LandingIndexMap
        eyebrow={t("landing.indexMap.eyebrow")}
        title={t("landing.indexMap.title")}
        selectRegionLabel={t("landing.indexMap.selectRegion")}
      />
    </Box>
  );
}
