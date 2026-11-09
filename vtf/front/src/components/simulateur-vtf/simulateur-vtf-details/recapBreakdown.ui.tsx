import * as React from "react";
import { Box, Typography } from "../../ui";
import { VtfSectionHeading } from "../../shared/VtfSectionHeading";
import {
  RECAP_ICON,
  RECAP_META,
  RECAP_SURFACE,
  type RecapSectionTheme,
} from "./recapCard.ui";

export type RecapBreakdownRowVariant =
  | "default"
  | "child"
  | "discount"
  | "subtotal";

export function RecapBreakdownDivider() {
  return (
    <Box
      role="separator"
      sx={{
        my: 0.75,
        mx: 0.25,
        height: "1px",
        bgcolor: "rgba(0, 68, 90, 0.08)",
      }}
    />
  );
}

export function RecapBreakdownSection({
  theme,
  title,
  icon,
  children,
  hideHeading,
}: {
  theme: RecapSectionTheme;
  title?: string;
  icon?: React.ReactElement<{ sx?: object }>;
  children: React.ReactNode;
  hideHeading?: boolean;
}) {
  const panel = RECAP_SURFACE.panel[theme];

  return (
    <Box
      sx={{
        mt: hideHeading ? 0 : 1,
        p: 0,
        bgcolor: "transparent",
        border: "none",
        borderRadius: 0,
      }}
    >
      {!hideHeading && title && icon && (
        <VtfSectionHeading
          title={title}
          icon={icon}
          accent={panel.accent}
          mb={1}
        />
      )}
      <Box sx={{ display: "flex", flexDirection: "column", gap: 0.25 }}>
        {children}
      </Box>
    </Box>
  );
}

/** Layout-only variants — amount typography stays on `strong` (original behaviour). */
const ROW_VARIANT_SX: Record<
  RecapBreakdownRowVariant,
  {
    py: number;
    px: number;
    bgcolor?: string;
    border?: string;
    borderRadius?: number;
    mb?: number;
    mt?: number;
  }
> = {
  default: { py: 0.65, px: 0.75 },
  child: {
    py: 0.75,
    px: 1,
    bgcolor: "rgba(255, 255, 255, 0.72)",
    border: "1px solid rgba(0, 68, 90, 0.06)",
    borderRadius: 2,
    mb: 0.25,
  },
  discount: {
    py: 0.65,
    px: 0.75,
    bgcolor: "rgba(46, 125, 90, 0.06)",
    border: "1px solid rgba(46, 125, 90, 0.12)",
    borderRadius: 2,
    mb: 0.25,
  },
  subtotal: {
    py: 1,
    px: 1.25,
    bgcolor: RECAP_SURFACE.total.bg,
    border: `1px solid ${RECAP_SURFACE.total.border}`,
    borderRadius: 2,
    mt: 0.5,
  },
};

export function RecapBreakdownRow({
  label,
  value,
  strong,
  leadingIcon,
  note,
  variant = "default",
  indent,
}: {
  label: string;
  value: string;
  strong?: boolean;
  leadingIcon?: React.ReactNode;
  note?: string;
  variant?: RecapBreakdownRowVariant;
  indent?: boolean;
}) {
  const isChild = variant === "child";
  const shell = ROW_VARIANT_SX[variant];

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: isChild || note ? "flex-start" : "center",
        gap: 1.5,
        transition: "background 0.12s ease",
        ...shell,
        ...(indent && variant === "default"
          ? { pl: 2.75, borderLeft: "2px solid rgba(0, 68, 90, 0.1)" }
          : {}),
        "&:hover":
          variant === "default"
            ? { bgcolor: "rgba(255, 255, 255, 0.55)" }
            : undefined,
        "&:not(:last-child)":
          variant === "default"
            ? { borderBottom: "1px dashed rgba(0, 68, 90, 0.06)" }
            : undefined,
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: isChild || note ? "flex-start" : "center",
          gap: 1,
          minWidth: 0,
          pt: isChild || note ? 0.1 : 0,
        }}
      >
        {leadingIcon && (
          <Box
            sx={{
              color:
                variant === "discount"
                  ? "var(--vtf-green)"
                  : "rgba(0, 68, 90, 0.4)",
              display: "flex",
              flexShrink: 0,
              mt: isChild || note ? 0.15 : 0,
              "& svg": {
                fontSize: isChild ? RECAP_ICON.rowChild : RECAP_ICON.row,
              },
            }}
          >
            {leadingIcon}
          </Box>
        )}
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={strong ? RECAP_META.bodyStrong : RECAP_META.body}>
            {label}
          </Typography>
          {note ? (
            <Typography sx={{ ...RECAP_META.note, mt: 0.25 }}>
              {note}
            </Typography>
          ) : null}
        </Box>
      </Box>
      <Typography
        sx={{
          ...(strong ? RECAP_META.rowValueAccent : RECAP_META.rowValue),
          flexShrink: 0,
          pt: isChild || note ? 0.1 : 0,
        }}
      >
        {value}
      </Typography>
    </Box>
  );
}
