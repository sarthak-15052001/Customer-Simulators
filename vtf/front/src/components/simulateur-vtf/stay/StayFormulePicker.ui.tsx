import type { SxProps, Theme } from "@mui/material/styles";
import HolidayVillageOutlinedIcon from "@mui/icons-material/HolidayVillageOutlined";
import RestaurantMenuRoundedIcon from "@mui/icons-material/RestaurantMenuRounded";
import WbTwilightRoundedIcon from "@mui/icons-material/WbTwilightRounded";

import type { VtfFormule } from "../../../data/vtfStay";
import { Box, Button, SelectedBadge, Typography } from "../../ui";
import { mergeSx } from "../../ui/_mergeSx";
import {
  STAY_FORMULE_SECTION_LABEL_SX,
  STAY_FORMULE_SECTION_SURFACE_SX,
  type StayFormulePickerGridLayout,
  type StayFormulePickerIcon,
  type StayFormulePickerOption,
} from "./StayFormulePicker.shared";

const FORMULE_TILE_ICONS = {
  pc: RestaurantMenuRoundedIcon,
  dp: WbTwilightRoundedIcon,
  loc: HolidayVillageOutlinedIcon,
} as const satisfies Record<
  StayFormulePickerIcon,
  typeof RestaurantMenuRoundedIcon
>;

function FormuleTileIcon({
  icon,
  selected,
}: {
  icon: StayFormulePickerIcon;
  selected: boolean;
}) {
  const Icon = FORMULE_TILE_ICONS[icon];
  return (
    <Icon
      sx={{
        fontSize: 22,
        color: selected ? "var(--vtf-navy)" : "rgba(0, 68, 90, 0.58)",
      }}
    />
  );
}

type GridDensity = "default" | "compact";

const gridClassName = (layout: StayFormulePickerGridLayout, count: number) => {
  if (layout === "three") return "grid grid-cols-3 gap-3";
  return `grid gap-3 ${count <= 2 ? "grid-cols-2" : "grid-cols-3"}`;
};

type StayFormulePickerGridProps = {
  options: StayFormulePickerOption[];
  selectedFormule: VtfFormule | null;
  onSelect: (f: VtfFormule) => void;
  layout?: StayFormulePickerGridLayout;
  /** Les tuiles du modal sont légèrement plus serrées ; la carte utilise les valeurs par défaut. */
  density?: GridDensity;
};

/**
 * Tuiles partagées PC / DP / LOC — mêmes visuels dans `StayFormuleCard` et le modal de filtres.
 */
export function StayFormulePickerGrid({
  options,
  selectedFormule,
  onSelect,
  layout = "auto",
  density = "default",
}: StayFormulePickerGridProps) {
  const iconBoxMb = density === "compact" ? 1 : 1.25;
  const titleFont = "var(--vtf-font-sm)";
  const subFont = "var(--vtf-font-xs)";
  const subMt = density === "compact" ? 0.55 : 0.75;

  if (options.length === 0) return null;

  return (
    <Box className={gridClassName(layout, options.length)}>
      {options.map((o) => {
        const sel = selectedFormule === o.k;
        return (
          <Button
            key={o.k}
            vtfVariant="selectableTileNavy"
            tileSelected={sel}
            onClick={() => onSelect(o.k)}
          >
            {sel && <SelectedBadge accent="navy" />}

            <Box
              sx={{
                width: "100%",
                textAlign: "center",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
              }}
            >
              <Box
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: "16px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  mb: iconBoxMb,
                  bgcolor: sel
                    ? "rgba(var(--vtf-navy-rgb), 0.10)"
                    : "rgba(255,255,255,0.55)",
                  border: "1px solid rgba(148, 163, 184, 0.30)",
                  boxShadow: sel
                    ? "0 14px 28px rgba(0, 68, 90, 0.14)"
                    : "0 10px 20px rgba(2,8,23,0.05)",
                }}
              >
                <FormuleTileIcon icon={o.icon} selected={sel} />
              </Box>

              <Typography
                sx={{
                  fontSize: titleFont,
                  fontWeight: 950,
                  color: sel ? "var(--vtf-navy)" : "rgba(0, 68, 90, 0.88)",
                  textAlign: "center",
                  lineHeight: 1.1,
                }}
              >
                {o.label}
              </Typography>
              <Typography
                sx={{
                  fontSize: subFont,
                  fontWeight: 750,
                  color: "var(--vtf-navy)",
                  opacity: 0.55,
                  lineHeight: 1.25,
                  textAlign: "center",
                  mt: subMt,
                }}
              >
                {o.sub}
              </Typography>
            </Box>
          </Button>
        );
      })}
    </Box>
  );
}

type StayFormulePickerSectionProps = {
  title: string;
  options: StayFormulePickerOption[];
  selectedFormule: VtfFormule | null;
  onSelect: (f: VtfFormule) => void;
  layout?: StayFormulePickerGridLayout;
  density?: GridDensity;
  mobileScroll?: boolean;
  scrollGridFrom?: string;
  labelSx?: SxProps<Theme>;
  sx?: SxProps<Theme>;
};

/** Section encadrée + libellé en majuscules + grille (modal de filtres). */
export function StayFormulePickerSection({
  title,
  options,
  selectedFormule,
  onSelect,
  layout = "three",
  density = "compact",
  labelSx,
  sx,
}: StayFormulePickerSectionProps) {
  return (
    <Box
      sx={mergeSx(STAY_FORMULE_SECTION_SURFACE_SX, mergeSx({ mb: 1.75 }, sx))}
    >
      <Typography sx={labelSx ?? STAY_FORMULE_SECTION_LABEL_SX}>
        {title}
      </Typography>
      <StayFormulePickerGrid
        options={options}
        selectedFormule={selectedFormule}
        onSelect={onSelect}
        layout={layout}
        density={density}
      />
    </Box>
  );
}
