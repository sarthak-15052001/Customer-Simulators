import { useEffect, useState } from "react";

import { useTranslation } from "../../../contexts/LanguageContext";
import { Box, Typography } from "../../ui";

import {
  backToTopArrowSvgStyle,
  backToTopBgSvgStyle,
  backToTopButtonSx,
  backToTopRootSx,
  backToTopTextSx,
} from "./backToTop.ui";

export function BackToTop() {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);

  const label = t("common.backToTop");
  const ariaLabel = label.replace(/\n/g, " ");

  useEffect(() => {
    const handleScroll = () => {
      setVisible(window.scrollY > 100);
    };

    handleScroll();

    window.addEventListener("scroll", handleScroll, {
      passive: true,
    });

    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const handleBackToTop = () => {
    const startPosition = window.scrollY;
    const duration = 950;
    const startTime = performance.now();

    const easeInSlowOutFast = (progress: number) => {
      if (progress < 0.72) return 2.8 * progress * progress * progress;
      return 1 - Math.pow(1 - progress, 4);
    };

    const animateScroll = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      const eased = easeInSlowOutFast(progress);
      const nextPosition = startPosition * (1 - eased);

      window.scrollTo({ top: nextPosition, behavior: "auto" });

      if (progress < 1) requestAnimationFrame(animateScroll);
    };

    requestAnimationFrame(animateScroll);
  };

  if (!visible) return null;

  return (
    <Box
      role="button"
      tabIndex={0}
      aria-label={ariaLabel}
      onClick={handleBackToTop}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleBackToTop();
        }
      }}
      sx={backToTopRootSx}
    >
      <Box sx={backToTopButtonSx}>
        {/* Background SVG (same as inspect) */}
        <svg aria-hidden="true" viewBox="0 0 6 8" style={backToTopBgSvgStyle}>
          <path
            fill="#AEDAC4"
            fillRule="evenodd"
            d="M.883 2.365L3 0l2.14 2.39c.53.596.86 1.412.86 2.312C6 6.524 4.657 8 3 8S0 6.524 0 4.702c0-.84.286-1.607.758-2.19l.125-.147z"
          />
        </svg>

        {/* Arrow SVG (same as inspect) */}
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          style={backToTopArrowSvgStyle}
        >
          <path fill="#00445A" d="M12 4l-6 6h4v8h4v-8h4l-6-6z" />
        </svg>

        <Typography sx={backToTopTextSx}>{label}</Typography>
      </Box>
    </Box>
  );
}
