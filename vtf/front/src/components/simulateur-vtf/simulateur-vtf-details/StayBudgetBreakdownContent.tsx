import PeopleAltRoundedIcon from "@mui/icons-material/PeopleAltRounded";
import HolidayVillageRoundedIcon from "@mui/icons-material/HolidayVillageRounded";
import PaymentsRoundedIcon from "@mui/icons-material/PaymentsRounded";
import CheckCircleOutlineRoundedIcon from "@mui/icons-material/CheckCircleOutlineRounded";
import CardMembershipRoundedIcon from "@mui/icons-material/CardMembershipRounded";
import {
  RecapBreakdownDivider,
  RecapBreakdownRow,
  RecapBreakdownSection,
} from "./recapBreakdown.ui";
import { formatEuro, formatPercentInt } from "./_format";
import {
  childDiscountLabel,
  resolveStayDiscountPct,
  resolveStayPackageTotal,
} from "./fullRecapBreakdown";
import type { FamilyState } from "../../../types/familyTab";
import type { SejourEstimate } from "../../../utils/stayEstimate";
import { useTranslation } from "../../../contexts/LanguageContext";
import { useSimulateurTabTranslation } from "../../../hooks/useSimulateurTabTranslation";

/** Line-by-line VTF stay budget (lodging, children, discounts, membership). */
export function StayBudgetBreakdownContent({
  family,
  estimate,
}: {
  family: FamilyState;
  estimate: SejourEstimate;
}) {
  const { t } = useTranslation();
  const td = useSimulateurTabTranslation("details");
  const trc = (k: string) => t(`simulateur.recap.${k}`);

  const stayDiscountPct = resolveStayDiscountPct(estimate);
  const showChildrenSubtotal =
    estimate.totalChildren > 0 || estimate.childLines.length > 0;
  const stayPackageTotal =
    estimate.adhesion > 0 ? resolveStayPackageTotal(estimate) : null;
  const hasAdjustments =
    estimate.extrasLoc > 0 ||
    estimate.soloSupplement > 0 ||
    stayDiscountPct != null;

  return (
    <RecapBreakdownSection theme="budget" hideHeading>
      <RecapBreakdownRow
        leadingIcon={<PeopleAltRoundedIcon />}
        label={`${family.adultes} ${td("recapCard.details.adultsAt")} ${formatEuro(estimate.perAdultBase)}`}
        value={formatEuro(estimate.totalAdults)}
      />
      {estimate.childLines.map((c, i) => (
        <RecapBreakdownRow
          key={`${c.age}-${i}`}
          variant="child"
          indent
          label={td("recapCard.details.childLine")
            .replace("{{child}}", trc("childOne"))
            .replace("{{index}}", String(i + 1))
            .replace("{{age}}", String(c.age))
            .replace("{{years}}", td("stay.years"))}
          value={formatEuro(c.amount)}
          note={childDiscountLabel(c.discountFraction, td) ?? undefined}
        />
      ))}
      {showChildrenSubtotal && (
        <RecapBreakdownRow
          label={td("recapCard.details.childrenSubtotal")}
          value={formatEuro(estimate.totalChildren)}
        />
      )}
      {hasAdjustments && <RecapBreakdownDivider />}
      {estimate.extrasLoc > 0 && (
        <RecapBreakdownRow
          leadingIcon={<HolidayVillageRoundedIcon />}
          label={td("recapCard.details.extrasLocLine")}
          value={formatEuro(estimate.extrasLoc)}
        />
      )}
      {estimate.soloSupplement > 0 && (
        <RecapBreakdownRow
          label={td("stay.solo")}
          value={formatEuro(estimate.soloSupplement)}
        />
      )}
      {stayDiscountPct != null && (
        <RecapBreakdownRow
          variant="discount"
          leadingIcon={<CheckCircleOutlineRoundedIcon />}
          label={td("recapCard.details.stayDiscount").replace(
            "{{pct}}",
            formatPercentInt(stayDiscountPct),
          )}
          value={`−${formatPercentInt(stayDiscountPct)}%`}
        />
      )}
      <RecapBreakdownRow
        variant="subtotal"
        label={td("recapCard.details.stayLodgingSubtotal")}
        value={formatEuro(estimate.staySubtotal)}
        strong
      />
      {estimate.adhesion > 0 && (
        <>
          <RecapBreakdownDivider />
          <RecapBreakdownRow
            leadingIcon={<CardMembershipRoundedIcon />}
            label={td("stay.adhesion")}
            value={formatEuro(estimate.adhesion)}
          />
        </>
      )}
      {stayPackageTotal != null && stayPackageTotal > estimate.staySubtotal && (
        <RecapBreakdownRow
          variant="subtotal"
          leadingIcon={<PaymentsRoundedIcon />}
          label={td("recapCard.details.stayWithMembership")}
          value={formatEuro(stayPackageTotal)}
          strong
        />
      )}
    </RecapBreakdownSection>
  );
}
