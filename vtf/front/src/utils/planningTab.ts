import type { ReactNode } from "react";
import type { Language } from "../locales/loadLocale";
import type {
  PlanningItem,
  PlanningSlotKey,
  SejourState,
} from "../types/stayTab";

const APP_LANGUAGE_LOCALE: Record<Language, string> = {
  FR: "fr-FR",
  GB: "en-GB",
  ES: "es-ES",
  NL: "nl-NL",
};

export function appLanguageToIntlLocale(language: Language): string {
  return APP_LANGUAGE_LOCALE[language] ?? "fr-FR";
}

export function formatPlanningDayLabel(
  iso: string,
  locale: string = "fr-FR",
): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;

  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  void locale;
  return `${dd}/${mm}/${yyyy}`;
}

export type StayDay = {
  key: string;
  label: string; // Keeping for compatibility, but we will prefer index/isDeparture
  date: Date;
  index: number;
  isDeparture: boolean;
};

function isoDayKey(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function safeParseIsoDate(iso: string): Date | null {
  // Expect yyyy-mm-dd from the app state.
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function getStayDays(
  dateDebutIso: string | null,
  dateFinIso: string | null,
): StayDay[] {
  if (!dateDebutIso || !dateFinIso) return [];
  const start = safeParseIsoDate(dateDebutIso);
  const end = safeParseIsoDate(dateFinIso);
  if (!start || !end) return [];
  if (end.getTime() < start.getTime()) return [];

  const out: StayDay[] = [];
  const cur = new Date(start);
  let idx = 0;
  // Industry standard for holiday villages: include the departure day (N nights = N+1 days).
  while (cur.getTime() <= end.getTime()) {
    const key = isoDayKey(cur);
    const isDeparture = cur.getTime() === end.getTime();
    out.push({
      key,
      date: new Date(cur),
      index: idx + 1,
      isDeparture,
      label: key,
    });
    cur.setDate(cur.getDate() + 1);
    idx++;
    if (idx > 31) break;
  }
  return out;
}

export function planningItemKey(i: PlanningItem): string {
  return `${i.cat}:${i.label}`;
}

export function formatPlanningPickerLabel(
  label: string,
  stats: { placed: number; total: number } | null,
  t: (path: string) => string,
): string {
  if (!stats) return label;
  return t("simulateur.planning.activityUsed")
    .replace("{{label}}", label)
    .replace("{{placed}}", String(stats.placed))
    .replace("{{total}}", String(stats.total));
}

export function emptyDaySlots(): Record<PlanningSlotKey, PlanningItem[]> {
  return { matin: [], aprem: [], soir: [] };
}

export type PlanningPickerGroupKey =
  | "includes"
  | "free"
  | "paid"
  | "meal"
  | "freeTime";

export type PlanningPickerGroup = {
  key: PlanningPickerGroupKey;
  title: string;
  icon: ReactNode;
  items: PlanningItem[];
};

function expandSelectableByQty(
  items: PlanningItem[],
  cat: PlanningItem["cat"],
  extra: SejourState["extraActivities"] | undefined,
  restoQty: Partial<Record<string, number>> | undefined,
): PlanningItem[] {
  const out: PlanningItem[] = [];
  for (const it of items) {
    if (!it.sourceId) {
      out.push(it);
      continue;
    }
    let qty = 0;
    if (cat === "free") qty = extra?.freeQtyById?.[it.sourceId] ?? 0;
    else if (cat === "paid") qty = extra?.paidQtyById?.[it.sourceId] ?? 0;
    else if (cat === "repas") qty = restoQty?.[it.sourceId] ?? 0;
    for (let n = 0; n < qty; n++) out.push(it);
  }
  return out;
}

function partitionIncludes(items: PlanningItem[]) {
  const evening: PlanningItem[] = [];
  const daytime: PlanningItem[] = [];
  const other: PlanningItem[] = [];
  for (const it of items) {
    const l = it.label.toLowerCase();
    if (/soir|anim|spectacle|musique|festiv/.test(l)) evening.push(it);
    else if (/rando|randonn|journ|pisc|club|piscine|sport/.test(l))
      daytime.push(it);
    else other.push(it);
  }
  return { evening, daytime, other };
}

function createRoundRobin(items: PlanningItem[]): () => PlanningItem | null {
  let idx = 0;
  return () => {
    if (!items.length) return null;
    const it = items[idx % items.length];
    idx += 1;
    return it;
  };
}

export type BuildDefaultPlanningParams = {
  days: StayDay[];
  groups: PlanningPickerGroup[];
  extra: SejourState["extraActivities"] | undefined;
  restoQty: Partial<Record<string, number>> | undefined;
  freeTimeFallback: PlanningItem;
};

/** Fills the schedule from picker groups (extras / resto selections + VTF inclus). */
export function buildDefaultPlanning({
  days,
  groups,
  extra,
  restoQty,
  freeTimeFallback,
}: BuildDefaultPlanningParams): NonNullable<SejourState["planning"]> {
  const includesRaw = groups.find((g) => g.key === "includes")?.items ?? [];
  const { evening, daytime, other } = partitionIncludes(includesRaw);
  const nextEvening = createRoundRobin(evening);
  const nextDaytime = createRoundRobin(daytime);
  const nextOther = createRoundRobin(other);

  const freePool = expandSelectableByQty(
    groups.find((g) => g.key === "free")?.items ?? [],
    "free",
    extra,
    restoQty,
  );
  const paidPool = expandSelectableByQty(
    groups.find((g) => g.key === "paid")?.items ?? [],
    "paid",
    extra,
    restoQty,
  );
  const mealPool = expandSelectableByQty(
    groups.find((g) => g.key === "meal")?.items ?? [],
    "repas",
    extra,
    restoQty,
  );

  const fillSlot = (
    pools: Array<PlanningItem[] | (() => PlanningItem | null)>,
  ): PlanningItem => {
    for (const p of pools) {
      if (typeof p === "function") {
        const it = p();
        if (it) return it;
      } else if (p.length > 0) {
        const it = p.shift();
        if (it) return it;
      }
    }
    return freeTimeFallback;
  };

  const next: NonNullable<SejourState["planning"]> = {};

  days.forEach((d) => {
    next[d.key] = emptyDaySlots();
    next[d.key].matin = [
      fillSlot([
        paidPool,
        freePool,
        nextDaytime,
        nextOther,
        nextEvening,
        mealPool,
      ]),
    ];
    next[d.key].aprem = [
      fillSlot([paidPool, freePool, nextDaytime, nextOther, nextEvening]),
    ];
    next[d.key].soir = [
      fillSlot([mealPool, nextEvening, paidPool, freePool, nextDaytime]),
    ];
  });

  return next;
}
