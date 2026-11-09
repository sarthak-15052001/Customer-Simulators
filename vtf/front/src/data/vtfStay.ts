import type { VtfInfraEntry } from './vtfExtras'

export type VtfFormule = 'PC' | 'DP' | 'LOC'

export type VtfSaisonKey = 'hs' | 'vs' | 'ete' | 'fetes'

export type VtfVillage = {
  id: string
  nom: string
  nom2?: string
  region: string
  /** Emoji env dans la source VTF. */
  env: string
  formules: VtfFormule[]
  hasLoc: boolean
  ski: boolean
  ouverture?: string
  tarifs: {
    PC?: Partial<Record<VtfSaisonKey, number>>
    LOC?: Partial<Record<VtfSaisonKey, number>>
  }
  perAdultBase?: number
  staySubtotal?: number
  tarif_unit?: string
  tarifUnit?: string
  // Optionnels (utiles pour highlights)
  bebeClub?: boolean
  forfaitRM?: boolean
  qfExc?: boolean
  enfSoloHalf?: boolean
  vtfDepartment?: string
  vtfCity?: string
  vtfSlug?: string
  /** Data populated when fetched deeply from API `/api/v1/villages/{id}/` endpoint. */
  infra?: VtfInfraEntry
}
