import * as React from "react";
import { Box, Pill, Typography } from "../../ui";

import type { SejourState } from "../../../types/stayTab";
import type { VtfInfraEntry } from "../../../data/vtfExtras";
import { useTranslation } from "../../../contexts/LanguageContext";
import { NoticeBox } from "../../shared/NoticeBox";
import StarsRoundedIcon from "@mui/icons-material/StarsRounded";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { useAnimations } from "../../../hooks/animations.hooks";
import { useFormules } from "../../../hooks/formules.hooks";
import { getFormuleLabelFromCatalog } from "../stay/StayFormulePicker.shared";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";
import {
  pillCompactCapsSx,
  pillCompactRowSx,
  pillTealAccentBorderSx,
  vtfCapsLabelSx,
} from "../../ui/vtfCardPresets";

type Props = {
  sejour: SejourState;
  villageInfra: VtfInfraEntry | null;
  animKey: "ete" | "hiver";
};

export function IncludedActivitiesCard({
  sejour,
  villageInfra,
  animKey,
}: Props) {
  const { t } = useTranslation();
  const te = React.useCallback((k: string) => t(`simulateur.extras.${k}`), [t]);
  const ts = React.useCallback((k: string) => t(`simulateur.sejour.${k}`), [t]);

  const {
    data: animationsData = [],
    isError: isAnimationsError,
    refetch: refetchAnimations,
  } = useAnimations();
  const { data: apiFormules } = useFormules();

  const includedList = React.useMemo(() => {
    const raw = villageInfra?.anim?.[animKey];
    if (raw && raw.length) return raw;
    return animationsData.map((a) => a.nom);
  }, [villageInfra, animKey, animationsData]);

  const extrasText = villageInfra?.extras?.[animKey] ?? "";
  const extrasLines = React.useMemo(
    () =>
      String(extrasText)
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
    [extrasText],
  );

  const infraTags = villageInfra?.infra ?? [];

  const includedPill = (
    <Pill
      size="small"
      label={te("includedPill")}
      vtfTone="softTeal"
      sx={{ ...pillCompactCapsSx, ...pillTealAccentBorderSx }}
    />
  );

  return (
    <VtfGlassCard
      title={te("includedTitle")}
      subtitle={te("includedSubtitle")}
      headingIcon={<StarsRoundedIcon />}
      headingAccent="teal"
      rightSlot={includedPill}
    >
      <NoticeBox tone="teal" dense>
        ✅ {te("includedHintPrefix")}{" "}
        {getFormuleLabelFromCatalog(sejour.formule, apiFormules)}
        {te("includedHintSuffix")}
      </NoticeBox>
      {isAnimationsError && (
        <VtfErrorAlert
          title={te("resultsActivitiesErrorTitle")}
          message={ts("errorSubtitle")}
          onRetry={() => refetchAnimations()}
          retryLabel={t("simulateur.family.retry")}
          sx={{ mt: 2, mb: 2 }}
        />
      )}
      <Box sx={{ mt: 2, display: "flex", flexDirection: "column", gap: 1 }}>
        {includedList.map((nom) => (
          <Box
            key={nom}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1.25,
              py: 0.75,
              borderBottom: "1px solid rgba(15,110,86,.10)",
            }}
          >
            <Box sx={{ color: "var(--vtf-teal)", fontWeight: 900 }}>✓</Box>
            <Typography
              sx={{
                flex: 1,
                fontSize: 'var(--vtf-font-sm)',
                fontWeight: 800,
                color: "var(--vtf-navy)",
              }}
            >
              {nom}
            </Typography>
            <Pill
              size="small"
              label={te("includedPill")}
              vtfTone="softTeal"
              sx={{ ...pillCompactRowSx, ...pillTealAccentBorderSx }}
            />
          </Box>
        ))}
      </Box>

      {!!extrasLines.length && (
        <Box
          sx={{
            mt: 2,
            p: 1.5,
            borderRadius: 2,
            bgcolor: "rgba(0,68,90,.04)",
            border: "1px solid rgba(0,68,90,.10)",
          }}
        >
          <Typography sx={{ ...vtfCapsLabelSx, mb: 1 }}>
            {te("extrasOnSiteTitle")}
          </Typography>
          {extrasLines.map((l) => (
            <Typography
              key={l}
              sx={{ fontSize: 'var(--vtf-font-sm)', color: "rgba(0,68,90,0.82)", py: 0.15 }}
            >
              • {l}
            </Typography>
          ))}
        </Box>
      )}

      {!!infraTags.length && (
        <Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", gap: 0.75 }}>
          {infraTags.map((tag) => (
            <Pill
              key={tag}
              size="small"
              label={tag}
              vtfTone="softNavy"
              sx={{
                ...pillCompactRowSx,
                fontSize: 'var(--vtf-font-sm)',
                bgcolor: "rgba(15,23,42,0.04)",
                color: "rgba(0,68,90,0.82)",
                border: "1px solid rgba(15,23,42,0.08)",
              }}
            />
          ))}
        </Box>
      )}

      {/* Avertissement sur la variabilité du contenu */}
      <Typography
        sx={{
          fontSize: 'var(--vtf-font-sm)',
          color: "text.secondary",
          mt: 1.5,
          fontStyle: "italic",
        }}
      >
        {te("footerNotice")}
      </Typography>
    </VtfGlassCard>
  );
}
