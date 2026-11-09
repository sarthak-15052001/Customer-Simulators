/** Libellés adulte/enfant singulier/pluriel (clés i18n déjà résolues). */
export function familyAdultChildLabels(
  tr: (key: string) => string,
  adults: number,
  children: number,
): { adultWord: string; childWord: string } {
  return {
    adultWord: adults > 1 ? tr("adultPlural") : tr("adultSingular"),
    childWord: children > 1 ? tr("childPlural") : tr("childSingular"),
  };
}
