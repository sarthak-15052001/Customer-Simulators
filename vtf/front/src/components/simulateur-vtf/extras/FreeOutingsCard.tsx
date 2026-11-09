import EventAvailableRoundedIcon from "@mui/icons-material/EventAvailableRounded";
import ParkRoundedIcon from "@mui/icons-material/ParkRounded";
import { Box, Button, Typography } from "../../ui";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";

import type { FreeActivity } from "../../../data/vtfExtras";
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
import { ExtrasFreeActivitiesSkeleton } from "./ExtrasActivitiesListSkeleton";

type Props = {
  region: string | null;
  freeList: FreeActivity[];
  freeQtyById: Record<string, number>;
  onToggle: (id: string) => void;
  onDec: (id: string) => void;
  onInc: (id: string) => void;
  freePlanned: number;
  isLoading?: boolean;
  loadError?: boolean;
  onRetry?: () => void;
};

export function FreeOutingsCard({
  region,
  freeList,
  freeQtyById,
  onToggle,
  onDec,
  onInc,
  freePlanned,
  isLoading,
  loadError,
  onRetry,
}: Props) {
  const { t } = useTranslation();
  const te = (k: string) => t(`simulateur.extras.${k}`);

  return (
    <VtfGlassCard
      title={te("freeTitle")}
      subtitle={te("freeSubtitle")}
      headingIcon={<ParkRoundedIcon />}
      headingAccent="teal"
    >
      {!region ? (
        <ExtrasRegionGate message={te("paidSelectVillageFirst")} />
      ) : isLoading ? (
        <Box>
          <ExtrasFreeActivitiesSkeleton rows={5} />
        </Box>
      ) : loadError ? (
        <VtfErrorAlert
          title={te("activitiesLoadErrorTitle")}
          message={te("activitiesLoadError")}
          onRetry={onRetry}
          retryLabel={t("simulateur.family.retry")}
          sx={{ mt: 1 }}
        />
      ) : (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
          <VtfScrollArea maxHeight={{ xs: 320, sm: 380 }}>
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 1, pr: 1.5 }}
            >
              {freeList.map((a) => {
                const qty = freeQtyById[a.id] ?? 0;
                const checked = qty > 0;
                return (
                  <Box
                    key={a.id}
                    sx={{
                      ...selectableRowShellSx,
                      px: { xs: 1.25, sm: 1.5 },
                      py: 1.15,
                      minHeight: checked
                        ? { xs: 72, sm: 56 }
                        : { xs: 56, sm: 52 },
                      borderRadius: "16px",
                      border: "1px solid",
                      borderColor: checked
                        ? "rgba(var(--vtf-teal-rgb), 0.28)"
                        : "rgba(15, 23, 42, 0.07)",
                      bgcolor: checked
                        ? "rgba(var(--vtf-teal-rgb), 0.06)"
                        : "rgba(255, 255, 255, 0.45)",
                      boxShadow: checked
                        ? "0 10px 24px rgba(0, 168, 181, 0.10)"
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
                          fontSize: "var(--vtf-font-sm)",
                          fontWeight: 900,
                          color: checked
                            ? "var(--vtf-teal)"
                            : "var(--vtf-navy)",
                          lineHeight: 1.25,
                        }}
                      >
                        {a.type} {a.nom}
                      </Typography>
                    </Box>

                    <Box sx={selectableRowPriceCenterSx}>
                      <Typography
                        sx={{
                          fontSize: "var(--vtf-font-md)",
                          fontWeight: 980,
                          color: "#047857",
                          lineHeight: 1,
                          letterSpacing: "-0.02em",
                        }}
                      >
                        {formatEuro(0)}
                      </Typography>
                      <Typography
                        sx={{
                          fontSize: "var(--vtf-font-xs)",
                          fontWeight: 850,
                          color: "rgba(4, 120, 87, 0.72)",
                          mt: 0.25,
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          ...selectableRowPriceMetaSx,
                        }}
                      >
                        {te("freePill")}
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
                              fontSize: "var(--vtf-font-sm)",
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
              })}
            </Box>
          </VtfScrollArea>

          {!freeList.length && (
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
                  fontSize: "var(--vtf-font-sm)",
                  fontWeight: 800,
                  color: "var(--vtf-navy)",
                  opacity: 0.75,
                }}
              >
                {te("freeNone")}
              </Typography>
            </Box>
          )}

          {freePlanned > 0 && (
            <Box
              sx={{
                ...selectableRowTotalShellSx,
                mt: 0.5,
                px: 1.75,
                py: 1.35,
                minHeight: 48,
                borderRadius: "16px",
                bgcolor: "rgba(16, 185, 129, 0.08)",
                border: "1px solid rgba(16, 185, 129, 0.20)",
              }}
            >
              <Box sx={selectableRowTotalLabelSx}>
                <EventAvailableRoundedIcon
                  sx={{
                    fontSize: "var(--vtf-font-lg)",
                    color: "#047857",
                    flexShrink: 0,
                  }}
                />
                <Typography
                  sx={{
                    fontSize: "var(--vtf-font-sm)",
                    fontWeight: 900,
                    color: "var(--vtf-navy)",
                    lineHeight: 1.3,
                  }}
                >
                  {te("outingsFreeLine")
                    .replace("{{count}}", String(freePlanned))
                    .replace(
                      "{{suffix}}",
                      freePlanned > 1 ? te("pluralS") : "",
                    )}
                </Typography>
              </Box>

              <Box sx={selectableRowTotalPriceSx}>
                <Typography
                  sx={{
                    fontSize: "var(--vtf-font-md)",
                    fontWeight: 980,
                    color: "#047857",
                    letterSpacing: "-0.02em",
                  }}
                >
                  {formatEuro(0)}
                </Typography>
                <Typography
                  sx={{
                    fontSize: "var(--vtf-font-sm)",
                    fontWeight: 850,
                    color: "rgba(4, 120, 87, 0.8)",
                    mt: 0.2,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    ...selectableRowPriceMetaSx,
                  }}
                >
                  {te("freePill")}
                </Typography>
              </Box>
            </Box>
          )}
        </Box>
      )}
    </VtfGlassCard>
  );
}
