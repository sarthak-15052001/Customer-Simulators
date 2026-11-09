import CheckRoundedIcon from "@mui/icons-material/CheckRounded";
import type { SxProps, Theme } from "@mui/material/styles";

import { Box } from "./Box";
import { mergeSx } from "./_mergeSx";
import type { SelectableAccent } from "./selectableTilePresets";

function accentRgbVar(accent: SelectableAccent): string {
  if (accent === "teal") return "var(--vtf-teal-rgb)";
  if (accent === "orange") return "var(--vtf-orange-rgb)";
  if (accent === "green") return "46, 125, 90";
  return "var(--vtf-navy-rgb)";
}

function selectedBadgeSx({
  accent,
  size,
  offset,
}: {
  accent: SelectableAccent;
  size: number;
  offset: number;
}): SxProps<Theme> {
  const rgb = accentRgbVar(accent);
  return {
    position: "absolute",
    top: offset,
    right: offset,
    width: size,
    height: size,
    borderRadius: "999px",
    backgroundColor: `rgba(${rgb}, 0.95)`,
    color: "white",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow:
      accent === "teal"
        ? "0 10px 18px rgba(0,168,181,0.22)"
        : accent === "orange"
          ? "0 10px 18px rgba(242,166,128,0.28)"
          : accent === "green"
            ? "0 10px 18px rgba(46, 125, 90, 0.24)"
            : "0 10px 18px rgba(0, 68, 90, 0.22)",
    border: "2px solid rgba(255,255,255,0.9)",
  };
}

export type SelectedBadgeProps = {
  accent: SelectableAccent;
  label?: string;
  size?: number;
  offset?: number;
  sx?: SxProps<Theme>;
};

export function SelectedBadge({
  accent,
  label = "Selected",
  size = 22,
  offset = 10,
  sx,
}: SelectedBadgeProps) {
  return (
    <Box
      sx={mergeSx(selectedBadgeSx({ accent, size, offset }), sx)}
      aria-label={label}
    >
      <CheckRoundedIcon
        sx={{ fontSize: Math.max(12, Math.round(size * 0.73)) }}
      />
    </Box>
  );
}
