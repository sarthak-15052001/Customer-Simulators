import { Box } from "../../ui";
import PeopleAltRoundedIcon from "@mui/icons-material/PeopleAltRounded";
import HolidayVillageRoundedIcon from "@mui/icons-material/HolidayVillageRounded";
import RestaurantRoundedIcon from "@mui/icons-material/RestaurantRounded";
import PaymentsRoundedIcon from "@mui/icons-material/PaymentsRounded";
import { RecapSummaryMetrics } from "./RecapSummaryMetrics";
import { RecapSummaryTotalCard } from "./RecapSummaryTotalCard";
import { formatEuro } from "./_format";

import type { FamilyState } from "../../../types/familyTab";
import type { SejourState } from "../../../types/stayTab";
import type { VtfVillage } from "../../../data/vtfStay";
import type { SejourEstimate } from "../../../utils/stayEstimate";
import { funnelSaisonKeyForRecap } from "../../../utils/extrasTab";
import { useTranslation } from "../../../contexts/LanguageContext";
import { formatDateRangeDDMMYYYY } from "../../../utils/date";
import { useFormules } from "../../../hooks/formules.hooks";
import { useSimulateurTabTranslation } from "../../../hooks/useSimulateurTabTranslation";
import { getFormuleLabelFromCatalog } from "../stay/StayFormulePicker.shared";
import { resolveStayIncludesText } from "../../../utils/stayEstimate";

export function RecapSummaryCard({
  family,
  sejour,
  village,
  estimate,
}: {
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
  estimate: SejourEstimate;
}) {
  const { t } = useTranslation();
  const td = useSimulateurTabTranslation("details");
  const trc = (k: string) => t(`simulateur.recap.${k}`);
  const { data: apiFormules } = useFormules();

  const dm = estimate.displayMetrics;
  const perPersonDayStr =
    dm != null && Number.isFinite(dm.perPersonPerDay)
      ? String(dm.perPersonPerDay)
      : "-";
  const perDayFamilyStr =
    dm != null && Number.isFinite(dm.perDayFamily)
      ? String(dm.perDayFamily)
      : "-";
  const nuitsShown = estimate.nuits;
  const saisonPillKey = funnelSaisonKeyForRecap(sejour, estimate.saisonKey);
  const saisonShown = t(`simulateur.recap.pillSeason.${saisonPillKey}`);
  const dateRangeLabel = formatDateRangeDDMMYYYY(
    sejour?.dateDebut,
    sejour?.dateFin,
  );

  const adultLabel = family.adultes > 1 ? trc("adultMany") : trc("adultOne");
  const childLabel =
    family.enfants.length > 1 ? trc("childMany") : trc("childOne");
  const nightLabel = nuitsShown > 1 ? trc("nightPlural") : trc("nightSingular");
  const formulaLabel = getFormuleLabelFromCatalog(sejour.formule, apiFormules);

  const formulaIncludesText = resolveStayIncludesText(
    sejour.formule,
    estimate.includes,
  );

  const perPersonDetail = [
    formatEuro(perPersonDayStr, {
      suffix: td("recapCard.perPersonPerDaySuffix"),
    }),
    formatEuro(perDayFamilyStr, {
      suffix: td("recapCard.perDayFamilySuffix"),
    }),
  ]
    .filter((line): line is string => line != null)
    .join(" · ");

  const childAgeItemLabel = (age: number, index: number) =>
    td("recapCard.summary.childAgeItem")
      .replace("{{index}}", String(index))
      .replace("{{age}}", String(age))
      .replace("{{years}}", td("stay.years"));

  const childrenAgesSublabel =
    family.enfants.length > 0
      ? `${td("recapCard.summary.childrenAges")}: ${family.enfants
          .map((e, i) => childAgeItemLabel(e.age, i + 1))
          .join(" · ")}`
      : undefined;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25 }}>
      <RecapSummaryMetrics
        items={[
          {
            variant: "family",
            label: td("recapCard.summary.family"),
            icon: <PeopleAltRoundedIcon />,
            value: `${family.adultes} ${adultLabel} · ${family.enfants.length} ${childLabel}`,
            sublabel: childrenAgesSublabel,
          },
          {
            variant: "stay",
            label: td("recapCard.summary.stay"),
            icon: <HolidayVillageRoundedIcon />,
            value: village?.nom || "-",
            sublabel: `${dateRangeLabel ? dateRangeLabel + " · " : ""}${nuitsShown} ${nightLabel} · ${saisonShown}`,
          },
          {
            variant: "formula",
            label: td("recapCard.summary.formula"),
            icon: <RestaurantRoundedIcon />,
            value: formulaLabel,
            sublabel: formulaIncludesText || undefined,
          },
          {
            variant: "budget",
            label: td("recapCard.summary.perPerson"),
            icon: <PaymentsRoundedIcon />,
            value: `${formatEuro(estimate.perPerson)} ${td("recapCard.summary.total")}`,
            sublabel: perPersonDetail || undefined,
          },
        ]}
      />
      <RecapSummaryTotalCard estimate={estimate} />
    </Box>
  );
}
