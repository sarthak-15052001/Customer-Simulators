import { Box, Typography } from "../../ui";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { VtfSectionHeading } from "../../shared/VtfSectionHeading";
import CompareArrowsRoundedIcon from "@mui/icons-material/CompareArrowsRounded";
import TrendingDownRoundedIcon from "@mui/icons-material/TrendingDownRounded";

import type { SejourEstimate } from "../../../utils/stayEstimate";
import { formatEuro, formatPercentInt } from "./_format";
import { useSimulateurTabTranslation } from "../../../hooks/useSimulateurTabTranslation";
import { RECAP_META, RECAP_TYPO } from "./recapCard.ui";

export function ComparatorCard({
  estimate,
}: {
  estimate: SejourEstimate | null;
}) {
  const td = useSimulateurTabTranslation("details");

  if (!estimate) return null;
  const total = Math.max(0, estimate.total);

  const hotelTotal = estimate.hotelEstimate;
  const eco = estimate.hotelSavings;

  if (eco <= 0 && hotelTotal <= total) return null;

  const dm = estimate.displayMetrics;
  const vtfCore =
    dm != null && Number.isFinite(dm.totalVtfStayOnly)
      ? dm.totalVtfStayOnly
      : null;
  const activitiesSlice = Math.max(0, estimate.activitiesTotal);
  const showVtfSplit =
    vtfCore != null &&
    activitiesSlice > 0 &&
    vtfCore + activitiesSlice === total;
  const savingsPctShown =
    dm != null && Number.isFinite(dm.savingsPct) ? dm.savingsPct : null;

  return (
    <VtfGlassCard glassSx={{ p: { xs: 2.5, sm: 3 } }}>
      <VtfSectionHeading
        title={td("comparator.title")}
        icon={<CompareArrowsRoundedIcon />}
        accent="navy"
      />
      <Box sx={{ mt: 0.5 }}>
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", sm: "1fr auto 1fr" },
            gap: 2,
            alignItems: "center",
            mb: 2,
          }}
        >
          <Box
            sx={{
              borderRadius: 4,
              p: 2.5,
              textAlign: "center",
              backgroundColor: "var(--vtf-green-soft)",
              border: "1px solid #D1E9E0",
              boxShadow: "0 4px 12px rgba(46, 125, 90, 0.04)",
            }}
          >
            <Typography
              sx={{
                fontSize: "var(--vtf-font-sm)",
                fontWeight: 950,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: "#2E7D5A",
                mb: 1,
              }}
            >
              {td("comparator.vtfLabel")}
            </Typography>
            <Typography
              sx={{
                ...RECAP_TYPO.comparatorAmount,
                color: "var(--vtf-teal)",
                mb: 1.25,
              }}
            >
              {formatEuro(total)}
            </Typography>
            {showVtfSplit && (
              <Typography
                sx={{
                  ...RECAP_META.bodyMuted,
                  color: "#2e7d5a",
                  mb: 0.75,
                }}
              >
                {td("comparator.vtfSplit")
                  .replace("{{vtfCore}}", formatEuro(vtfCore))
                  .replace("{{activities}}", formatEuro(activitiesSlice))}
              </Typography>
            )}
            <Typography sx={{ ...RECAP_META.bodyMuted, color: "#2e7d5a" }}>
              {td("comparator.vtfDesc")}
            </Typography>
          </Box>

          <Typography
            sx={{
              textAlign: "center",
              fontWeight: 900,
              color: "rgba(0,68,90,0.3)",
              fontSize: "var(--vtf-font-md)",
            }}
          >
            {td("comparator.vs")}
          </Typography>

          <Box
            sx={{
              borderRadius: 4,
              p: 2.5,
              textAlign: "center",
              bgcolor: "#fff5f5",
              border: "1px solid #fadada",
              boxShadow: "0 4px 12px rgba(192, 57, 43, 0.04)",
            }}
          >
            <Typography
              sx={{
                fontSize: "var(--vtf-font-sm)",
                fontWeight: 950,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                color: "#C0392B",
                mb: 1,
              }}
            >
              {td("comparator.hotelLabel")}
            </Typography>
            <Typography
              sx={{
                ...RECAP_TYPO.comparatorAmount,
                color: "#922b21",
                mb: 1.25,
              }}
            >
              {formatEuro(hotelTotal)}
            </Typography>
            <Typography sx={{ ...RECAP_META.bodyMuted, color: "#c0392b" }}>
              {td("comparator.hotelDesc")}
            </Typography>
          </Box>
        </Box>

        <Box
          sx={{
            borderRadius: 4,
            p: 2.5,
            textAlign: "center",
            background: "#2E7D5A",
            color: "white",
            boxShadow: "0 10px 25px rgba(26, 83, 54, 0.15)",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <Box
            sx={{
              position: "absolute",
              right: -10,
              top: -10,
              opacity: 0.1,
              transform: "rotate(-15deg)",
            }}
          >
            <TrendingDownRoundedIcon sx={{ fontSize: 100 }} />
          </Box>
          <Typography
            sx={{
              fontSize: 28,
              fontWeight: 980,
              letterSpacing: "-0.03em",
              lineHeight: 1,
            }}
          >
            {td("comparator.savingsTitle").replace(
              "{{amount}}",
              formatEuro(eco),
            )}
          </Typography>
          {savingsPctShown != null && (
            <Typography
              sx={{
                ...RECAP_META.body,
                color: "rgba(255,255,255,0.92)",
                mt: 0.75,
              }}
            >
              {td("comparator.savingsSubtitle").replace(
                "{{pct}}",
                formatPercentInt(savingsPctShown),
              )}
            </Typography>
          )}
        </Box>
      </Box>
    </VtfGlassCard>
  );
}
