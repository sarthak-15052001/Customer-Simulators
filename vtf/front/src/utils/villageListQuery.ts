import type { VtfFormule } from "../data/vtfStay";
import type { SejourEnvKey } from "./stayTab";

/** `GET /villages` query — see API docs (env, formule, limit, offset, openOn, dateDebut, dateFin, region, search, ski). */
export type VillagesListQueryParams = {
  env: string;
  formule?: VtfFormule | null;
  limit: number;
  offset: number;
  openOn?: string;
  dateDebut?: string;
  dateFin?: string;
  region?: string;
  search?: string;
  ski?: boolean;
  attractionId?: string;
};

export function buildVillagesListQueryParams(input: {
  fEnv: SejourEnvKey;
  formule: VtfFormule | null;
  dateDebut: string | null;
  dateFin?: string | null;
  limit: number;
  offset: number;
  region?: string | null;
  search?: string | null;
  attractionId?: string | null;
}): VillagesListQueryParams {
  const out: VillagesListQueryParams = {
    env: input.fEnv,
    limit: input.limit,
    offset: input.offset,
  };
  if (input.formule) out.formule = input.formule;

  if (input.dateDebut) {
    out.openOn = input.dateDebut;
    out.dateDebut = input.dateDebut;
  }
  if (input.dateFin) {
    out.dateFin = input.dateFin;
  }
  if (input.region?.trim()) out.region = input.region.trim();
  if (input.search?.trim()) out.search = input.search.trim();
  if (input.fEnv === "ski") out.ski = true;
  if (input.attractionId?.trim()) out.attractionId = input.attractionId.trim();
  return out;
}
