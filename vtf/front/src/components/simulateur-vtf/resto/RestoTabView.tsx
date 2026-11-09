import PaymentsRoundedIcon from "@mui/icons-material/PaymentsRounded";
import RestaurantMenuRoundedIcon from "@mui/icons-material/RestaurantMenuRounded";
import { Box, Button, Typography } from "../../ui";
import { NoticeBox } from "../../shared/NoticeBox";

import type { RestoMealId } from "../../../data/vtfResto";
import { formatEuro } from "../../../utils/currency";
import { QuantityStepper } from "../../shared/QuantityStepper";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import {
  selectableRowPriceCenterSx,
  selectableRowPriceMetaSx,
  selectableRowShellSx,
  selectableRowStepperWrapSx,
  selectableRowTitleWrapRestoSx,
  selectableRowTotalActionSx,
  selectableRowTotalLabelSx,
  selectableRowTotalPriceSx,
  selectableRowTotalShellSx,
} from "../shared/selectableRowLayout";

import { useTranslation } from "../../../contexts/LanguageContext";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";
import { RestoMealsSkeleton } from "./RestoMealsSkeleton";
import {
  RestoVtfFormuleSection,
  type RestoVtfFormuleOption,
} from "./RestoVtfFormuleSection";
import type { VtfFormule } from "../../../data/vtfStay";

export type RestoMealRow = {
  id: RestoMealId;
  label: string;
  priceAdultRounded: number;
  priceChildRounded: number;
  unitFamilyRounded: number;
  qty: number;
  lineTotal: number;
};

type RestoTabViewProps = {
  tr: (k: string) => string;
  note: string;
  items: RestoMealRow[];
  adultWord: string;
  childWord: string;
  totalMeals: number;
  totalAmount: number;
  onDec: (id: RestoMealId) => void;
  onInc: (id: RestoMealId) => void;
  onReset: () => void;
  isLoading?: boolean;
  loadError?: boolean;
  onRetry?: () => void;
  vtfFormuleOptions?: RestoVtfFormuleOption[];
  onSelectVtfFormule?: (formule: VtfFormule) => void;
};

export function RestoTabView({
  tr,
  note,
  items,
  adultWord,
  childWord,
  totalMeals,
  totalAmount,
  onDec,
  onInc,
  onReset,
  isLoading = false,
  loadError = false,
  onRetry,
  vtfFormuleOptions,
  onSelectVtfFormule,
}: RestoTabViewProps) {
  const { t } = useTranslation();

  return (
    <Box className="vtf-tab-stack">
      <VtfGlassCard
        title={tr("title")}
        subtitle={tr("subtitle")}
        headingIcon={<RestaurantMenuRoundedIcon />}
        headingAccent="orange"
      >
        {!(isLoading || loadError) ? (
          <NoticeBox tone="navy" dense>
            {note}
          </NoticeBox>
        ) : null}

        <Box
          sx={{ mt: 1.25, display: "flex", flexDirection: "column", gap: 1 }}
        >
          {isLoading ? (
            <RestoMealsSkeleton />
          ) : loadError ? (
            <VtfErrorAlert
              title={tr("mealsLoadErrorTitle")}
              message={tr("mealsLoadError")}
              onRetry={onRetry}
              retryLabel={t("simulateur.family.retry")}
            />
          ) : (
            items.map((m) => {
              const active = m.qty > 0;
              const displayPrice = active ? m.lineTotal : m.unitFamilyRounded;

              return (
                <Box
                  key={m.id}
                  sx={{
                    ...selectableRowShellSx,
                    px: { xs: 1.25, sm: 1.5 },
                    py: 1.15,
                    minHeight: { xs: 72, sm: 64 },
                    borderRadius: "16px",
                    border: "1px solid",
                    borderColor: active
                      ? "rgba(var(--vtf-orange-rgb), 0.35)"
                      : "rgba(15, 23, 42, 0.07)",
                    bgcolor: active
                      ? "rgba(var(--vtf-orange-rgb), 0.07)"
                      : "rgba(255, 255, 255, 0.45)",
                    boxShadow: active
                      ? "0 10px 24px rgba(242, 166, 128, 0.14)"
                      : "0 4px 14px rgba(2, 8, 23, 0.04)",
                    transition:
                      "border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease",
                  }}
                >
                  <Box sx={selectableRowTitleWrapRestoSx}>
                    <Typography
                      sx={{
                        fontSize: 'var(--vtf-font-sm)',
                        fontWeight: 900,
                        color: active ? "var(--vtf-orange)" : "var(--vtf-navy)",
                        lineHeight: 1.25,
                      }}
                    >
                      {m.label}
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: 'var(--vtf-font-sm)',
                        fontWeight: 700,
                        color: "rgba(0, 68, 90, 0.58)",
                        mt: 0.35,
                        lineHeight: 1.35,
                      }}
                    >
                      {formatEuro(m.priceAdultRounded, { compact: true })} /{adultWord}{" "}
                      · {formatEuro(m.priceChildRounded, { compact: true })} /{childWord}
                    </Typography>
                  </Box>

                  <Box sx={selectableRowPriceCenterSx}>
                    <Typography
                      sx={{
                        fontSize: 'var(--vtf-font-md)',
                        fontWeight: 980,
                        color: active
                          ? "rgba(185, 28, 28, 0.95)"
                          : "rgba(0, 68, 90, 0.82)",
                        lineHeight: 1,
                        letterSpacing: "-0.02em",
                      }}
                    >
                      {formatEuro(displayPrice)}
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: 'var(--vtf-font-xs)',
                        fontWeight: 850,
                        color: "rgba(0, 68, 90, 0.52)",
                        mt: 0.25,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        ...selectableRowPriceMetaSx,
                      }}
                    >
                      {active && m.qty > 1
                        ? `${formatEuro(m.unitFamilyRounded, { compact: true })} × ${m.qty}`
                        : `${formatEuro(m.unitFamilyRounded, { compact: true })} /${tr("familyMeal")}`}
                    </Typography>
                  </Box>

                  <Box sx={selectableRowStepperWrapSx}>
                    <QuantityStepper
                      value={m.qty}
                      counterSize="sm"
                      onDec={() => onDec(m.id)}
                      onInc={() => onInc(m.id)}
                      decAriaLabel={tr("decAria").replace("{{label}}", m.label)}
                      incAriaLabel={tr("incAria").replace("{{label}}", m.label)}
                      decButtonSx={{
                        borderRadius: 2,
                        border: "1px solid rgba(15,23,42,0.10)",
                      }}
                      incButtonSx={{ borderRadius: 2 }}
                    >
                      <Typography
                        sx={{
                          minWidth: 36,
                          textAlign: "center",
                          fontSize: 'var(--vtf-font-sm)',
                          fontWeight: 950,
                          color: "var(--vtf-navy)",
                        }}
                      >
                        {m.qty}×
                      </Typography>
                    </QuantityStepper>
                  </Box>
                </Box>
              );
            })
          )}

          {totalMeals > 0 && (
            <Box
              sx={{
                ...selectableRowTotalShellSx,
                mt: 0.5,
                px: 1.75,
                py: 1.35,
                minHeight: 48,
                borderRadius: "16px",
                bgcolor: "rgba(var(--vtf-orange-rgb), 0.10)",
                border: "1px solid rgba(var(--vtf-orange-rgb), 0.22)",
              }}
            >
              <Box sx={selectableRowTotalLabelSx}>
                <PaymentsRoundedIcon
                  sx={{
                    fontSize: 'var(--vtf-font-lg)',
                    color: "var(--vtf-orange)",
                    flexShrink: 0,
                  }}
                />
                <Typography
                  sx={{
                    fontSize: 'var(--vtf-font-sm)',
                    fontWeight: 900,
                    color: "var(--vtf-navy)",
                    lineHeight: 1.3,
                  }}
                >
                  {totalMeals}{" "}
                  {tr(totalMeals > 1 ? "mealPlural" : "mealSingular")}
                </Typography>
              </Box>

              <Box sx={selectableRowTotalPriceSx}>
                <Typography
                  sx={{
                    fontSize: 'var(--vtf-font-md)',
                    fontWeight: 980,
                    color: "rgba(185, 28, 28, 0.95)",
                    letterSpacing: "-0.02em",
                  }}
                >
                  {formatEuro(totalAmount)}
                </Typography>
              </Box>

              <Box sx={selectableRowTotalActionSx}>
                <Button
                  variant="text"
                  onClick={onReset}
                  sx={{
                    fontSize: 'var(--vtf-font-sm)',
                    fontWeight: 900,
                    color: "var(--vtf-orange)",
                    textTransform: "none",
                    minWidth: 0,
                    px: 1,
                  }}
                >
                  {tr("reset")}
                </Button>
              </Box>
            </Box>
          )}
        </Box>
      </VtfGlassCard>

      {vtfFormuleOptions?.length && onSelectVtfFormule ? (
        <RestoVtfFormuleSection
          tr={tr}
          options={vtfFormuleOptions}
          onSelect={onSelectVtfFormule}
        />
      ) : null}
    </Box>
  );
}
