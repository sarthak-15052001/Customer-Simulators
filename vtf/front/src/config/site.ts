import type { Language } from "../locales/loadLocale";

const DEFAULT_VTF_BASE_URL = "https://www.vtf-vacances.com/fr_FR/";

const VTF_LOCALE_MAP: Record<Language, string> = {
  FR: "fr_FR",
  GB: "en_GB",
  ES: "fr_FR",
  // NL has no dedicated VTF site — redirect to the French site
  NL: "fr_FR",
};

/** VTF public site base (locale path included), from `VITE_VTF_BASE_URL`. */
export function getVtfBaseUrl(lang?: Language): string {
  const raw = import.meta.env.VITE_VTF_BASE_URL?.trim();
  let base = raw || DEFAULT_VTF_BASE_URL;
  if (!base.endsWith("/")) base = `${base}/`;

  if (lang && VTF_LOCALE_MAP[lang]) {
    const locale = VTF_LOCALE_MAP[lang];
    // Regex matches /xx_XX/ pattern (common for VTF locales)
    const localeRegex = /\/([a-z]{2}_[A-Z]{2})\//;
    if (localeRegex.test(base)) {
      return base.replace(localeRegex, `/${locale}/`);
    }
    // If no locale pattern found, but we have a lang, we might want to append it?
    // However, usually the base URL should already have a locale or be the root.
    // Given the previous requirement, we assume it has a locale to replace.
  }

  return base;
}

/** Origin only, e.g. `https://www.vtf-vacances.com` */
export function getVtfOrigin(): string {
  try {
    return new URL(getVtfBaseUrl()).origin;
  } catch {
    return "https://www.vtf-vacances.com";
  }
}

/** Absolute URL on the VTF shop (path without locale prefix, e.g. `contactez-nous`). */
export function vtfUrl(path: string, lang?: Language): string {
  if (path.startsWith("http")) return path;
  const base = getVtfBaseUrl(lang);
  // Remove any leading slash and any existing xx_XX locale from the path
  const normalized = path
    .replace(/^\//, "")
    .replace(/^[a-z]{2}_[A-Z]{2}\//, "");
  return `${base}${normalized}`;
}
