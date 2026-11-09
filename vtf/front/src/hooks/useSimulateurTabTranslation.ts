import * as React from "react";
import { useTranslation } from "../contexts/LanguageContext";

export type SimulateurTabLocaleScope =
  | "resto"
  | "transport"
  | "promos"
  | "planning"
  | "details";

/** Traductions des onglets du simulateur : `simulateur.{scope}.{key}`
 * (prend en charge les clés imbriquées, par ex. `hero.vtfTitle`).
 */
export function useSimulateurTabTranslation(scope: SimulateurTabLocaleScope) {
  const { t } = useTranslation();

  return React.useCallback(
    (key: string) => t(`simulateur.${scope}.${key}`),
    [t, scope],
  );
}
