export type TransportMode = 'car' | 'train' | 'onSite'

export type FuelKey = 'essence' | 'diesel' | 'electrique'

/** UI-only slider bounds. Pricing and train fares come from API (`pricing-rules`, `transport/*`). */
export const VTF_TRANSPORT_DEFAULTS = {
  distanceMinKm: 50,
  distanceMaxKm: 1200,
  distanceStepKm: 25,
} as const
