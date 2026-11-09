import type { QfBadgeKind } from '../types/familyTab'
import { EURO_MARK, formatEuro } from './currency'
import { dateToSaisonIdx } from './stayTab'

export const CAF_ATTESTATION_URL = 'https://www.caf.fr'

export const QF_SEUIL_BAS = 880
export const QF_SEUIL_HAUT = 1350

export const FAMILY_TAB_LIMITS = {
  adultesMin: 1,
  adultesMax: 6,
  enfantsMax: 8,
  ageEnfantMax: 17,
  qfMin: 0,
  qfMax: 5000,
} as const

export const DEFAULT_NEW_CHILD_AGE = 6

/** Bracket table from `GET /api/v1/pricing-rules` → `payload.childDiscounts`. */
export type ChildDiscountsRow = {
  lt1: number;
  "1to2_withBebeClub": number;
  "1to2_withoutBebeClub": number;
  "3to5": number;
  "6to10": number;
  "11to15": number;
  ge16: number;
};

/**
 * Child tariff discount fraction (0–1) from active pricing rules.
 * Mirrors backend `stay_estimate._child_discount_with_bebe_club`.
 *
 * @param bebeClub — Villages with bébé club use the lower 1–2y bracket; on the family
 * step (no village yet) pass `false` so labels match the conservative estimate.
 */
export function discountFractionForChildAge(
  age: number,
  childDiscounts: ChildDiscountsRow,
  bebeClub: boolean,
): number {
  if (age < 1) return childDiscounts.lt1;
  if (age < 3) {
    return bebeClub
      ? childDiscounts["1to2_withBebeClub"]
      : childDiscounts["1to2_withoutBebeClub"];
  }
  if (age < 6) return childDiscounts["3to5"];
  if (age < 11) return childDiscounts["6to10"];
  if (age < 16) return childDiscounts["11to15"];
  return childDiscounts.ge16;
}

export const FAMILY_AGE_OPTIONS = Array.from(
  { length: FAMILY_TAB_LIMITS.ageEnfantMax + 1 },
  (_, age) => age,
)

export function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n))
}

/** Replace `{{low}}`, `{{high}}`, `{{euro}}`, `{{amount}}` in QF copy (thresholds from `QF_SEUIL_*`). */
export function fillQfTemplate(
  template: string,
  values?: { amount?: number },
): string {
  let out = template
    .replace(/\{\{low\}\}/g, formatEuro(QF_SEUIL_BAS, { compact: true }))
    .replace(/\{\{high\}\}/g, formatEuro(QF_SEUIL_HAUT, { compact: true }))
    .replace(/\{\{euro\}\}/g, EURO_MARK);
  if (values?.amount != null && Number.isFinite(values.amount)) {
    const formatted = formatEuro(values.amount);
    out = out
      .replace(/\{\{amount\}\}/g, formatted)
      .replace(/\{\{qf\}\}/g, formatted);
  }
  return out;
}

export function getQfBadgeKind(qfVal: number | null): QfBadgeKind {
  if (qfVal == null) return 'empty'
  if (qfVal < QF_SEUIL_BAS) return 'r1'
  if (qfVal < QF_SEUIL_HAUT) return 'r2'
  return 'plein'
}

/**
 * Rough CAF-style hint: 1 part first adult + 1 part second adult,
 * 0.5 per child for the first two, and 1.0 per child from the third onwards.
 * Matches: 2 ad + 2 enf = 3 parts; 1 ad + 2 enf = 2 parts.
 */
export function suggestedFiscalParts(adultes: number, enfantsCount: number): number {
  const a = Math.max(1, adultes);
  const e = Math.max(0, enfantsCount);

  // First 2 children = 0.5 each. 3rd and next = 1.0 each.
  const childrenParts = e <= 2 ? e * 0.5 : 1 + (e - 2);

  return a + childrenParts;
}

function monthFromIso(dateIso: string): number {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateIso);
  return m ? Number.parseInt(m[2]!, 10) : new Date(dateIso).getMonth() + 1;
}

/**
 * Offre Solidaire (QF reduction) applies during:
 * - Marketing « été » (Jun–Aug) when that funnel is selected
 * - Pricing season « été » (Jul–Aug on the arrival date)
 * - Vacances scolaires / fêtes on the arrival date
 * Les Karellis are excluded in winter (vs + fêtes).
 */
export function isQfReductionPeriod(
  dateIso: string | null,
  villageId?: string | null,
  marketingSeasonKey?: string | null,
): boolean {
  if (!dateIso) return false;

  // Exclude Printemps and Automne seasons strictly
  if (marketingSeasonKey === "printemps" || marketingSeasonKey === "automne") {
    return false;
  }

  const month = monthFromIso(dateIso);
  const saisonIdx = dateToSaisonIdx(dateIso);

  const isKarellis =
    villageId === "montricher-albanne" || villageId === "karellis";

  if (marketingSeasonKey === "ete" && month >= 6 && month <= 8) {
    return true;
  }

  if (saisonIdx === 2) return true;

  if (saisonIdx === 1 || saisonIdx === 3) return !isKarellis;

  return false;
}



