import type { CSSProperties } from "react";
import type { SxProps, Theme } from "@mui/material/styles";

export const STAY_FORMULE_TILE_MIN_WIDTH_XS = 140;
export const STAY_SEASON_TILE_MIN_WIDTH_XS = 148;
export const STAY_ENV_TILE_MIN_WIDTH_XS = 220;

type ScrollGridFrom = "sm" | "md";

type StayTileGridTemplateColumns =
  | NonNullable<CSSProperties["gridTemplateColumns"]>
  | Partial<Record<"sm" | "md" | "xl", NonNullable<CSSProperties["gridTemplateColumns"]>>>;

/** Mobile-only scroll row; at `gridFrom` and above, no sx overrides (tailwind grid unchanged). */
export function stayTileScrollContainerSx(args: {
  gridFrom?: ScrollGridFrom;
  gridTemplateColumns: StayTileGridTemplateColumns;
}): SxProps<Theme> {
  const bp = args.gridFrom ?? "sm";
  return {
    display: { xs: "flex", [bp]: "grid" },
    gridTemplateColumns: args.gridTemplateColumns,
    gap: { xs: 1.5, [bp]: undefined },
    overflowX: { xs: "auto", [bp]: "visible" },
    pt: { xs: 1.5, [bp]: 0 },
    pb: { xs: 1.75, [bp]: 0 },
    mx: { xs: -0.25, [bp]: 0 },
    px: { xs: 0.25, [bp]: 0 },
    WebkitOverflowScrolling: "touch",
  };
}

export function stayTileScrollItemSx(
  minWidthXs: number,
  gridFrom: ScrollGridFrom = "sm",
): SxProps<Theme> {
  return {
    minWidth: { xs: minWidthXs, [gridFrom]: "auto" },
    width: { xs: minWidthXs, [gridFrom]: "auto" },
    flexShrink: { xs: 0, [gridFrom]: 1 },
  };
}
