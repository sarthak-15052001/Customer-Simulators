import * as React from "react";
import { Pill } from "../../ui";
import RestaurantRoundedIcon from "@mui/icons-material/RestaurantRounded";

import { useTranslation } from "../../../contexts/LanguageContext";
import type { VtfFormule, VtfVillage } from "../../../data/vtfStay";
import { useFormules } from "../../../hooks/formules.hooks";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";
import { pillCompactCapsSx } from "../../ui/vtfCardPresets";
import { StayFormulePickerGrid } from "./StayFormulePicker.ui";
import { resolveStayFormulePickerOptions } from "./StayFormulePicker.shared";
import { StayFormulePickerSkeleton } from "./StayFormulePickerSkeleton";

type Props = {
  village: VtfVillage;
  value: { formule: VtfFormule | null };
  onSelect: (f: VtfFormule) => void;
};

export function StayFormuleCard({ village, value, onSelect }: Props) {
  const { t } = useTranslation();
  const ts = React.useCallback((k: string) => t(`simulateur.sejour.${k}`), [t]);

  const {
    data: apiFormules,
    isLoading,
    isError,
    refetch,
  } = useFormules();

  const formuleOptions = React.useMemo(
    () =>
      resolveStayFormulePickerOptions({
        apiFormules,
        villageFormules: village.formules,
      }),
    [apiFormules, village.formules],
  );

  const skeletonCount = Math.min(Math.max(village.formules.length, 1), 3);

  return (
    <VtfGlassCard
      glassClassName="vtf-glass-strong rounded-3xl p-4"
      title={ts("stayFormulaTitle")}
      headingIcon={<RestaurantRoundedIcon />}
      headingAccent="navy"
      rightSlot={
        <Pill
          size="small"
          label={
            value.formule
              ? `✓ ${ts("cardHintSelected")}`
              : `• ${ts("cardHintPick")}`
          }
          vtfTone="softNavy"
          sx={{
            ...pillCompactCapsSx,
            fontSize: "var(--vtf-font-sm)",
            fontWeight: 900,
            opacity: 0.95,
          }}
        />
      }
    >
      {isLoading ? (
        <StayFormulePickerSkeleton count={skeletonCount} />
      ) : isError ? (
        <VtfErrorAlert
          title={ts("formulesLoadErrorTitle")}
          message={ts("formulesLoadError")}
          onRetry={() => void refetch()}
          retryLabel={t("simulateur.family.retry")}
        />
      ) : (
        <StayFormulePickerGrid
          options={formuleOptions}
          selectedFormule={value.formule}
          onSelect={onSelect}
          layout="auto"
          density="default"
        />
      )}
    </VtfGlassCard>
  );
}
