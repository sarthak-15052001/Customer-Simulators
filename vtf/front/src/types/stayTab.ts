import type { VtfFormule } from '../data/vtfStay'
import type { RestoMealId } from '../data/vtfResto'
import type { FuelKey, TransportMode } from '../data/vtfTransport'
import type { SejourEnvKey } from '../utils/stayTab'

export type SejourMode = 'village' | 'activite'

export type SejourState = {
  /** Funnel: saison choisie (avant dates précises). */
  fSaison: string | null
  /** Funnel: nuits choisies. */
  fNuits: number
  /** Retrieved season key from server (pricing season). */
  serverSeasonKey?: string | null
  /** Optional override date arrivée (ISO yyyy-mm-dd). */
  dateDebut: string | null
  /** Derived from dateDebut + fNuits when possible. */
  dateFin: string | null
  /** Funnel: type d'environnement. */
  fEnv: SejourEnvKey | null
  /**
   * Optional `GET /villages` filter: exact region key from `GET /regions` (`key` field).
   * Omit or `''` = all regions.
   */
  regionFilter?: string
  /**
   * Filtre modal (région): codes d’activités catalogue cochés (multi), persistés au « Soumettre ».
   */
  filterModalActivityIds?: string[]
  /** Mode de recherche. */
  mode: SejourMode
  /** Mode activité: attraction sélectionnée. */
  attractionNom: string | null
  /** Mode activité: ID de l'attraction sélectionnée (pour filtrage API). */
  attractionId?: string | null
  /**
   * Filtre modal : formule appliquée à `GET /villages` et pilule de filtre.
   * Distinct de `formule` (choix explicite sur la carte formule / devis).
   */
  formuleFilter?: VtfFormule | null
  /** Selection village dans la liste filtrée globale. */
  villageId: string | null
  /** Formule choisie pour le devis (carte formule après sélection village). */
  formule: VtfFormule | null

  /**
   * Étape "Extras" :
   * - sorties gratuites (hors budget)
   * - activités payantes (API région) => comptées dans le budget
   */
  extraActivities?: {
    freeQtyById: Record<string, number>
    paidQtyById: Record<string, number>
  }

  /** Restauration (estimatif). */
  resto: {
    qtyByMealId: Partial<Record<RestoMealId, number>>
  }

  /** Transport (estimatif). */
  transport: {
    mode: TransportMode
    /** Distance aller (km) — template slider. */
    distanceOneWayKm: number
    /** Car only: selected fuel. */
    fuel: FuelKey
  }

  /** Promos / règles. */
  promos: {
    /** Promo séjour (non cumulable avec d'autres promos séjour). Ex: 0.25 pour -25%. */
    promoSejourRate: number
    /** Quizaine futée (-10%) — cumulable (2 semaines min, PC). */
    quinzaineFutee: boolean
    /** Supplément solo par défaut: 'default' (22€/nuit), 'reduced' (11€/nuit), 'off' (0€). */
    soloSupplementMode: 'default' | 'reduced' | 'off'
  }

  /**
   * Étape "Planning" (portage du template) :
   * Planning par jour (clé ISO `yyyy-mm-dd`), par créneau.
   */
  planning?: Record<
    string,
    {
      matin: PlanningItem[]
      aprem: PlanningItem[]
      soir: PlanningItem[]
    }
  >
}

export type SejourTabProps = {
  value: SejourState
  onChange: (next: SejourState) => void
}

export type PlanningSlotKey = 'matin' | 'aprem' | 'soir'

export type PlanningItem = {
  label: string
  cat: 'vtf' | 'libre' | 'repas' | 'free' | 'paid'
  icon: React.ReactNode
  /** Optional link to an Extras activity id (for remaining count). */
  sourceId?: string
  prix?: number
}

