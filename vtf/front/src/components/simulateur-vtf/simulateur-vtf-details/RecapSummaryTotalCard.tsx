import { Box, Typography } from "../../ui";
import PaymentsRoundedIcon from "@mui/icons-material/PaymentsRounded";
import { VtfSectionIcon } from "../../shared/VtfSectionHeading";
import { formatEuro } from "./_format";
import { RECAP_SURFACE, RECAP_TYPO } from "./recapCard.ui";

import type { SejourEstimate } from "../../../utils/stayEstimate";
import { useSimulateurTabTranslation } from "../../../hooks/useSimulateurTabTranslation";

/** Full-width total strip — third row below the 2×2 metric grid. */
export function RecapSummaryTotalCard({
  estimate,
}: {
  estimate: SejourEstimate;
}) {
  const td = useSimulateurTabTranslation("details");

  return (
    <Box
      sx={{
        width: "100%",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 2,
        p: { xs: 1.25, sm: 1.5 },
        borderRadius: 2,
        bgcolor: RECAP_SURFACE.total.bg,
        border: `1px solid ${RECAP_SURFACE.total.border}`,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0 }}>
        <VtfSectionIcon icon={<PaymentsRoundedIcon />} accent="navy" />
        <Typography sx={RECAP_TYPO.totalLabel}>
          {td("recapCard.details.estimatedTotal")}
        </Typography>
      </Box>
      <Typography sx={{ ...RECAP_TYPO.totalAmount, flexShrink: 0 }}>
        {formatEuro(estimate.total)}
      </Typography>
    </Box>
  );
}
