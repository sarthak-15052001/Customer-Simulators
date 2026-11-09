import RestaurantRoundedIcon from "@mui/icons-material/RestaurantRounded";
import { Box, Button, Skeleton, Typography } from "../../ui";
import { NoticeBox } from "../../shared/NoticeBox";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { formatEuro } from "../../../utils/currency";
import type { VtfFormule } from "../../../data/vtfStay";
import {
  selectableRowPriceCenterSx,
  selectableRowPriceMetaSx,
  selectableRowShellSx,
  selectableRowStepperSpacerSx,
  selectableRowTitleWrapSx,
  selectableRowToggleSx,
} from "../shared/selectableRowLayout";

export type RestoVtfFormuleOption = {
  formule: VtfFormule;
  label: string;
  sub: string;
  total: number | null;
  selected?: boolean;
  loading: boolean;
  error: boolean;
};

type Props = {
  tr: (k: string) => string;
  options: RestoVtfFormuleOption[];
  onSelect: (formule: VtfFormule) => void;
};

export function RestoVtfFormuleSection({ tr, options, onSelect }: Props) {
  if (!options.length) return null;

  return (
    <VtfGlassCard
      title={tr("vtfMealsTitle")}
      subtitle={tr("vtfMealsSubtitle")}
      headingIcon={<RestaurantRoundedIcon />}
      headingAccent="teal"
    >
      <NoticeBox tone="teal" dense>
        {tr("vtfMealsHint")}
      </NoticeBox>

      <Box sx={{ mt: 1.25, display: "flex", flexDirection: "column", gap: 1 }}>
        {options.map((o) => {
          const disabled = o.loading || o.error;
          const active = Boolean(o.selected);
          return (
            <Box
              key={o.formule}
              onClick={() => {
                if (!disabled) onSelect(o.formule);
              }}
              sx={{
                ...selectableRowShellSx,
                px: { xs: 1.25, sm: 1.5 },
                py: 1.15,
                minHeight: { xs: 64, sm: 58 },
                borderRadius: "16px",
                border: "1px solid",
                borderColor: active
                  ? "rgba(var(--vtf-teal-rgb), 0.45)"
                  : "rgba(15, 23, 42, 0.07)",
                bgcolor: active
                  ? "rgba(var(--vtf-teal-rgb), 0.07)"
                  : "rgba(255, 255, 255, 0.45)",
                boxShadow: active
                  ? "0 10px 24px rgba(45, 212, 191, 0.14)"
                  : "0 4px 14px rgba(2, 8, 23, 0.04)",
                cursor: disabled ? "default" : "pointer",
                opacity: disabled && !active ? 0.7 : 1,
                transition:
                  "border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease",
              }}
            >
              <Button
                vtfVariant="toggle"
                toggleTone="teal"
                toggleChecked={active}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(o.formule);
                }}
                sx={selectableRowToggleSx}
              >
                {active ? "✓" : ""}
              </Button>

              <Box sx={selectableRowTitleWrapSx}>
                <Typography
                  sx={{
                    fontSize: "var(--vtf-font-sm)",
                    fontWeight: 900,
                    color: "var(--vtf-navy)",
                    lineHeight: 1.25,
                  }}
                >
                  {o.label}
                </Typography>
                {o.sub ? (
                  <Typography
                    sx={{
                      fontSize: "var(--vtf-font-sm)",
                      fontWeight: 700,
                      color: "rgba(0, 68, 90, 0.58)",
                      mt: 0.35,
                      lineHeight: 1.35,
                    }}
                  >
                    {o.sub}
                  </Typography>
                ) : null}
              </Box>

              <Box sx={selectableRowPriceCenterSx}>
                {o.loading ? (
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-end",
                      gap: 0.5,
                      ...selectableRowPriceMetaSx,
                    }}
                  >
                    <Skeleton width={68} height={20} sx={{ borderRadius: 1 }} />
                    <Skeleton width={80} height={12} sx={{ borderRadius: 0.5 }} />
                  </Box>
                ) : o.error || o.total == null ? (
                  <Typography
                    sx={{
                      fontSize: "var(--vtf-font-xs)",
                      fontWeight: 800,
                      color: "rgba(0, 68, 90, 0.65)",
                      fontStyle: "italic",
                      ...selectableRowPriceMetaSx,
                    }}
                  >
                    {tr("vtfMealsError")}
                  </Typography>
                ) : (
                  <>
                    <Typography
                      sx={{
                        fontSize: "var(--vtf-font-md)",
                        fontWeight: 980,
                        color: "rgba(0, 68, 90, 0.82)",
                        lineHeight: 1,
                        letterSpacing: "-0.02em",
                      }}
                    >
                      {formatEuro(o.total)}
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: "var(--vtf-font-xs)",
                        fontWeight: 850,
                        color: "rgba(0, 68, 90, 0.52)",
                        mt: 0.25,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        ...selectableRowPriceMetaSx,
                      }}
                    >
                      {tr("vtfMealsTotal")}
                    </Typography>
                  </>
                )}
              </Box>

              <Box sx={selectableRowStepperSpacerSx} />
            </Box>
          );
        })}
      </Box>
    </VtfGlassCard>
  );
}
