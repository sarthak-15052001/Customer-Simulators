import * as React from "react";
import { Box, Typography } from "../../ui";
import {
  RECAP_ICON,
  RECAP_META,
  RECAP_SURFACE,
  recapMetricLabelSx,
  type RecapMetricVariant,
} from "./recapCard.ui";

type RecapMetricItem = {
  variant: RecapMetricVariant;
  label: string;
  value: React.ReactNode;
  sublabel?: string;
  icon: React.ReactNode;
};

function MetricTile({
  variant,
  label,
  value,
  sublabel,
  icon,
}: RecapMetricItem) {
  const theme = RECAP_SURFACE.metric[variant];

  return (
    <Box
      sx={{
        borderRadius: 2.5,
        p: 1.5,
        bgcolor: theme.bg,
        border: `1px solid ${theme.border}`,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
        <Box
          sx={{
            width: 32,
            height: 32,
            borderRadius: 2,
            bgcolor: theme.icon,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            color: "#fff",
            "& svg": { fontSize: RECAP_ICON.metric },
          }}
        >
          {icon}
        </Box>
        <Typography sx={recapMetricLabelSx(variant)}>{label}</Typography>
      </Box>

      <Typography sx={RECAP_META.metricLine}>{value}</Typography>
      {sublabel ? (
        <Typography sx={{ ...RECAP_META.bodyMuted, mt: 0.5 }}>
          {sublabel}
        </Typography>
      ) : null}
    </Box>
  );
}

export function RecapSummaryMetrics({ items }: { items: RecapMetricItem[] }) {
  return (
    <Box
      sx={{
        pb: { xs: 1.25, sm: 2 },
        display: "grid",
        gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
        gap: 1.25,
      }}
    >
      {items.map((item) => (
        <MetricTile key={item.variant} {...item} />
      ))}
    </Box>
  );
}
