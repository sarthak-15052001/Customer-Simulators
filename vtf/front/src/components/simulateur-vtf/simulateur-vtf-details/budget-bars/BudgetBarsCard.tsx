import * as React from "react";
import { Box, Typography } from "../../../ui";
import { VtfGlassCard } from "../../../shared/VtfGlassCard";
import { VtfSectionHeading } from "../../../shared/VtfSectionHeading";
import PieChartRoundedIcon from "@mui/icons-material/PieChartRounded";
import { useSimulateurTabTranslation } from "../../../../hooks/useSimulateurTabTranslation";
import { RECAP_META } from "../recapCard.ui";
import type { BudgetBarKey, BudgetBarsCardProps } from "./budgetBars.types";
import { buildBudgetBarRows } from "./buildBudgetBarRows";
import { BudgetExpandableBarRow } from "./BudgetExpandableBarRow";
import { StayBudgetExpandPanel } from "./panels/StayBudgetExpandPanel";
import { ActivitiesBudgetExpandPanel } from "./panels/ActivitiesBudgetExpandPanel";
import { RestoBudgetExpandPanel } from "./panels/RestoBudgetExpandPanel";
import { TransportBudgetExpandPanel } from "./panels/TransportBudgetExpandPanel";

function BudgetBarExpandPanel({
  barKey,
  estimate,
  family,
  sejour,
  village,
}: {
  barKey: BudgetBarKey;
  estimate: NonNullable<BudgetBarsCardProps["estimate"]>;
  family: BudgetBarsCardProps["family"];
  sejour: BudgetBarsCardProps["sejour"];
  village: BudgetBarsCardProps["village"];
}) {
  switch (barKey) {
    case "stay":
      return <StayBudgetExpandPanel family={family} sejour={sejour} estimate={estimate} />;
    case "activities":
      return (
        <ActivitiesBudgetExpandPanel
          family={family}
          sejour={sejour}
          village={village}
          estimate={estimate}
        />
      );
    case "restoration":
      return (
        <RestoBudgetExpandPanel
          family={family}
          sejour={sejour}
          estimate={estimate}
        />
      );
    case "transport":
      return (
        <TransportBudgetExpandPanel
          family={family}
          sejour={sejour}
          estimate={estimate}
        />
      );
    default:
      return null;
  }
}

export function BudgetBarsCard({
  estimate,
  family,
  sejour,
  village,
}: BudgetBarsCardProps) {
  const td = useSimulateurTabTranslation("details");
  const [expandedKey, setExpandedKey] = React.useState<BudgetBarKey | null>(
    null,
  );

  const bd = estimate?.budgetBreakdown;
  const total = Math.max(0, estimate?.total ?? 0);

  const rows = React.useMemo(
    () => (bd ? buildBudgetBarRows(bd, td) : []),
    [bd, td],
  );

  const toggle = (key: BudgetBarKey) => {
    setExpandedKey((prev) => (prev === key ? null : key));
  };

  return (
    <VtfGlassCard glassSx={{ p: { xs: 2.5, sm: 3 } }}>
      <VtfSectionHeading
        title={td("bars.title")}
        icon={<PieChartRoundedIcon />}
        accent="orange"
      />
      {!estimate ? (
        <Typography sx={RECAP_META.bodyMuted}>{td("bars.empty")}</Typography>
      ) : !bd ? (
        <Typography sx={RECAP_META.bodyMuted}>
          {td("bars.noBreakdown")}
        </Typography>
      ) : rows.length === 0 ? (
        <Typography sx={RECAP_META.bodyMuted}>{td("bars.empty")}</Typography>
      ) : (
        <Box sx={{ mt: 0.25 }}>
          <Typography sx={{ ...RECAP_META.caption, mb: 0.5, px: 0.5 }}>
            {td("bars.expandHint")}
          </Typography>
          {rows.map((r) => {
            const pct = total > 0 ? Math.round((r.value / total) * 100) : 0;
            const shareLabel = td("bars.shareOfBudget").replace(
              "{{pct}}",
              String(pct),
            );
            const expandId = `budget-bar-${r.key}`;
            const isOpen = expandedKey === r.key;
            return (
              <BudgetExpandableBarRow
                key={r.key}
                barKey={r.key}
                label={r.label}
                value={r.value}
                widthPct={pct}
                color={r.color}
                icon={r.icon}
                shareLabel={shareLabel}
                expanded={isOpen}
                onToggle={() => toggle(r.key)}
                expandId={expandId}
              >
                <BudgetBarExpandPanel
                  barKey={r.key}
                  estimate={estimate}
                  family={family}
                  sejour={sejour}
                  village={village}
                />
              </BudgetExpandableBarRow>
            );
          })}
        </Box>
      )}
    </VtfGlassCard>
  );
}
