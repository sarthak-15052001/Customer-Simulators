function promoRateAsNumber(rate: unknown): number {
  const n = typeof rate === "number" ? rate : Number(rate);
  return Number.isFinite(n) ? n : 0;
}

/** Match promo rate between catalog / available / state (tolerates string rates). */
export function promoRatesMatch(a: unknown, b: unknown): boolean {
  return (
    Math.round(promoRateAsNumber(a) * 100) ===
    Math.round(promoRateAsNumber(b) * 100)
  );
}
