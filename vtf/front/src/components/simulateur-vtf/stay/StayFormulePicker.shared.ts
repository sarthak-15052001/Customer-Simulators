import type { SxProps, Theme } from "@mui/material/styles";

import type { ApiFormule } from "../../../api/formules.api";
import type { VtfFormule } from "../../../data/vtfStay";

const VTF_FORMULE_CODES = new Set<VtfFormule>(["PC", "DP", "LOC"]);

/** Clés d'icônes de tuiles — rendues comme icônes MUI avec une teinte marine cohérente (voir l'interface utilisateur du sélecteur). */
export type StayFormulePickerIcon = "pc" | "dp" | "loc";

export type StayFormulePickerOption = {
  k: VtfFormule;
  icon: StayFormulePickerIcon;
  label: string;
  sub: string;
};

function isVtfFormule(code: string): code is VtfFormule {
  return VTF_FORMULE_CODES.has(code as VtfFormule);
}

function toPickerIcon(iconKey: string): StayFormulePickerIcon {
  if (iconKey === "pc" || iconKey === "dp" || iconKey === "loc") return iconKey;
  return "pc";
}

/** Catalogue API → tuiles du sélecteur (tri `sortOrder`). */
export function mapApiFormulesToPickerOptions(
  apiFormules: ApiFormule[],
): StayFormulePickerOption[] {
  return [...apiFormules]
    .sort((a, b) => a.sortOrder - b.sortOrder)
    .flatMap((f) => {
      if (!isVtfFormule(f.code)) return [];
      return [
        {
          k: f.code,
          icon: toPickerIcon(f.iconKey),
          label: f.label,
          sub: f.shortDescription,
        },
      ];
    });
}

export function filterStayFormuleOptionsForVillage(
  options: StayFormulePickerOption[],
  villageFormules: VtfFormule[],
): StayFormulePickerOption[] {
  return options.filter((o) => villageFormules.includes(o.k));
}

/** Catalogue API → tuiles ; filtre optionnel par `village.formules`. */
export function resolveStayFormulePickerOptions(args: {
  apiFormules?: ApiFormule[];
  villageFormules?: VtfFormule[];
}): StayFormulePickerOption[] {
  const base = args.apiFormules?.length
    ? mapApiFormulesToPickerOptions(args.apiFormules)
    : [];

  return args.villageFormules
    ? filterStayFormuleOptionsForVillage(base, args.villageFormules)
    : base;
}

export function getFormuleLabelFromCatalog(
  code: VtfFormule | null,
  apiFormules?: ApiFormule[],
): string {
  if (!code) return "";
  return apiFormules?.find((f) => f.code === code)?.label ?? code;
}

/** Panneau encadré (sections du modal de filtres, bloc de formule). */
export const STAY_FORMULE_SECTION_SURFACE_SX: SxProps<Theme> = {
  p: 1.75,
  borderRadius: "16px",
  bgcolor: "rgba(15, 23, 42, 0.022)",
  border: "1px solid rgba(15, 23, 42, 0.065)",
  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.75)",
};

export const STAY_FORMULE_SECTION_LABEL_SX: SxProps<Theme> = {
  fontSize: "var(--vtf-font-xs)",
  fontWeight: 850,
  color: "var(--vtf-navy)",
  opacity: 0.55,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  mb: 1.1,
};

/** Filter modal — Formule / Région section labels: 14px */
export const STAY_FILTER_MODAL_SECTION_LABEL_SX: SxProps<Theme> = {
  ...STAY_FORMULE_SECTION_LABEL_SX,
  fontSize: "var(--vtf-font-sm)",
};

export type StayFormulePickerGridLayout = "auto" | "three";
