import { getVtfBaseUrl, getVtfOrigin } from "../config/site";
import {
  resolveVtfBookingPathParts,
  vtfResortSegment,
} from "../data/vtfBookingLocalePaths";
import type { FamilyState } from "../types/familyTab";
import type { VtfVillage } from "../data/vtfStay";
import type { Language } from "../locales/loadLocale";

const BOOKING_RESORT_SEGMENTS = ["village-vacances", "holiday-resort"] as const;

function seasonSegment(saisonKey: string, dateDebut: string): "summer" | "winter" {
  if (saisonKey === "ete") return "summer";
  if (saisonKey === "fetes") return "winter";
  const month = Number.parseInt(dateDebut.slice(5, 7), 10);
  return (month >= 1 && month <= 3) || (month >= 10 && month <= 12) ? "winter" : "summer";
}

function childBuckets(enfants: FamilyState["enfants"]) {
  const b = { nbBabies: 0, nbChildren3: 0, nbChildren1: 0, nbChildren2: 0 };
  for (const { age = 0 } of enfants) {
    if (age <= 1) b.nbBabies++;
    else if (age <= 5) b.nbChildren3++;
    else if (age <= 11) b.nbChildren1++;
    else b.nbChildren2++;
  }
  return b;
}

export function isVtfVillageBookingUrl(url: string): boolean {
  try {
    return (
      new URL(url).origin === getVtfOrigin() &&
      BOOKING_RESORT_SEGMENTS.some((segment) => url.includes(`/${segment}/`)) &&
      url.includes("search_engine")
    );
  } catch {
    return false;
  }
}

/** VTF village booking URL (reserve, share, email, PDF). */
export function buildVtfBookingUrl(
  village: VtfVillage | null,
  family: FamilyState,
  dateDebut: string | null,
  dateFin: string | null,
  saisonKey: string,
  lang?: Language,
): string {
  if (!dateDebut || !dateFin) return getVtfBaseUrl(lang);

  const fallbackDept = village?.vtfDepartment?.trim();
  const fallbackCity = village?.vtfCity?.trim();
  const fallbackSlug = village?.vtfSlug?.trim();
  const { department: dept, city, slug } = resolveVtfBookingPathParts(
    village?.id,
    lang,
    {
      department: fallbackDept ?? "",
      city: fallbackCity ?? "",
      slug: fallbackSlug ?? "",
    },
  );
  const season = seasonSegment(saisonKey, dateDebut);
  const resortSegment = vtfResortSegment(lang);
  const shopBase = getVtfBaseUrl(lang).replace(/\/?$/, "/");
  const path =
    dept && city && slug
      ? `${shopBase}${season}/${resortSegment}/${dept}/${city}/${slug}`
      : shopBase.replace(/\/$/, "");

  const buckets = childBuckets(family.enfants ?? []);
  const qs = new URLSearchParams({
    "search_engine[startedAt]": dateDebut,
    "search_engine[endedAt]": dateFin,
    "search_engine[nbPersons]": String(family.adultes + (family.enfants?.length ?? 0)),
    "search_engine[nbAdults]": String(family.adultes),
    "search_engine[nbBabies]": String(buckets.nbBabies),
    "search_engine[nbChildren3]": String(buckets.nbChildren3),
    "search_engine[nbChildren1]": String(buckets.nbChildren1),
    "search_engine[nbChildren2]": String(buckets.nbChildren2),
  }).toString();

  return qs ? `${path}?${qs}` : path;
}
