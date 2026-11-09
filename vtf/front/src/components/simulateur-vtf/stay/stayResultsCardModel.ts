import type { VtfVillage } from "../../../data/vtfStay";

export type VillagesPaging = {
  totalCount: number;
  pageSize: number;
  offset: number;
  onOffsetChange: (nextOffset: number) => void;
};

export type MergedAttraction = {
  id: string;
  nom: string;
  type: string;
  icon: string;
  minKm: number;
};

export function normalizeResultsSearch(q: string): string {
  return q.trim().toLowerCase();
}

export function villageMatchesResultsSearch(v: VtfVillage, searchQNorm: string): boolean {
  if (!searchQNorm) return true;
  const hay = [v.nom, v.nom2, v.region, String(v.id), v.env]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return hay.includes(searchQNorm);
}

export function attractionMatchesResultsSearch(
  a: Pick<MergedAttraction, "nom" | "type">,
  searchQNorm: string,
): boolean {
  if (!searchQNorm) return true;
  return `${a.nom} ${a.type}`.toLowerCase().includes(searchQNorm);
}
