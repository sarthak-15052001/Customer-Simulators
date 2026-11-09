import * as React from "react";
import MuiChip from "@mui/material/Chip";
import type { ChipProps } from "@mui/material/Chip";

export type VtfPillTone = "softOrange" | "softTeal" | "softGreen" | "softNavy";

function toneToSx(tone: VtfPillTone): ChipProps["sx"] {
  if (tone === "softOrange") {
    return {
      backgroundColor: "var(--vtf-soft-orange)",
      color: "var(--vtf-orange)",
    };
  }
  if (tone === "softTeal") {
    return {
      backgroundColor: "var(--vtf-soft-teal)",
      color: "var(--vtf-teal)",
    };
  }
  if (tone === "softGreen") {
    return {
      backgroundColor: "var(--vtf-soft-green)",
      color: "var(--vtf-green)",
    };
  }
  if (tone === "softNavy") {
    return {
      backgroundColor: "var(--vtf-soft-navy)",
      color: "var(--vtf-navy)",
    };
  }
}

const baseSx: ChipProps["sx"] = {
  borderRadius: "9999px",
  fontWeight: 800,
  fontSize: "var(--vtf-font-sm)",
  px: 1,
  height: 28,
  fontFamily: "var(--sans)",
};

export type PillProps = Omit<ChipProps, "color" | "variant"> & {
  vtfTone?: VtfPillTone;
};

export const Pill = React.forwardRef<HTMLDivElement, PillProps>(function Pill(
  { vtfTone = "softNavy", className, sx, ...props },
  ref,
) {
  const toneSx = toneToSx(vtfTone);
  return (
    <MuiChip
      ref={ref}
      {...props}
      className={["vtf-pill", className].filter(Boolean).join(" ")}
      variant="filled"
      sx={[baseSx, toneSx, ...(Array.isArray(sx) ? sx : [sx])]}
    />
  );
});
