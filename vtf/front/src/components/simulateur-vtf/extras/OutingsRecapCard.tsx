import SummarizeRoundedIcon from "@mui/icons-material/SummarizeRounded";
import { Box, Typography } from "../../ui";

import { formatEuro } from "../../../utils/currency";
import { useTranslation } from "../../../contexts/LanguageContext";
import { VtfGlassCard } from "../../shared/VtfGlassCard";

type Props = {
  freePlanned: number;
  paidPlanned: number;
  paidTotal: number;
};

export function OutingsRecapCard({
  freePlanned,
  paidPlanned,
  paidTotal,
}: Props) {
  const { t } = useTranslation();
  const te = (k: string) => t(`simulateur.extras.${k}`);

  return (
    <VtfGlassCard
      title={te("outingsRecapTitle")}
      headingIcon={<SummarizeRoundedIcon />}
      headingAccent="navy"
    >
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            p: 1.25,
            borderRadius: 2,
            bgcolor: "rgba(16,185,129,0.10)",
            border: "1px solid rgba(16,185,129,0.18)",
          }}
        >
          <Typography
            sx={{ fontSize: 'var(--vtf-font-sm)', fontWeight: 950, color: "var(--vtf-navy)" }}
          >
            {te("outingsFreeLine")
              .replace("{{count}}", String(freePlanned))
              .replace("{{suffix}}", freePlanned > 1 ? te("pluralS") : "")}
          </Typography>
          <Typography sx={{ fontSize: 'var(--vtf-font-sm)', fontWeight: 950, color: "#047857" }}>
            {formatEuro(0)}
          </Typography>
        </Box>

        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            p: 1.25,
            borderRadius: 2,
            bgcolor: "rgba(var(--vtf-orange-rgb), 0.10)",
            border: "1px solid rgba(var(--vtf-orange-rgb), 0.18)",
          }}
        >
          <Typography
            sx={{ fontSize: 'var(--vtf-font-sm)', fontWeight: 950, color: "var(--vtf-navy)" }}
          >
            {te("outingsPaidLine")
              .replace("{{count}}", String(paidPlanned))
              .replace("{{suffix}}", paidPlanned > 1 ? te("pluralS") : "")}
          </Typography>
          <Typography
            sx={{
              fontSize: 'var(--vtf-font-sm)',
              fontWeight: 950,
              color: "rgba(185, 28, 28, 0.9)",
            }}
          >
            {formatEuro(paidTotal)}
          </Typography>
        </Box>
      </Box>
    </VtfGlassCard>
  );
}
