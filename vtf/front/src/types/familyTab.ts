/**
 * Types for the simulateur “Famille” step (single module file).
 */
export interface Enfant {
  age: number
}

export interface FamilyState {
  adultes: number
  enfants: Enfant[]
  qfVal: number | null
  maxiFamily: boolean
}

export interface FamilyTabProps {
  value: FamilyState
  onChange: (next: FamilyState) => void
}

export type QfBadgeKind = 'empty' | 'r1' | 'r2' | 'plein'

export type FamilyTabTranslations = (key: string) => string

export type AgeOption = {
  value: string
  label: string
  icon: string
}
