import type { Language } from "../locales/loadLocale";

export type VtfBookingPathParts = {
  department: string;
  city: string;
  slug: string;
};

/** VTF shop resort category segment by simulator language. */
export const VTF_RESORT_SEGMENT: Record<Language, string> = {
  FR: "village-vacances",
  GB: "holiday-resort",
  ES: "village-vacances",
  NL: "village-vacances",
};

/**
 * English path overrides keyed by village id.
 * FR paths are stored on the village record; EN slugs differ on vtf-vacances.com.
 */
export const VTF_BOOKING_PATH_GB: Record<string, VtfBookingPathParts> = {
  "saint-cast": {
    department: "cotes-d-armor",
    city: "saint-cast-le-guildo",
    slug: "saint-cast-le-guildo-l-hotel-des-bains-vtf-hotel",
  },
  blainville: {
    department: "channel",
    city: "blainville-sur-mer",
    slug: "blainville-le-senequet-vtf-holiday-village",
  },
  riec: {
    department: "finistere",
    city: "riec-sur-belon",
    slug: "riec-sur-belon-ker-belen-le-pigneroux-vtf-holiday-village",
  },
  biarritz: {
    department: "atlantic-pyrenees",
    city: "biarritz",
    slug: "biarritz-domaine-de-francon-vtf-holiday-village",
  },
  lacanau: {
    department: "gironde",
    city: "lacanau",
    slug: "lacanau-ocean-la-forestiere-vtf-holiday-village",
  },
  carcans: {
    department: "gironde",
    city: "carcans",
    slug: "carcans-les-bruyeres-vtf-holiday-village",
  },
  biscarrosse: {
    department: "landes",
    city: "biscarrosse",
    slug: "biscarrosse-la-jaougue-soule-vtf-holiday-village",
  },
  bandol: {
    department: "var",
    city: "bandol",
    slug: "bandol-clairefont-vtf-hotel",
  },
  "sainte-maxime": {
    department: "var",
    city: "sainte-maxime",
    slug: "sainte-maxime-golfe-de-saint-tropez-vtf-vvf-holiday-village",
  },
  agde: {
    department: "herault",
    city: "agde",
    slug: "domaine-d-agde-vtf-holiday-village",
  },
  chamonix: {
    department: "haute-savoie",
    city: "chamonix",
    slug: "chamonix-les-econtres-vtf-holiday-village",
  },
  "alpe-dhuez": {
    department: "isere",
    city: "alpe-d-huez",
    slug: "le-balcon-de-l-alpe-vtf-holiday-village",
  },
  doucy: {
    department: "savoy",
    city: "doucy-combelouviere",
    slug: "doucy-valmorel-les-carlines-vtf-holiday-village",
  },
  karellis: {
    department: "savoy",
    city: "montricher-albanne",
    slug: "karellis-balcons-de-maurienne-vtf-holiday-village",
  },
  "la-plagne": {
    department: "savoy",
    city: "la-plagne-montalbert",
    slug: "plagne-montalbert-le-dou-de-la-ramaz-vtf-holiday-village",
  },
  montgenevre: {
    department: "hautes-alpes",
    city: "montgenevre",
    slug: "montgenevre-le-grand-hotel-vtf-hotel",
  },
  "le-sauze": {
    department: "alpes-de-haute-provence",
    city: "le-sauze-barcelonnette",
    slug: "le-sauze-les-balcons-du-sauze-vtf-holiday-village",
  },
  praloup: {
    department: "alpes-de-haute-provence",
    city: "uvernet-fours",
    slug: "praloup-l-ouka-vtf-hotel",
  },
  arvieux: {
    department: "hautes-alpes",
    city: "arvieux",
    slug: "arvieux-les-esquirousses-vtf-holiday-village",
  },
  savines: {
    department: "hautes-alpes",
    city: "savines-le-lac",
    slug: "savines-le-lac-le-pigneroux-vtf-holiday-village",
  },
  "saint-sauves": {
    department: "puy-de-dome",
    city: "saint-sauves-d-auvergne",
    slug: "saint-sauves-le-domaine-des-puys-vtf-holiday-village",
  },
  metabief: {
    department: "doubs",
    city: "metabief",
    slug: "metabief-le-bief-rouge-vtf-holiday-village",
  },
  soultzeren: {
    department: "haut-rhin",
    city: "soultzeren",
    slug: "soultzeren-les-fougeres-vtf-holiday-village",
  },
  "font-durle": {
    department: "drome",
    city: "bouvante",
    slug: "font-urle-vtf-holiday-village",
  },
  bedoin: {
    department: "vaucluse",
    city: "bedoin",
    slug: "bedoin-les-florans-vtf-holiday-village",
  },
  cereste: {
    department: "alpes-de-haute-provence",
    city: "cereste",
    slug: "cereste-domaine-du-grand-luberon-vtf-holiday-village",
  },
  singleyrac: {
    department: "dordogne",
    city: "singleyrac",
    slug: "singleyrac-le-domaine-du-peyrichoux-vtf-holiday-village",
  },
  areches: {
    department: "savoy",
    city: "areches-beaufort",
    slug: "areches-beaufort-le-rafour-vtf-holiday-village",
  },
  vernet: {
    department: "eastern-pyrenees",
    city: "vernet-les-bains",
    slug: "vernet-les-bains-clair-canigou-vtf-holiday-village",
  },
  talloires: {
    department: "haute-savoie",
    city: "talloires",
    slug: "talloires-les-alerions-vtf-holiday-village",
  },
  "montricher-albanne": {
    department: "savoy",
    city: "montricher-albanne",
    slug: "karellis-balcons-de-maurienne-vtf-holiday-village",
  },
};

export function vtfResortSegment(lang?: Language): string {
  if (lang && VTF_RESORT_SEGMENT[lang]) return VTF_RESORT_SEGMENT[lang];
  return VTF_RESORT_SEGMENT.FR;
}

export function resolveVtfBookingPathParts(
  villageId: string | undefined,
  lang: Language | undefined,
  fallback: VtfBookingPathParts,
): VtfBookingPathParts {
  if (lang === "GB" && villageId && VTF_BOOKING_PATH_GB[villageId]) {
    return VTF_BOOKING_PATH_GB[villageId];
  }
  return fallback;
}
