/**
 * Utility for resolving localized price suffix labels based on dynamic API `tarif_unit` values and stay formula type.
 */

const ADULT_PREFIX_MAP: Record<string, string> = {
  GB: "/adult",
  ES: "/adulto",
  NL: "/volwassene",
  FR: "/adulte",
};

const ACCOMMODATION_PREFIX_MAP: Record<string, string> = {
  GB: "/accommodation",
  ES: "/alojamiento",
  NL: "/accommodatie",
  FR: "/hébergement",
};

const UNIT_LABEL_MAP: Record<string, { week: string; night: string; stay: string }> = {
  GB: { week: "week", night: "night", stay: "stay" },
  NL: { week: "week", night: "nacht", stay: "verblijf" },
  ES: { week: "semana", night: "noche", stay: "estancia" },
  FR: { week: "semaine", night: "nuit", stay: "séjour" },
};

/**
 * Resolves localized price suffix (e.g. `/adulte · semaine` or `/ hébergement · semaine`)
 * based on API `tarif_unit`, active language code (`FR` | `GB` | `ES` | `NL`), and accommodation flag.
 */
export function getDynamicPriceSuffix(
  rawUnit: string | undefined,
  t: (key: string) => string,
  lang: string,
  isAccommodation?: boolean,
): string {
  const code = (lang || "FR").toUpperCase();
  const unit = (rawUnit || "").toLowerCase().trim();

  if (!rawUnit && !isAccommodation) return t("resultsPriceSuffix");

  const isNight = unit.startsWith("nuit") || unit.startsWith("night");
  const isStay = unit.startsWith("sejour") || unit.startsWith("séjour") || unit.startsWith("stay");

  const currentLang = UNIT_LABEL_MAP[code] ? code : "FR";
  const units = UNIT_LABEL_MAP[currentLang];
  const label = isNight ? units.night : isStay ? units.stay : units.week;

  const prefix = isAccommodation
    ? ACCOMMODATION_PREFIX_MAP[currentLang]
    : ADULT_PREFIX_MAP[currentLang];

  return `${prefix} · ${label}`;
}
