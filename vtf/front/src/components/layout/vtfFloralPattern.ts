import type { SxProps, Theme } from "@mui/material/styles";

/** Floral dot motif (7 circles) — shared by footer, top bar, and landing map. */
export const VTF_FLORAL_PATTERN = `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23ffffff' fill-rule='evenodd'%3E%3Ccircle cx='30' cy='30' r='2.4'/%3E%3Ccircle cx='30' cy='22' r='1.9'/%3E%3Ccircle cx='30' cy='38' r='1.9'/%3E%3Ccircle cx='23.1' cy='26' r='1.9'/%3E%3Ccircle cx='36.9' cy='26' r='1.9'/%3E%3Ccircle cx='23.1' cy='34' r='1.9'/%3E%3Ccircle cx='36.9' cy='34' r='1.9'/%3E%3C/g%3E%3C/svg%3E")`;

export type VtfFloralPatternOptions = {
  opacity?: number;
  tileSize?: number;
  backgroundPosition?: string;
  backgroundRepeat?: string;
  /** Soft fade so the motif stays visible at top/center, not along the bottom edge. */
  fadeBottom?: boolean;
};

const floralFadeBottomMask = {
  maskImage:
    "linear-gradient(to bottom, #000 0%, #000 42%, rgba(0,0,0,0.35) 72%, transparent 100%)",
  WebkitMaskImage:
    "linear-gradient(to bottom, #000 0%, #000 42%, rgba(0,0,0,0.35) 72%, transparent 100%)",
};

/** Repeating floral overlay (absolute, non-interactive). */
export function vtfFloralPatternOverlaySx(
  options: VtfFloralPatternOptions = {},
): SxProps<Theme> {
  const {
    opacity = 0.12,
    tileSize = 96,
    backgroundPosition = "center",
    backgroundRepeat = "repeat",
    fadeBottom = false,
  } = options;
  return {
    position: "absolute",
    inset: 0,
    zIndex: 0,
    opacity,
    backgroundImage: VTF_FLORAL_PATTERN,
    backgroundRepeat,
    backgroundPosition,
    backgroundSize: `${tileSize}px ${tileSize}px`,
    pointerEvents: "none",
    ...(fadeBottom ? floralFadeBottomMask : {}),
  };
}

/**
 * Top bar — short strip: use tiles smaller than bar height and center them so
 * the flower cluster sits mid-bar (not the bottom petals at `top` + 96px tile).
 */
export function vtfTopbarFloralPatternOverlaySx(
  options: Pick<VtfFloralPatternOptions, "opacity" | "tileSize"> = {},
): SxProps<Theme> {
  const tile = options.tileSize ?? 64;
  return {
    position: "absolute",
    inset: 0,
    zIndex: 0,
    opacity: options.opacity ?? 0.1,
    backgroundImage: VTF_FLORAL_PATTERN,
    backgroundRepeat: "repeat",
    backgroundPosition: "center center",
    backgroundSize: `${tile}px ${tile}px`,
    pointerEvents: "none",
  };
}
