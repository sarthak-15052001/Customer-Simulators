export type RestoMealId = string

export type RestoMeal = {
  id: RestoMealId
  label: string
  /** Prix unitaire par adulte (€/repas). */
  priceAdult: number
  /** Prix unitaire par enfant (€/repas). */
  priceChild: number
}
