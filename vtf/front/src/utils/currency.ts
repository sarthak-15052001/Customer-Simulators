/**
 * Central EUR formatting for the VTF simulator UI.
 *
 * Always render prices with `formatEuro` instead of hardcoding `€`, `Math.round`,
 * or locale strings. That keeps spacing, rounding, and symbol placement identical
 * everywhere (recap, tabs, QF badges, transport, extras).
 *
 * @example Totals and recap rows
 * formatEuro(estimate.total) // "1234 €"
 *
 * @example Secondary lines (per person, unit rates)
 * formatEuro(price, { compact: true }) // "12€"
 *
 * @example Rate with unit
 * formatEuro(costPerKm, { compact: true, suffix: "/km" }) // "12€/km"
 *
 * @example Recap metric from API string
 * formatEuro(perDayStr, { suffix: "/ pers / jour" }) // "45 €/ pers / jour" or null
 *
 * For QF threshold copy in translations, use `fillQfTemplate` in `familyTab.ts`
 * (placeholders `{{low}}`, `{{high}}`, `{{amount}}`, `{{euro}}`).
 */

export type FormatEuroOptions = {
  /** true → `12€` (meta lines, thresholds); false → `12 €` (default, totals). */
  compact?: boolean;
  /** Text after the symbol, e.g. `"/km"` or `"/ pers / jour"`. */
  suffix?: string;
  /** Keep decimals (e.g. fuel `0.12€/km`). Default: round to whole euros. */
  decimals?: number;
};

const NBSP = "\u00a0";
const SYM = "€";

/** Spaced euro sign for static labels, e.g. `{{euro}} / mois` → ` € / mois`. */
export const EURO_MARK = `${NBSP}${SYM}`;

function amountToString(amount: number, decimals?: number): string {
  if (!Number.isFinite(amount)) return "0";
  if (decimals != null) return amount.toFixed(decimals);
  return String(Math.round(amount));
}

function parseAmount(
  amount: number | string,
  decimals?: number,
): number | string | null {
  if (typeof amount === "number") {
    return Number.isFinite(amount) ? amountToString(amount, decimals) : "0";
  }
  const trimmed = amount.trim();
  if (trimmed === "" || trimmed === "-") return null;
  const n = Number(trimmed);
  return Number.isFinite(n) ? amountToString(n, decimals) : trimmed;
}

function formatCore(
  parsed: number | string,
  compact: boolean,
  suffix: string,
): string {
  const numStr = typeof parsed === "number" ? String(parsed) : parsed;
  const base = compact ? `${numStr}${SYM}` : `${numStr}${NBSP}${SYM}`;
  const s = suffix.trim();
  if (!s) return base;
  const glue = compact && s.startsWith("/") ? "" : compact ? " " : "";
  return `${base}${glue}${s}`;
}

export function formatEuro(amount: number, options?: FormatEuroOptions): string;
export function formatEuro(
  amount: string,
  options: FormatEuroOptions & { suffix: string },
): string | null;
export function formatEuro(
  amount: number | string,
  options?: FormatEuroOptions,
): string | null {
  const { compact = false, suffix = "", decimals } = options ?? {};
  const parsed = parseAmount(amount, decimals);
  if (parsed === null) return null;
  return formatCore(parsed, compact, suffix);
}

/**
 * Intl-based EUR string for exports that must follow the user locale.
 * Simulator screens should use `formatEuro` for a single VTF look and feel.
 */
export function formatEuroLocale(
  amount: number,
  locale: string = "fr-FR",
): string {
  if (!Number.isFinite(amount)) return formatEuro(0) as string;

  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  })
    .format(amount)
    .replace(/[\u202F\u00A0]/g, NBSP);
}

/** Whole-number percent for discount chips and recap (not a currency value). */
export function formatPercentInt(pct: number | null | undefined): string {
  if (pct == null || !Number.isFinite(pct)) return "0";
  return String(Math.round(pct));
}
