import type { RegionActivityDto } from "../api/regionActivities.api";
import type { FreeActivity, PaidActivity, VtfSeasonKey } from "../data/vtfExtras";

export function mapRegionActivitiesToFree(
  rows: RegionActivityDto[],
): FreeActivity[] {
  return rows.map((a) => ({ id: a.id, nom: a.nom, type: a.type }));
}

export function mapRegionActivitiesToPaid(
  rows: RegionActivityDto[],
): PaidActivity[] {
  return rows.map((a) => ({
    id: a.id,
    nom: a.nom,
    type: a.type,
    ad: typeof a.ad === "number" ? a.ad : 0,
    enf: typeof a.enf === "number" ? a.enf : 0,
    saisons: Array.isArray(a.saisons) ? a.saisons : [],
  }));
}

export function filterPaidActivitiesBySeason(
  list: PaidActivity[],
  saisonKey: VtfSeasonKey,
): PaidActivity[] {
  return list.filter(
    (a) => !a.saisons?.length || a.saisons.includes(saisonKey),
  );
}

export function activityDisplayTitle(type: string, nom: string): string {
  return `${type} ${nom}`.trim();
}

export function paidActivityUnitPrice(
  activity: Pick<PaidActivity, "ad" | "enf">,
  adults: number,
  children: number,
): number {
  return (
    Math.max(0, activity.ad) * Math.max(0, adults) +
    Math.max(0, activity.enf) * Math.max(0, children)
  );
}
