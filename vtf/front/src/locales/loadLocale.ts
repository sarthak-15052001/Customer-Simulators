export type Language = "FR" | "GB" | "ES" | "NL";

export type TranslationNode =
  | string
  | number
  | boolean
  | null
  | TranslationObject
  | TranslationNode[];
export type TranslationObject = { [key: string]: TranslationNode };

const loaders: Record<Language, () => Promise<{ default: TranslationObject }>> =
  {
    FR: () => import("./fr.json"),
    GB: () => import("./en.json"),
    ES: () => import("./es.json"),
    NL: () => import("./nl.json"),
  };

const cache = new Map<Language, TranslationObject>();

export async function loadLocale(lang: Language): Promise<TranslationObject> {
  const hit = cache.get(lang);
  if (hit) return hit;

  const mod = await loaders[lang]();
  cache.set(lang, mod.default);
  return mod.default;
}

export function resolveTranslation(
  messages: TranslationObject,
  path: string,
  fallback?: string,
): string {
  const keys = path.split(".");
  let result: TranslationNode = messages;

  for (const key of keys) {
    if (
      result === null ||
      typeof result !== "object" ||
      Array.isArray(result)
    ) {
      return fallback ?? path;
    }
    const obj = result as TranslationObject;
    if (obj[key] === undefined) return fallback ?? path;
    result = obj[key];
  }

  return typeof result === "string" ? result : (fallback ?? path);
}
