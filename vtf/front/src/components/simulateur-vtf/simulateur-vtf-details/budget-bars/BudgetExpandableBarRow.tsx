import * as React from "react";
import Collapse from "@mui/material/Collapse";
import KeyboardArrowDownRoundedIcon from "@mui/icons-material/KeyboardArrowDownRounded";
import { Box, Typography } from "../../../ui";
import { formatEuro } from "../_format";
import { RECAP_ICON, RECAP_META } from "../recapCard.ui";
import type { BudgetBarKey } from "./budgetBars.types";

export type BudgetExpandableBarRowProps = {
  barKey: BudgetBarKey;
  label: string;
  value: number;
  widthPct: number;
  color: string;
  icon: React.ReactNode;
  shareLabel: string;
  expanded: boolean;
  onToggle: () => void;
  expandId: string;
  children: React.ReactNode;
};

export function BudgetExpandableBarRow({
  barKey,
  label,
  value,
  widthPct,
  color,
  icon,
  shareLabel,
  expanded,
  onToggle,
  expandId,
  children,
}: BudgetExpandableBarRowProps) {
  const pctShown = Math.max(3, Math.min(100, widthPct || 0));

  return (
    <Box
      component="section"
      aria-labelledby={`${expandId}-label`}
      sx={{ mt: 1.75 }}
    >
      <Box
        component="button"
        type="button"
        id={expandId}
        aria-expanded={expanded}
        aria-controls={`${expandId}-panel`}
        onClick={onToggle}
        sx={{
          display: "block",
          width: "100%",
          p: 0,
          m: 0,
          border: "none",
          bgcolor: "transparent",
          cursor: "pointer",
          textAlign: "left",
          borderRadius: 2,
          transition: "background 0.15s ease",
          "&:hover": { bgcolor: "rgba(255,255,255,0.45)" },
          "&:focus-visible": {
            outline: "2px solid var(--vtf-teal)",
            outlineOffset: 2,
          },
        }}
      >
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 1.5,
            py: 0.35,
            px: 0.5,
          }}
        >
          <Box
            sx={{
              display: "flex",
              alignItems: "flex-start",
              gap: 1,
              minWidth: 0,
            }}
          >
            <Box
              sx={{
                color: expanded ? color : "rgba(0, 68, 90, 0.45)",
                display: "flex",
                flexShrink: 0,
                mt: 0.15,
                transition: "color 0.15s ease",
                "& svg": { fontSize: RECAP_ICON.row },
              }}
            >
              {icon}
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography
                id={`${expandId}-label`}
                sx={{
                  ...RECAP_META.bodyStrong,
                  color: expanded ? "var(--vtf-navy)" : undefined,
                }}
              >
                {label}
              </Typography>
              <Typography sx={{ ...RECAP_META.caption, mt: 0.2 }}>
                {shareLabel}
              </Typography>
            </Box>
          </Box>
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 0.5,
              flexShrink: 0,
              pt: 0.1,
            }}
          >
            <Typography sx={RECAP_META.rowValue}>
              {formatEuro(value)}
            </Typography>
            <KeyboardArrowDownRoundedIcon
              aria-hidden
              sx={{
                fontSize: 22,
                color: "rgba(0, 68, 90, 0.4)",
                transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
                transition: "transform 0.22s cubic-bezier(0.4, 0, 0.2, 1)",
              }}
            />
          </Box>
        </Box>
        <Box
          sx={{
            mt: 1,
            mx: 0.5,
            height: 12,
            borderRadius: 99,
            bgcolor: "rgba(15,23,42,0.06)",
            overflow: "hidden",
            border: "1px solid rgba(15,23,42,0.04)",
          }}
        >
          <Box
            sx={{
              width: `${pctShown}%`,
              height: "100%",
              bgcolor: color,
              borderRadius: 99,
              transition: "width 1s cubic-bezier(0.4, 0, 0.2, 1)",
              boxShadow: expanded
                ? `0 0 14px ${color}33`
                : `0 0 12px ${color}1a`,
              opacity: expanded ? 1 : 0.92,
            }}
          />
        </Box>
      </Box>

      <Collapse in={expanded} timeout={260} unmountOnExit>
        <Box
          id={`${expandId}-panel`}
          role="region"
          aria-labelledby={expandId}
          data-budget-bar={barKey}
        >
          {children}
        </Box>
      </Collapse>
    </Box>
  );
}
