import type { SimulateurStepKey } from "../components/simulateur-vtf/shared/SimulateurTabsList";
import { FAMILY_TAB_LIMITS } from "./familyTab";
import type { FamilyState } from "../types/familyTab";
import type { PlanningItem, SejourState } from "../types/stayTab";

function planningItemFingerprint(item: PlanningItem) {
  return {
    label: item.label,
    cat: item.cat,
    sourceId: item.sourceId,
    prix: item.prix,
  };
}

function planningStateFingerprint(
  planning: NonNullable<SejourState["planning"]>,
): string {
  const out: Record<
    string,
    {
      matin: ReturnType<typeof planningItemFingerprint>[];
      aprem: ReturnType<typeof planningItemFingerprint>[];
      soir: ReturnType<typeof planningItemFingerprint>[];
    }
  > = {};

  for (const [dayKey, slots] of Object.entries(planning)) {
    out[dayKey] = {
      matin: (slots.matin ?? []).map(planningItemFingerprint),
      aprem: (slots.aprem ?? []).map(planningItemFingerprint),
      soir: (slots.soir ?? []).map(planningItemFingerprint),
    };
  }

  return JSON.stringify(out);
}

export type StepValidationResult = {
  valid: boolean;
  messageKey: string;
};

const STEP_ORDER: SimulateurStepKey[] = [
  "famille",
  "sejour",
  "extras",
  "resto",
  "transport",
  "promos",
  "planning",
  "details",
];

function isSejourCoreValid(sejour: SejourState): StepValidationResult | null {
  if (!sejour.fSaison) {
    return { valid: false, messageKey: "simulateur.validation.sejourSeason" };
  }
  if (!sejour.fEnv) {
    return {
      valid: false,
      messageKey: "simulateur.validation.sejourEnvironment",
    };
  }
  if (sejour.mode === "village" && !sejour.villageId) {
    return { valid: false, messageKey: "simulateur.validation.sejourVillage" };
  }
  if (sejour.mode === "village" && sejour.villageId && !sejour.formule) {
    return { valid: false, messageKey: "simulateur.validation.sejourFormule" };
  }
  if (sejour.mode === "activite" && !sejour.attractionId) {
    return { valid: false, messageKey: "simulateur.validation.sejourVillage" };
  }
  if (!sejour.dateDebut || !sejour.dateFin) {
    return { valid: false, messageKey: "simulateur.validation.sejourDates" };
  }
  return null;
}

export function validateSimulatorStep(
  stepKey: SimulateurStepKey,
  family: FamilyState,
  sejour: SejourState,
): StepValidationResult {
  if (stepKey === "famille") {
    if (family.adultes < FAMILY_TAB_LIMITS.adultesMin) {
      return { valid: false, messageKey: "simulateur.validation.familyAdults" };
    }
    const invalidChild = family.enfants.some(
      (e) => e.age < 0 || e.age > FAMILY_TAB_LIMITS.ageEnfantMax,
    );
    if (invalidChild) {
      return {
        valid: false,
        messageKey: "simulateur.validation.familyChildAge",
      };
    }
    return { valid: true, messageKey: "" };
  }

  if (stepKey === "sejour") {
    const sejourError = isSejourCoreValid(sejour);
    return sejourError ?? { valid: true, messageKey: "" };
  }

  if (
    stepKey === "extras" ||
    stepKey === "resto" ||
    stepKey === "transport" ||
    stepKey === "promos"
  ) {
    const sejourError = isSejourCoreValid(sejour);
    return sejourError ?? { valid: true, messageKey: "" };
  }

  if (stepKey === "planning") {
    const sejourError = isSejourCoreValid(sejour);
    return sejourError ?? { valid: true, messageKey: "" };
  }

  return { valid: true, messageKey: "" };
}

/** Highest step index the user may open (0 = famille only until it is valid). */
export function computeFurthestUnlockedStep(
  family: FamilyState,
  sejour: SejourState,
): number {
  let unlocked = 0;
  for (let i = 0; i < STEP_ORDER.length; i++) {
    const result = validateSimulatorStep(STEP_ORDER[i], family, sejour);
    if (!result.valid) break;
    unlocked = Math.min(i + 1, STEP_ORDER.length - 1);
  }
  return unlocked;
}

export function stepStateFingerprint(
  stepKey: SimulateurStepKey,
  family: FamilyState,
  sejour: SejourState,
): string {
  switch (stepKey) {
    case "famille":
      return JSON.stringify(family);
    case "sejour":
      return JSON.stringify({
        fSaison: sejour.fSaison,
        fNuits: sejour.fNuits,
        dateDebut: sejour.dateDebut,
        dateFin: sejour.dateFin,
        fEnv: sejour.fEnv,
        regionFilter: sejour.regionFilter,
        filterModalActivityIds: sejour.filterModalActivityIds,
        formuleFilter: sejour.formuleFilter,
        mode: sejour.mode,
        attractionNom: sejour.attractionNom,
        attractionId: sejour.attractionId,
        villageId: sejour.villageId,
        formule: sejour.formule,
      });
    case "extras":
      return JSON.stringify(sejour.extraActivities ?? {});
    case "resto":
      return JSON.stringify(sejour.resto ?? {});
    case "transport":
      return JSON.stringify(sejour.transport ?? {});
    case "promos":
      return JSON.stringify({
        promos: sejour.promos,
        qfVal: family.qfVal,
        maxiFamily: family.maxiFamily,
      });
    case "planning":
      return sejour.planning ? planningStateFingerprint(sejour.planning) : "{}";
    case "details":
      return "";
    default:
      return "";
  }
}
