export type VtfSeasonKey = 'hs' | 'vs' | 'ete' | 'fetes'

export type FreeActivity = { id: string; nom: string; type: string }
export type PaidActivity = { id: string; nom: string; type: string; ad: number; enf: number; saisons: VtfSeasonKey[] }

export type VtfInfraEntry = {
  infra?: string[]
  anim?: { ete?: string[]; hiver?: string[]; hs?: string[] }
  extras?: { ete?: string; hiver?: string }
}

