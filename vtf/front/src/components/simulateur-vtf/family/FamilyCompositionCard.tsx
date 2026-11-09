import { Box, Button, Pill, Skeleton, Typography } from "../../ui";
/**
 * Carte Composition Familiale
 * Gère le nombre d'adultes, d'enfants et affiche les remises enfants basées sur l'API.
 */
import PeopleAltRoundedIcon from "@mui/icons-material/PeopleAltRounded";
import AddCircleRoundedIcon from "@mui/icons-material/AddCircleRounded";
import LightbulbRoundedIcon from "@mui/icons-material/LightbulbRounded";
import type {
  AgeOption,
  FamilyState,
  FamilyTabTranslations,
} from "../../../types/familyTab";
import type { ChildDiscountsRow } from "../../../utils/familyTab";
import { discountFractionForChildAge } from "../../../utils/familyTab";
import { VtfSelect } from "../../ui/Select";
import { NoticeBox } from "../../shared/NoticeBox";
import { QuantityStepper } from "../../shared/QuantityStepper";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { VtfSectionHeading } from "../../shared/VtfSectionHeading";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";
import { useTranslation } from "../../../contexts/LanguageContext";

type Props = {
  value: FamilyState;
  tf: FamilyTabTranslations;
  ageOptions: AgeOption[];
  onSetAdultes: (next: number) => void;
  onSetEnfantAge: (idx: number, age: number) => void;
  onAddEnfant: () => void;
  onRemoveEnfant: (idx: number) => void;
  limits: {
    adultesMin: number;
    adultesMax: number;
    enfantsMax: number;
  };
  /** Provient de `GET /pricing-rules` — pilote les badges de remise enfants. */
  childDiscounts: ChildDiscountsRow | null;
  childDiscountsLoading: boolean;
  childDiscountsError?: boolean;
  onRetry?: () => void;
  /** L'étape famille n'a pas de village : utilise `false` (correspond à l'estimation sans bébé club). */
  bebeClubForDiscounts?: boolean;
};

export function FamilyCompositionCard({
  value,
  tf,
  ageOptions,
  onSetAdultes,
  onSetEnfantAge,
  onAddEnfant,
  onRemoveEnfant,
  limits,
  childDiscounts,
  childDiscountsLoading,
  childDiscountsError = false,
  onRetry,
  bebeClubForDiscounts = false,
}: Props) {
  const { t } = useTranslation();
  const decAria = (label: string) =>
    t("simulateur.resto.decAria").replace("{{label}}", label);
  const incAria = (label: string) =>
    t("simulateur.resto.incAria").replace("{{label}}", label);

  const discountChipLabel = (fraction: number) =>
    fraction >= 1 ? tf("discountFree") : `-${Math.round(fraction * 100)}%`;

  const fractionForAge = (age: number): number | null => {
    if (childDiscountsLoading || !childDiscounts) return null;
    return discountFractionForChildAge(
      age,
      childDiscounts,
      bebeClubForDiscounts,
    );
  };
  return (
    <VtfGlassCard>
      <VtfSectionHeading
        accent="orange"
        icon={<PeopleAltRoundedIcon />}
        title={tf("cardTitle")}
        rightSlot={
          <Pill
            label={`${value.adultes} ${tf("abbrAdults")} · ${value.enfants.length} ${tf("abbrChildren")}`}
            vtfTone="softNavy"
            sx={{
              fontSize: "var(--vtf-font-sm)",
              fontWeight: 700,
              height: 22,
              px: 1,
            }}
          />
        }
      />

      <Box className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Compteur Adultes */}
        <Box
          sx={{
            display: { xs: "flex", sm: "block" },
            alignItems: { xs: "center", sm: "stretch" },
            justifyContent: { xs: "space-between", sm: "flex-start" },
            gap: { xs: 1, sm: 0 },
          }}
        >
          <Typography
            sx={{
              fontSize: "var(--vtf-font-sm)",
              fontWeight: 800,
              color: "var(--vtf-navy)",
              mb: { xs: 0, sm: 1 },
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            {tf("adults")}
          </Typography>
          <QuantityStepper
            value={value.adultes}
            counterSize="md"
            plusTone="navy"
            onDec={() => onSetAdultes(value.adultes - 1)}
            onInc={() => onSetAdultes(value.adultes + 1)}
            decDisabled={value.adultes <= limits.adultesMin}
            incDisabled={value.adultes >= limits.adultesMax}
            decAriaLabel={decAria(tf("adults"))}
            incAriaLabel={incAria(tf("adults"))}
            containerClassName="bg-vtf-cream/50 p-1 rounded-lg w-fit border border-vtf-navy/5"
            containerSx={{ gap: 1.5 }}
          >
            <Typography
              sx={{
                fontSize: "var(--vtf-font-md)",
                fontWeight: 900,
                color: "var(--vtf-navy)",
                minWidth: 14,
                textAlign: "center",
              }}
            >
              {value.adultes}
            </Typography>
          </QuantityStepper>
        </Box>

        {/* Section Enfants */}
        <Box>
          <Box className="mb-2 flex flex-nowrap items-center justify-between gap-1.5 min-w-0">
            <Box className="flex items-center gap-2 min-w-0 shrink">
              <Typography
                sx={{
                  fontSize: "var(--vtf-font-sm)",
                  fontWeight: 900,
                  color: "var(--vtf-navy)",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                }}
              >
                {tf("children")}
              </Typography>
              <Pill
                size="small"
                label={String(value.enfants.length)}
                vtfTone="softNavy"
                sx={{
                  fontSize: "var(--vtf-font-sm)",
                  fontWeight: 950,
                  height: "auto",
                  py: 0.2,
                  bgcolor: "rgba(15,23,42,0.04)",
                  color: "rgba(0, 68, 90, 0.92)",
                  border: "1px solid rgba(15,23,42,0.08)",
                }}
              />
            </Box>

            <Button
              variant="contained"
              size="small"
              vtfVariant="navyFillPill"
              onClick={onAddEnfant}
              disabled={value.enfants.length >= limits.enfantsMax}
              aria-label={tf("addChild")}
              startIcon={
                <AddCircleRoundedIcon sx={{ fontSize: "var(--vtf-font-md)" }} />
              }
              sx={{
                flexShrink: 0,
                minWidth: { xs: 36, sm: "auto" },
                px: { xs: 1, sm: 1.75 },
                fontSize: { xs: "var(--vtf-font-xs)", sm: "var(--vtf-font-sm)" },
                "& .MuiButton-startIcon": { mr: { xs: 0, sm: 0.75 } },
              }}
            >
              <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
                {tf("addChild")}
              </Box>
            </Button>
          </Box>

          <Box
            className="rounded-xl border border-slate-200/70 bg-slate-50/70 p-2 flex flex-col gap-2"
            sx={{
              minHeight: value.enfants.length === 0 ? { xs: 64, sm: 82 } : "auto",
              justifyContent:
                value.enfants.length === 0 ? "center" : "flex-start",
            }}
          >
            {value.enfants.length === 0 ? (
              <Box
                className="flex items-center gap-2 rounded-2xl px-2 py-2 sm:gap-3 sm:px-3 sm:py-3"
                sx={{
                  background:
                    "linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(174,218,196,0.10) 100%)",
                  border: "1px dashed rgba(var(--vtf-teal-rgb),0.18)",
                }}
              >
                <Box
                  sx={{
                    width: 36,
                    height: 36,
                    borderRadius: "14px",
                    display: "grid",
                    placeItems: "center",
                    bgcolor: "rgba(var(--vtf-orange-rgb),0.10)",
                    color: "var(--vtf-orange)",
                    fontWeight: 900,
                    fontSize: "var(--vtf-font-lg)",
                    flexShrink: 0,
                  }}
                >
                  +
                </Box>

                <Box sx={{ minWidth: 0 }}>
                  <Typography
                    sx={{
                      fontSize: "var(--vtf-font-sm)",
                      fontWeight: 900,
                      color: "var(--vtf-navy)",
                      mb: 0.3,
                      lineHeight: 1.2,
                    }}
                  >
                    {tf("noChildrenAdded")}
                  </Typography>

                  <Typography
                    sx={{
                      fontSize: "var(--vtf-font-sm)",
                      fontWeight: 600,
                      color: "var(--vtf-navy)",
                      opacity: 0.68,
                      lineHeight: 1.45,
                    }}
                  >
                    {tf("noChildrenHint")}
                  </Typography>
                </Box>
              </Box>
            ) : (
              value.enfants.map((e, idx) => {
                const fraction = fractionForAge(e.age);

                return (
                  <Box
                    key={idx}
                    className="grid grid-cols-[24px_minmax(0,1fr)_auto] items-center gap-2 rounded-xl bg-white/80 p-2 sm:gap-3 sm:bg-transparent sm:p-0"
                  >
                    <Box className="w-6 h-6 rounded-full flex items-center justify-center text-[var(--vtf-font-xs)] font-black text-vtf-navy bg-white border border-slate-200 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
                      {idx + 1}
                    </Box>

                    <Box className="flex-1 min-w-0">
                      <VtfSelect
                        className="vtf-select-age"
                        options={ageOptions}
                        value={e.age.toString()}
                        onChange={(v) => onSetEnfantAge(idx, Number(v))}
                        width="100%"
                        showIcons={false}
                        variant="light"
                        size="compact"
                      />
                    </Box>

                    <Box className="flex items-center justify-end gap-2 min-w-[76px]">
                      {childDiscountsLoading ? (
                        <Skeleton
                          variant="rounded"
                          animation="pulse"
                          className="vtf-discount-chip-skeleton"
                        />
                      ) : fraction != null && fraction > 0 ? (
                        <Box
                          className={`vtf-discount-chip ${
                            fraction >= 1
                              ? "vtf-discount-chip--free"
                              : "vtf-discount-chip--partial"
                          }`}
                        >
                          {discountChipLabel(fraction)}
                        </Box>
                      ) : childDiscountsError && childDiscounts == null ? (
                        <Box
                          className="vtf-discount-chip vtf-discount-chip--unavailable"
                          title={tf("discountUnavailable")}
                        >
                          -
                        </Box>
                      ) : null}

                      <Button
                        type="button"
                        vtfVariant="iconRemove"
                        onClick={() => onRemoveEnfant(idx)}
                        aria-label={tf("removeChildAria")}
                      >
                        ×
                      </Button>
                    </Box>
                  </Box>
                );
              })
            )}
          </Box>
        </Box>
      </Box>

      <NoticeBox
        tone="teal"
        dense
        sx={{
          mt: { xs: 3, sm: 4 },
          display: "flex",
          gap: 2,
          alignItems: "flex-start",
        }}
      >
        <Box
          sx={{
            color: "var(--vtf-teal)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <LightbulbRoundedIcon sx={{ fontSize: "var(--vtf-font-md)" }} />
        </Box>
        <Typography
          variant="caption"
          sx={{
            color: "var(--vtf-navy)",
            opacity: 0.8,
            lineHeight: 1.2,
            fontSize: "var(--vtf-font-xs)",
          }}
        >
          <Box
            component="span"
            sx={{ fontWeight: 800, color: "var(--vtf-teal)" }}
          >
            {tf("tarifsTitle")}
          </Box>{" "}
          {tf("tarifsBody")}
        </Typography>
      </NoticeBox>

      {childDiscountsError && (
        <VtfErrorAlert
          title={tf("pricingRulesErrorTitle")}
          message={tf("pricingRulesError")}
          onRetry={onRetry}
          retryLabel={tf("retry")}
          sx={{ mb: 2, mt: 2 }}
        />
      )}
    </VtfGlassCard>
  );
}
