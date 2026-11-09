export type VtfPromoKey = 'none' | 'premiere' | 'derniere' | 'jeudi' | 'pack'

export type PromoChoice = {
  key: VtfPromoKey
  icon: string
  label: string
  description: string
  tag: string
  /** Discount rate applied on stay base. Ex: 0.2 means -20%. */
  rate: number
  /** Whether promo is "flash/auto" (derived from dates) vs manual. */
  kind: 'auto' | 'manual'
}

