import LocalOfferRoundedIcon from "@mui/icons-material/LocalOfferRounded";
import AccountBalanceWalletRoundedIcon from "@mui/icons-material/AccountBalanceWalletRounded";
import PaidRoundedIcon from "@mui/icons-material/PaidRounded";
import AutoAwesomeRoundedIcon from "@mui/icons-material/AutoAwesomeRounded";
import { Box } from "../../ui";

import type { PromoChoice } from "../../../data/vtfPromos";
import { DiscountsRecapPanel } from "./DiscountsRecapPanel";
import { FamilyQuotientSection } from "./FamilyQuotientSection";
import { StayPromotionSection } from "./StayPromotionSection";
import { TotalDiscountCard } from "./TotalDiscountCard";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import type { PromosDiscountSummaryState } from "./promosDiscountState";

export type PromosTabViewProps = {
  tp: (k: string) => string;
  appliedLines: Array<{ icon: string; label: string; note?: string }>;
  discountSummaryState: PromosDiscountSummaryState;
  totalStayDiscountPct: number | null;
  discountedBudgetLabel: string | null;
  qfSelection: "r1" | "r2" | "plein" | "empty";
  qfValueLabel: string;
  isQfPeriodValid?: boolean;
  qfVal?: number | null;
  onUpdateQf?: (val: number | null) => void;
  promoCatalog: PromoChoice[];
  availablePromos: PromoChoice[];
  hasStayDates?: boolean;
  hasVillage?: boolean;
  isCatalogLoading?: boolean;
  isCatalogError?: boolean;
  isAvailableLoading?: boolean;
  isAvailableError?: boolean;
  onRetryCatalog?: () => void;
  onRetryAvailable?: () => void;
  selectedPromoKey: PromoChoice["key"];
  onSelectPromo: (choice: PromoChoice) => void;
  onSelectNone: () => void;
};

export function PromosTabView({
  tp,
  appliedLines,
  discountSummaryState,
  totalStayDiscountPct,
  discountedBudgetLabel,
  qfSelection,
  qfValueLabel,
  isQfPeriodValid = true,
  qfVal,
  onUpdateQf,
  promoCatalog,
  availablePromos,
  hasStayDates = false,
  hasVillage = false,
  isCatalogLoading = false,
  isCatalogError = false,
  isAvailableLoading = false,
  isAvailableError = false,
  onRetryCatalog,
  onRetryAvailable,
  selectedPromoKey,
  onSelectPromo,
  onSelectNone,
}: PromosTabViewProps) {
  return (
    <Box className="vtf-tab-stack grid gap-4">
      <VtfGlassCard
        title={tp("title")}
        subtitle={tp("subtitle")}
        headingIcon={<LocalOfferRoundedIcon />}
        headingAccent="orange"
      >
        <DiscountsRecapPanel
          tp={tp}
          lines={appliedLines}
          discountSummaryState={discountSummaryState}
        />
      </VtfGlassCard>

      <VtfGlassCard
        title={tp("qfTitle")}
        headingIcon={<AccountBalanceWalletRoundedIcon />}
        headingAccent="teal"
      >
        <FamilyQuotientSection
          tp={tp}
          qfSelection={qfSelection}
          currentValueLabel={qfValueLabel}
          isPeriodValid={isQfPeriodValid}
          qfVal={qfVal}
          onUpdateQf={onUpdateQf}
        />
      </VtfGlassCard>

      <VtfGlassCard
        title={tp("sejourPromoTitle")}
        headingIcon={<AutoAwesomeRoundedIcon />}
        headingAccent="orange"
      >
        <StayPromotionSection
          tp={tp}
          catalog={promoCatalog}
          available={availablePromos}
          hasStayDates={hasStayDates}
          hasVillage={hasVillage}
          isCatalogLoading={isCatalogLoading}
          isCatalogError={isCatalogError}
          isAvailableLoading={isAvailableLoading}
          isAvailableError={isAvailableError}
          onRetryCatalog={onRetryCatalog}
          onRetryAvailable={onRetryAvailable}
          selectedKey={selectedPromoKey}
          onSelectNone={onSelectNone}
          onSelectPromo={onSelectPromo}
        />
      </VtfGlassCard>

      <VtfGlassCard
        title={tp("totalAppliedTitle")}
        headingIcon={<PaidRoundedIcon />}
        headingAccent="teal"
      >
        <TotalDiscountCard
          tp={tp}
          state={discountSummaryState}
          discountPct={totalStayDiscountPct}
          discountedBudgetLabel={discountedBudgetLabel}
        />
      </VtfGlassCard>
    </Box>
  );
}
