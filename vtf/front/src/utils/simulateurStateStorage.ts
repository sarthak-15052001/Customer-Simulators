import * as React from "react";
import BeachAccessRoundedIcon from "@mui/icons-material/BeachAccessRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import ExploreRoundedIcon from "@mui/icons-material/ExploreRounded";
import LocalActivityRoundedIcon from "@mui/icons-material/LocalActivityRounded";
import RestaurantRoundedIcon from "@mui/icons-material/RestaurantRounded";
import type { FamilyState } from "../types/familyTab";
import type {
  PlanningItem,
  PlanningSlotKey,
  SejourState,
} from "../types/stayTab";

const STORAGE_KEY = "vtf-simulateur-draft";
const PLANNING_SLOTS: PlanningSlotKey[] = ["matin", "aprem", "soir"];

export const DEFAULT_FAMILY: FamilyState = {
  adultes: 2,
  enfants: [{ age: 8 }, { age: 5 }],
  qfVal: null,
  maxiFamily: false,
};

export const DEFAULT_SEJOUR: SejourState = {
  fSaison: null,
  fNuits: 7,
  dateDebut: null,
  dateFin: null,
  fEnv: null,
  regionFilter: "",
  filterModalActivityIds: [],
  mode: "village",
  attractionNom: null,
  attractionId: null,
  villageId: null,
  formuleFilter: "DP",
  formule: null,
  extraActivities: {
    freeQtyById: {},
    paidQtyById: {},
  },
  resto: {
    qtyByMealId: {},
  },
  transport: {
    // Stay step must not include transport until user chooses on Transport tab.
    // Backend prices only `car` / `train`; `onSite` → transportTotal = 0.
    mode: "onSite",
    distanceOneWayKm: 400,
    fuel: "essence",
  },
  promos: {
    promoSejourRate: 0,
    quinzaineFutee: false,
    soloSupplementMode: "default",
  },
};

export type SimulateurDraft = {
  family: FamilyState;
  sejour: SejourState;
};

type StoredPlanningItem = Omit<PlanningItem, "icon">;

function planningIcon(cat: PlanningItem["cat"]): React.ReactNode {
  const sx = { fontSize: "var(--vtf-font-md)" };
  if (cat === "libre") {
    return React.createElement(BeachAccessRoundedIcon, {
      sx: { ...sx, color: "#0ea5e9" },
    });
  }
  if (cat === "repas") {
    return React.createElement(RestaurantRoundedIcon, {
      sx: { ...sx, color: "var(--vtf-navy)" },
    });
  }
  if (cat === "free") {
    return React.createElement(ExploreRoundedIcon, {
      sx: { ...sx, color: "var(--vtf-teal)" },
    });
  }
  if (cat === "paid") {
    return React.createElement(LocalActivityRoundedIcon, {
      sx: { ...sx, color: "var(--vtf-orange)" },
    });
  }
  return React.createElement(CheckCircleRoundedIcon, {
    sx: { ...sx, color: "var(--vtf-teal)" },
  });
}

function stripPlanningIcons(
  planning: SejourState["planning"],
): Record<string, Record<PlanningSlotKey, StoredPlanningItem[]>> | undefined {
  if (!planning) return undefined;

  const out: Record<string, Record<PlanningSlotKey, StoredPlanningItem[]>> = {};
  for (const [dayKey, slots] of Object.entries(planning)) {
    const day: Record<PlanningSlotKey, StoredPlanningItem[]> = {
      matin: [],
      aprem: [],
      soir: [],
    };
    for (const slot of PLANNING_SLOTS) {
      day[slot] = (slots[slot] ?? []).map(({ icon: _icon, ...item }) => item);
    }
    out[dayKey] = day;
  }
  return out;
}

function restorePlanning(
  planning: Record<string, Record<PlanningSlotKey, StoredPlanningItem[]>>,
): SejourState["planning"] {
  const out: NonNullable<SejourState["planning"]> = {};
  for (const [dayKey, slots] of Object.entries(planning)) {
    const day: Record<PlanningSlotKey, PlanningItem[]> = {
      matin: [],
      aprem: [],
      soir: [],
    };
    for (const slot of PLANNING_SLOTS) {
      day[slot] = (slots[slot] ?? []).map((item) => ({
        ...item,
        icon: planningIcon(item.cat),
      }));
    }
    out[dayKey] = day;
  }
  return out;
}

function mergeSejour(partial: Partial<SejourState>): SejourState {
  const { planning: storedPlanning, ...rest } = partial;

  return {
    ...DEFAULT_SEJOUR,
    ...rest,
    ...(storedPlanning && typeof storedPlanning === "object"
      ? {
          planning: restorePlanning(
            storedPlanning as Record<
              string,
              Record<PlanningSlotKey, StoredPlanningItem[]>
            >,
          ),
        }
      : {}),
    extraActivities: {
      ...DEFAULT_SEJOUR.extraActivities,
      ...rest.extraActivities,
      freeQtyById: {
        ...DEFAULT_SEJOUR.extraActivities?.freeQtyById,
        ...rest.extraActivities?.freeQtyById,
      },
      paidQtyById: {
        ...DEFAULT_SEJOUR.extraActivities?.paidQtyById,
        ...rest.extraActivities?.paidQtyById,
      },
    },
    resto: {
      ...DEFAULT_SEJOUR.resto,
      ...rest.resto,
      qtyByMealId: {
        ...DEFAULT_SEJOUR.resto.qtyByMealId,
        ...rest.resto?.qtyByMealId,
      },
    },
    transport: {
      ...DEFAULT_SEJOUR.transport,
      ...rest.transport,
    },
    promos: {
      ...DEFAULT_SEJOUR.promos,
      ...rest.promos,
    },
  };
}

let cachedDraft: SimulateurDraft | null | undefined;

export function hasSimulateurDraftInStorage(): boolean {
  if (typeof sessionStorage === "undefined") return false;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const parsed = JSON.parse(raw) as Partial<SimulateurDraft>;
    return Boolean(parsed.family && parsed.sejour);
  } catch {
    return false;
  }
}

/** Initial state for the simulator page (reads sessionStorage once per page load). */
export function getInitialSimulatorState(): SimulateurDraft {
  if (cachedDraft === undefined) {
    cachedDraft = loadSimulateurDraft();
  }
  return cachedDraft ?? { family: DEFAULT_FAMILY, sejour: DEFAULT_SEJOUR };
}

/** Restore draft from sessionStorage (survives refresh / address-bar navigation). */
export function loadSimulateurDraft(): SimulateurDraft | null {
  if (typeof sessionStorage === "undefined") return null;

  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as Partial<SimulateurDraft>;
    if (!parsed.family || !parsed.sejour) return null;

    return {
      family: { ...DEFAULT_FAMILY, ...parsed.family },
      sejour: mergeSejour(parsed.sejour),
    };
  } catch {
    return null;
  }
}

/** Persist draft (family, sejour, and planning). */
export function saveSimulateurDraft(
  family: FamilyState,
  sejour: SejourState,
): void {
  if (typeof sessionStorage === "undefined") return;

  try {
    const { planning, ...sejourRest } = sejour;
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        family,
        sejour: {
          ...sejourRest,
          planning: stripPlanningIcons(planning),
        },
      }),
    );
  } catch {
    // Private mode / quota — ignore.
  }
}

export function clearSimulateurDraft(): void {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.removeItem(STORAGE_KEY);
  cachedDraft = null;
}

/** Clears session storage and returns default family / séjour state. */
export function resetSimulateurDraft(): SimulateurDraft {
  clearSimulateurDraft();
  const fresh = { family: DEFAULT_FAMILY, sejour: DEFAULT_SEJOUR };
  cachedDraft = fresh;
  return fresh;
}
