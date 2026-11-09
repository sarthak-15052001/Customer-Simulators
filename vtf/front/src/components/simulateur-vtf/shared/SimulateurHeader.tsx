import * as React from "react";
import { Box, Typography } from "../../ui";
import AutoGraphRoundedIcon from "@mui/icons-material/AutoGraphRounded";
import { useTranslation } from "../../../contexts/LanguageContext";

export const SimulateurHeader: React.FC = () => {
  const { t } = useTranslation();

  return (
    <Box
      className="rounded-3xl p-4 sm:p-5"
      sx={{
        background: "var(--vtf-mint-light)",
        border: "1px solid rgba(0,68,90,0.06)",
        boxShadow: "0 14px 38px rgba(0,68,90,0.08)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Decorative glow */}
      <Box
        sx={{
          position: "absolute",
          top: -40,
          right: -40,
          width: 140,
          height: 140,
          borderRadius: "50%",
          background: "rgba(242,166,128,0.12)",
          filter: "blur(45px)",
          pointerEvents: "none",
        }}
      />

      <Box className="flex items-start gap-3 relative z-10">
        <Box
          className="w-11 h-11 rounded-2xl flex items-center justify-center"
          sx={{
            background: `
              linear-gradient(
                135deg,
                rgba(242,166,128,0.20) 0%,
                rgba(255,255,255,0.96) 55%,
                rgba(174,218,196,0.22) 100%
              )
            `,
            border: "1px solid rgba(0,68,90,0.08)",
            boxShadow: `
              0 10px 24px rgba(0,68,90,0.08),
              inset 0 2px 8px rgba(255,255,255,0.55)
            `,
            flexShrink: 0,
          }}
        >
          <AutoGraphRoundedIcon
            sx={{
              color: "var(--vtf-navy)",
              fontSize: 20,
            }}
          />
        </Box>

        <Box className="min-w-0">
          <Typography
            variant="h4"
            sx={{
              fontWeight: 950,
              color: "var(--vtf-navy)",
              fontSize: { xs: 'var(--vtf-font-lg)', sm: 24 },
              letterSpacing: "-0.025em",
              mb: 0.35,
              lineHeight: 1.1,
            }}
          >
            {t("simulateur.page.title")}
          </Typography>

          <Typography
            sx={{
              color: "rgba(0,68,90,0.72)",
              fontWeight: 600,
              fontSize: { xs: 'var(--vtf-font-sm)', sm: 'var(--vtf-font-sm)' },
              maxWidth: { xs: "100%", sm: 700 },
              lineHeight: 1.55,
            }}
          >
            {t("simulateur.page.subtitle")}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
};
