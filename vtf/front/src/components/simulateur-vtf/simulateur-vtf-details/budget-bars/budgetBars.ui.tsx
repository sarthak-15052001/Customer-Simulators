import * as React from "react";
import { Box, Typography } from "../../../ui";
import { RecapBreakdownDivider, RecapBreakdownRow } from "../recapBreakdown.ui";
import { RECAP_META, RECAP_SURFACE, type RecapSectionTheme } from "../recapCard.ui";

export function BudgetExpandPanelShell({
  theme,
  children,
}: {
  theme: RecapSectionTheme;
  children: React.ReactNode;
}) {
  const panel = RECAP_SURFACE.panel[theme];
  return (
    <Box
      sx={{
        mt: 1.25,
        p: { xs: 1.25, sm: 1.5 },
        borderRadius: 2.5,
        bgcolor: panel.bg,
        border: `1px solid ${panel.border}`,
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.65)",
      }}
    >
      {children}
    </Box>
  );
}

export function BudgetPanelHeading({ children }: { children: React.ReactNode }) {
  return (
    <Typography
      sx={{ ...RECAP_META.captionStrong, mb: 0.75, letterSpacing: 0.4 }}
    >
      {children}
    </Typography>
  );
}

export function BudgetPanelEmptyNote({ children }: { children: React.ReactNode }) {
  return (
    <Typography sx={{ ...RECAP_META.bodyMuted, py: 0.5, px: 0.25 }}>
      {children}
    </Typography>
  );
}

export function BudgetPanelSubtotal({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <>
      <RecapBreakdownDivider />
      <RecapBreakdownRow variant="subtotal" label={label} value={value} strong />
    </>
  );
}
