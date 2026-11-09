import type { VtfFormule, VtfVillage } from "../data/vtfStay";

export type SejourEnvKey = "mer" | "montagne" | "campagne" | "ski" | "fond";

export type QuickSearchMarketingSeason = {
  key: string;
  startDate?: string;
  endDate?: string;
  defaultDate?: string;
  defaultStartDate?: string;
  salesOpenDate?: string;
};

function toIsoYmd(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString().split("T")[0]!;
}

function isDateInSeason(dateIso: string, season: QuickSearchMarketingSeason): boolean {
  const start = toIsoYmd(season.startDate);
  const end = toIsoYmd(season.endDate);
  if (!start || !end) return false;
  return dateIso >= start && dateIso <= end;
}

function firstOpenDateFrom(
  ouverture: string | undefined,
  fromIso: string,
  maxDays: number,
  match?: (dateIso: string) => boolean,
): string | null {
  for (let i = 0; i <= maxDays; i++) {
    const dateIso = addDaysIso(fromIso, i);
    if (!isVillageOuvert(ouverture, dateIso)) continue;
    if (match && !match(dateIso)) continue;
    return dateIso;
  }
  return null;
}

/** Quick Search: season + date from first village-open day, env from village + season. */
export function pickQuickSearchStay(
  village: {
    ouverture?: string;
    ski?: boolean;
    region?: string;
    envCode?: string;
    env?: string;
  },
  seasons: QuickSearchMarketingSeason[],
  fallbackSeasonKey: string,
  todayIso: string = todayIsoLocal(),
): { seasonKey: string; dateDebut: string; fEnv: SejourEnvKey } {
  const openDate = firstOpenDateFrom(village.ouverture, todayIso, 400);
  const seasonKey = openDate
    ? (seasons.find((s) => isDateInSeason(openDate, s))?.key ??
      fallbackSeasonKey)
    : fallbackSeasonKey;
  const dateDebut =
    openDate ??
    toIsoYmd(seasons.find((s) => s.key === fallbackSeasonKey)?.defaultDate) ??
    todayIso;

  return {
    seasonKey,
    dateDebut,
    fEnv: resolveQuickSearchEnv(village, seasonKey),
  };
}

/** Default formule when a village is selected (keeps current if still valid). */
export function resolveVillageFormule(
  villageFormules: VtfFormule[] | undefined,
  current: VtfFormule | null = null,
): VtfFormule | null {
  if (!villageFormules?.length) return null;
  if (current && villageFormules.includes(current)) return current;
  return villageFormules[0] ?? null;
}

function resolveQuickSearchEnv(
  village: {
    ski?: boolean;
    region?: string;
    envCode?: string;
    env?: string;
  },
  seasonKey: string,
): SejourEnvKey {
  const nordic =
    village.region?.includes("Massif Central") ||
    village.region?.includes("Jura");

  if (village.ski) {
    if (seasonKey === "hiver") return nordic ? "fond" : "ski";
    return "montagne";
  }

  const envMap: Record<string, SejourEnvKey> = {
    "🏖️": "mer",
    "🌊": "mer",
    "☀️": "mer",
    "⛰️": "montagne",
    "🌲": "campagne",
    "🌻": "campagne",
    sea: "mer",
    ocean: "mer",
    sun: "mer",
    mountain: "montagne",
    forest: "campagne",
    countryside: "campagne",
    nature: "campagne",
    ski: "ski",
    snow: "fond",
  };
  const raw = village.envCode || village.env || "mer";
  return (
    envMap[raw] ??
    (["mer", "montagne", "campagne", "ski", "fond"].includes(raw)
      ? (raw as SejourEnvKey)
      : "mer")
  );
}

/** UI constants for village highlights, opening-date parsing, and season index fallback. */
const CONFIG = {
  villageHighlights: {
    envByEmoji: {
      "🌊": "highlightsEnvSea",
      "⛰️": "highlightsEnvMountain",
      "🌲": "highlightsEnvCountryside",
      "🎿": "highlightsEnvSki",
      "🌻": "highlightsEnvSunProvence",
      "☀️": "highlightsEnvSun",
    } as Record<string, string>,
    flagBadges: [
      { id: "bebeClub", icon: "👶", textKey: "highlightsBebeClub" },
      { id: "forfaitRM", icon: "⛷️", textKey: "highlightsForfaitRM" },
      { id: "qfExc", icon: "💎", textKey: "highlightsQfExc" },
      { id: "enfSoloHalf", icon: "👩‍👦", textKey: "highlightsEnfSoloHalf" },
      { id: "locAndPc", icon: "🏡", textKey: "highlightsLocAndPc" },
    ],
  },
  villageOuverture: {
    skipIfContains: ["sur demande", "confirmer"],
    defaultYearWhenOmitted: new Date().getFullYear(),
  },
  pricingSeasonJj: {
    defaultIdx: 0 as const,
    eteMinJj: 701,
    eteMaxJj: 831,
    fetesJjGte: 1220,
    fetesJjLte: 105,
  },
  pricingSeasonVsOrGroups: [
    [{ m: 2 }, { m: 4 }, { m: 10, jMin: 20 }, { m: 11, jMax: 5 }],
  ],
};

export function addDaysIso(isoDate: string, days: number): string {
  const d = new Date(isoDate);
  d.setDate(d.getDate() + days);
  return d.toISOString().split("T")[0]!;
}

/** Today in the local calendar as `yyyy-MM-dd` (default arrival date). */
export function todayIsoLocal(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function diffNuits(
  dateDebut: string | null,
  dateFin: string | null,
): number | null {
  if (!dateDebut || !dateFin) return null;
  const ms = new Date(dateFin).getTime() - new Date(dateDebut).getTime();
  const days = Math.round(ms / (1000 * 60 * 60 * 24));
  return days;
}

function vsIdxFromMonthDay(m: number, j: number): boolean {
  return CONFIG.pricingSeasonVsOrGroups.some((group) =>
    group.some(
      (c) =>
        c.m === m &&
        (c.jMin === undefined || j >= c.jMin) &&
        (c.jMax === undefined || j <= c.jMax),
    ),
  );
}

export function dateToSaisonIdx(dateStr: string | null): 0 | 1 | 2 | 3 {
  const p = CONFIG.pricingSeasonJj;
  if (!dateStr) return p.defaultIdx;
  const d = new Date(dateStr);
  const m = d.getMonth() + 1;
  const j = d.getDate();
  const jj = m * 100 + j;
  if (jj >= p.eteMinJj && jj <= p.eteMaxJj) return 2;
  if (jj >= p.fetesJjGte || jj <= p.fetesJjLte) return 3;
  if (vsIdxFromMonthDay(m, j)) return 1;
  return 0;
}

type OuverturePlage = { abs1: number; abs2: number };

function parseOuverture(
  str: string | undefined | null,
): OuverturePlage[] | null {
  if (!str) return null;
  if (CONFIG.villageOuverture.skipIfContains.some((s) => str.includes(s)))
    return null;
  let s = str;
  s = s.replace(/\([^)]*\)/g, "");
  s = s.replace(/[A-Za-zÀ-ÿ]+\s+(?:LOC|PC|DP)[/A-Za-z]*/g, "");
  const plageRe =
    /([0-9]{1,2})\/([0-9]{1,2})(?:\/([0-9]{2}))?[–-]([0-9]{1,2})\/([0-9]{1,2})(?:\/([0-9]{2}))?/g;

  const matches = [...s.matchAll(plageRe)];
  if (!matches.length) return null;

  let yHint = new Date().getFullYear();
  for (const m of matches) {
    if (m[3]) yHint = Math.max(yHint, 2000 + Number.parseInt(m[3], 10));
    if (m[6]) yHint = Math.max(yHint, 2000 + Number.parseInt(m[6], 10));
  }

  const plages: OuverturePlage[] = [];
  for (const m of matches) {
    const d1j = Number.parseInt(m[1]!, 10);
    const d1m = Number.parseInt(m[2]!, 10);
    const d1yRaw = m[3] ? Number.parseInt(m[3], 10) : null;
    const d2j = Number.parseInt(m[4]!, 10);
    const d2m = Number.parseInt(m[5]!, 10);
    const d2yRaw = m[6] ? Number.parseInt(m[6], 10) : null;
    const y2 = d2yRaw ? 2000 + d2yRaw : yHint;
    let y1: number;
    if (d1yRaw) y1 = 2000 + d1yRaw;
    else if (d1m > d2m || (d1m === d2m && d1j > d2j)) y1 = y2 - 1;
    else y1 = y2;

    const addPlage = (yearOffset: number) => {
      plages.push({
        abs1: (y1 + yearOffset) * 10000 + d1m * 100 + d1j,
        abs2: (y2 + yearOffset) * 10000 + d2m * 100 + d2j,
      });
    };

    addPlage(0);
    if (!d1yRaw && !d2yRaw) {
      addPlage(1);
      addPlage(2);
    }
  }
  return plages.length ? plages : null;
}

export function isVillageOuvert(
  ouvertureStr: string | undefined,
  dateStr: string | null,
): boolean {
  if (!ouvertureStr || !dateStr) return true;
  if (
    CONFIG.villageOuverture.skipIfContains.some((s) =>
      ouvertureStr.toLowerCase().includes(s),
    )
  ) {
    return false;
  }
  const plages = parseOuverture(ouvertureStr);
  if (!plages) return true;
  const d = new Date(dateStr);
  const djj = d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate();
  return plages.some((p) => djj >= p.abs1 && djj < p.abs2);
}

function flagBadgeApplies(v: VtfVillage, id: string): boolean {
  if (id === "locAndPc")
    return v.formules.includes("LOC") && v.formules.includes("PC");
  return Boolean((v as Record<string, unknown>)[id]);
}

export function getHighlights(
  v: VtfVillage,
  t: (key: string) => string,
): Array<{ icon: string; txt: string }> {
  const hl: Array<{ icon: string; txt: string }> = [];
  const { envByEmoji, flagBadges } = CONFIG.villageHighlights;
  const envKey = envByEmoji[v.env];
  if (envKey) hl.push({ icon: v.env, txt: t(envKey) });
  for (const row of flagBadges) {
    if (flagBadgeApplies(v, row.id))
      hl.push({ icon: row.icon, txt: t(row.textKey) });
  }
  return hl.slice(0, 3);
}
