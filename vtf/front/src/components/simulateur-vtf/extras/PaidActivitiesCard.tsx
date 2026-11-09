import LocalActivityRoundedIcon from "@mui/icons-material/LocalActivityRounded";
import PaymentsRoundedIcon from "@mui/icons-material/PaymentsRounded";
import { Box, Button, Typography } from "../../ui";
import { NoticeBox } from "../../shared/NoticeBox";

import type { PaidActivity } from "../../../data/vtfExtras";
import { formatEuro } from "../../../utils/currency";
import { useTranslation } from "../../../contexts/LanguageContext";
import { QuantityStepper } from "../../shared/QuantityStepper";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { VtfScrollArea } from "../../shared/VtfScrollArea";
import { ExtrasRegionGate } from "../shared/ExtrasRegionGate";
import {
  selectableRowPriceCenterSx,
  selectableRowPriceMetaSx,
  selectableRowShellSx,
  selectableRowStepperSpacerSx,
  selectableRowStepperWrapSx,
  selectableRowTitleWrapSx,
  selectableRowToggleSx,
  selectableRowTotalLabelSx,
  selectableRowTotalPriceSx,
  selectableRowTotalShellSx,
} from "../shared/selectableRowLayout";
import {
  ExtrasPaidActivitiesSkeleton,
  ExtrasPaidActivitiesTotalSkeleton,
} from "./ExtrasActivitiesListSkeleton";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";

type Props = {
  region: string | null;
  paidList: PaidActivity[];
  paidQtyById: Record<string, number>;
  familyAdults: number;
  familyChildren: number;
  onToggle: (id: string) => void;
  onDec: (id: string) => void;
  onInc: (id: string) => void;
  paidTotal: number;
  isLoading?: boolean;
  loadError?: boolean;
  onRetry?: () => void;
};

export function PaidActivitiesCard({
  region,
  paidList,
  paidQtyById,
  familyAdults,
  familyChildren,
  onToggle,
  onDec,
  onInc,
  paidTotal,
  isLoading,
  loadError,
  onRetry,
}: Props) {
  const { t } = useTranslation();
  const te = (k: string) => t(`simulateur.extras.${k}`);
  const adultWord = familyAdults > 1 ? te("adultPlural") : te("adultSingular");
  const childWord =
    familyChildren > 1 ? te("childPlural") : te("childSingular");

  const hasSelection = Object.values(paidQtyById).some((q) => q > 0);

  return (
    <VtfGlassCard
      title={te("paidTitle")}
      subtitle={te("paidSubtitle")}
      headingIcon={<LocalActivityRoundedIcon />}
      headingAccent="orange"
    >
      {!region ? (
        <ExtrasRegionGate message={te("paidSelectVillageFirst")} />
      ) : (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25 }}>
          {!(isLoading || loadError) ? (
            <NoticeBox tone="orange" dense>
              {te("paidDisclaimer")}
            </NoticeBox>
          ) : null}

          {isLoading ? (
            <Box>
              <ExtrasPaidActivitiesSkeleton rows={5} />
            </Box>
          ) : loadError ? (
            <VtfErrorAlert
              title={te("activitiesLoadErrorTitle")}
              message={te("activitiesLoadError")}
              onRetry={onRetry}
              retryLabel={t("simulateur.family.retry")}
              sx={{ mt: 2 }}
            />
          ) : (
            <VtfScrollArea maxHeight={{ xs: 340, sm: 400 }}>
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1, pr: 1.5 }}>
                {paidList.length ? (
                  paidList.map((a) => {
                    const qty = paidQtyById[a.id] ?? 0;
                    const checked = qty > 0;
                    const unit =
                      Math.max(0, a.ad) * familyAdults +
                      Math.max(0, a.enf) * familyChildren;
                    const lineTotal = unit * Math.max(qty, 1);

                    return (
                      <Box
                        key={a.id}
                        sx={{
                          ...selectableRowShellSx,
                          px: { xs: 1.25, sm: 1.5 },
                          py: 1.15,
                          minHeight: checked
                            ? { xs: 80, sm: 64 }
                            : { xs: 64, sm: 58 },
                          borderRadius: "16px",
                          border: "1px solid",
                          borderColor: checked
                            ? "rgba(var(--vtf-orange-rgb), 0.35)"
                            : "rgba(15, 23, 42, 0.07)",
                          bgcolor: checked
                            ? "rgba(var(--vtf-orange-rgb), 0.07)"
                            : "rgba(255, 255, 255, 0.45)",
                          boxShadow: checked
                            ? "0 10px 24px rgba(242, 166, 128, 0.14)"
                            : "0 4px 14px rgba(2, 8, 23, 0.04)",
                          transition:
                            "border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease",
                        }}
                      >
                        <Button
                          vtfVariant="toggle"
                          toggleTone="teal"
                          toggleChecked={checked}
                          onClick={() => onToggle(a.id)}
                          sx={selectableRowToggleSx}
                        >
                          {checked ? "✓" : ""}
                        </Button>

                        <Box sx={selectableRowTitleWrapSx}>
                          <Typography
                            sx={{
                              fontSize: 'var(--vtf-font-sm)',
                              fontWeight: 900,
                              color: checked
                                ? "var(--vtf-orange)"
                                : "var(--vtf-navy)",
                              lineHeight: 1.25,
                            }}
                          >
                            {a.type} {a.nom}
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
                            {formatEuro(a.ad, { compact: true })} /{adultWord} ·{" "}
                            {formatEuro(a.enf, { compact: true })} /{childWord}
                          </Typography>
                        </Box>

                        <Box sx={selectableRowPriceCenterSx}>
                          <Typography
                            sx={{
                              fontSize: 'var(--vtf-font-md)',
                              fontWeight: 980,
                              color: checked
                                ? "rgba(185, 28, 28, 0.95)"
                                : "rgba(0, 68, 90, 0.82)",
                              lineHeight: 1,
                              letterSpacing: "-0.02em",
                            }}
                          >
                            {formatEuro(checked && qty > 0 ? lineTotal : unit)}
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
                            {checked && qty > 1
                              ? `${formatEuro(unit, { compact: true })} × ${qty}`
                              : `${formatEuro(unit, { compact: true })} /${te("familyOuting")}`}
                          </Typography>
                        </Box>

                        {checked ? (
                          <Box sx={selectableRowStepperWrapSx}>
                            <QuantityStepper
                              value={qty}
                              counterSize="sm"
                              onDec={() => onDec(a.id)}
                              onInc={() => onInc(a.id)}
                              decAriaLabel={t("simulateur.resto.decAria").replace(
                                "{{label}}",
                                `${a.type} ${a.nom}`.trim(),
                              )}
                              incAriaLabel={t("simulateur.resto.incAria").replace(
                                "{{label}}",
                                `${a.type} ${a.nom}`.trim(),
                              )}
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
                                {qty}×
                              </Typography>
                            </QuantityStepper>
                          </Box>
                        ) : (
                          <Box sx={selectableRowStepperSpacerSx} />
                        )}
                      </Box>
                    );
                  })
                ) : (
                  <Box
                    sx={{
                      p: 1.75,
                      borderRadius: "14px",
                      bgcolor: "rgba(15,23,42,0.03)",
                      border: "1px dashed rgba(15,23,42,0.12)",
                      textAlign: "center",
                    }}
                  >
                    <Typography
                      sx={{
                        fontSize: 'var(--vtf-font-sm)',
                        fontWeight: 800,
                        color: "var(--vtf-navy)",
                        opacity: 0.75,
                      }}
                    >
                      {te("paidNone")}
                    </Typography>
                  </Box>
                )}
              </Box>
            </VtfScrollArea>
          )}
          {isLoading ? (
            <ExtrasPaidActivitiesTotalSkeleton />
          ) : hasSelection && !loadError ? (
            <Box
              sx={{
                ...selectableRowTotalShellSx,
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
                  {te("totalProviders")}
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
                  {formatEuro(paidTotal)}
                </Typography>
              </Box>
            </Box>
          ) : null}
        </Box>
      )}
    </VtfGlassCard>
  );
}
