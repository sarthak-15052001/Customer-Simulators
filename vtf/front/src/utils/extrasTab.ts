import type { SejourState } from "../types/stayTab";
import { dateToSaisonIdx } from "./stayTab";
import type { VtfSeasonKey } from "../data/vtfExtras";

const FUNNEL_TO_API_SEASON: Record<string, VtfSeasonKey> = {
  printemps: "vs",
  ete: "ete",
  automne: "hs",
  hiver: "fetes",
};

const API_TO_FUNNEL_SAISON: Record<VtfSeasonKey, string> = {
  vs: "printemps",
  ete: "ete",
  hs: "automne",
  fetes: "hiver",
};

const FUNNEL_SAISON_KEYS = new Set(Object.keys(FUNNEL_TO_API_SEASON));

/** Recap pill i18n key for a pricing/API season code (`hs`, `vs`, `ete`, `fetes`). */
export function pricingSeasonRecapPillKey(
  apiSaisonKey: string | null | undefined,
): string {
  if (apiSaisonKey && apiSaisonKey in API_TO_FUNNEL_SAISON) {
    return API_TO_FUNNEL_SAISON[apiSaisonKey as VtfSeasonKey];
  }
  if (apiSaisonKey && FUNNEL_SAISON_KEYS.has(apiSaisonKey)) {
    return apiSaisonKey;
  }
  return "ete";
}

/** `simulateur.recap.pillSeason.*` uses funnel keys (printemps…), not API keys (vs…). */
export function funnelSaisonKeyForRecap(
  sejour: SejourState,
  apiSaisonKey?: string | null,
): string {
  if (apiSaisonKey && apiSaisonKey in API_TO_FUNNEL_SAISON) {
    return API_TO_FUNNEL_SAISON[apiSaisonKey as VtfSeasonKey];
  }
  if (apiSaisonKey && FUNNEL_SAISON_KEYS.has(apiSaisonKey)) {
    return apiSaisonKey;
  }
  if (sejour.fSaison && FUNNEL_SAISON_KEYS.has(sejour.fSaison)) {
    return sejour.fSaison;
  }
  return "ete";
}

/** Pill i18n key for recap UI — prefers pricing season from API when known. */
export function recapSeasonPillKey(sejour: SejourState): string {
  return funnelSaisonKeyForRecap(sejour, sejour.serverSeasonKey);
}

export function saisonKeyFromSejour(sejour: SejourState): VtfSeasonKey {
  if (sejour.fSaison && FUNNEL_TO_API_SEASON[sejour.fSaison]) {
    return FUNNEL_TO_API_SEASON[sejour.fSaison];
  }
  const idx = dateToSaisonIdx(sejour.dateDebut);
  return idx === 0 ? "hs" : idx === 1 ? "vs" : idx === 2 ? "ete" : "fetes";
}

export function clampInt(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, Math.trunc(Number.isFinite(n) ? n : 0)));
}

export function qtyFromMap(
  map: Record<string, number> | undefined,
  id: string,
): number {
  const v = map?.[id];
  return typeof v === "number" && v > 0 ? v : 0;
}

export { formatEuro as euro } from "./currency";
