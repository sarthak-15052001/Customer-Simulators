import * as React from "react";
import { Box, Button, Typography } from "../../ui";
import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import ErrorOutlineRoundedIcon from "@mui/icons-material/ErrorOutlineRounded";
import OpenInNewRoundedIcon from "@mui/icons-material/OpenInNewRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import RestartAltRoundedIcon from "@mui/icons-material/RestartAltRounded";
import NightsStayRoundedIcon from "@mui/icons-material/NightsStayRounded";
import PeopleAltRoundedIcon from "@mui/icons-material/PeopleAltRounded";
import ChildCareRoundedIcon from "@mui/icons-material/ChildCareRounded";
import WavesRoundedIcon from "@mui/icons-material/WavesRounded";
import LandscapeRoundedIcon from "@mui/icons-material/LandscapeRounded";
import YardRoundedIcon from "@mui/icons-material/YardRounded";
import DownhillSkiingRoundedIcon from "@mui/icons-material/DownhillSkiing";
import TerrainRoundedIcon from "@mui/icons-material/Terrain";
import PlaceRoundedIcon from "@mui/icons-material/PlaceRounded";
import PersonRoundedIcon from "@mui/icons-material/PersonRounded";
import type { SvgIconProps } from "@mui/material/SvgIcon";
import { useTranslation } from "../../../contexts/LanguageContext";
import Tooltip from "@mui/material/Tooltip";
import { useEnvironments } from "../../../hooks/season.hooks";
import type { StayEstimateApiResult } from "../../../api/stayEstimate.api";
import type { FamilyState } from "../../../types/familyTab";
import type { SejourState } from "../../../types/stayTab";
import { recapSeasonPillKey } from "../../../utils/extrasTab";
import type { SejourEnvKey } from "../../../utils/stayTab";
import type { VtfVillage } from "../../../data/vtfStay";
import { formatEuro } from "../simulateur-vtf-details/_format";
import { SimulateurStepFooterRecapSkeleton } from "./SimulateurStepFooterRecapSkeleton";
import { formatDateRangeDDMMYYYY } from "../../../utils/date";

export type SimulateurStepFooterProps = {
  onPrevious: () => void;
  onNext?: () => void;
  disablePrevious?: boolean;
  disableNext?: boolean;
  previousLabel?: string;
  nextLabel?: string;
  isLastStep?: boolean;
  onViewDetails?: () => void;
  viewDetailsLabel?: string;
  showReset?: boolean;
  onReset?: () => void;
  resetLabel?: string;
  family?: FamilyState;
  sejour?: SejourState;
  village?: VtfVillage | null;
  serverEstimate?: StayEstimateApiResult | null;
  serverEstimateLoading?: boolean;
  serverEstimateError?: boolean;
  serverEstimateErrorMessage?: string | null;
  onRetryEstimate?: () => void;
};

const navBtnSx = {
  minWidth: { xs: 0, sm: 148 },
  flex: { xs: 1, sm: "0 0 auto" },
  height: 45,
} as const;

/** Solid backgrounds — no gradients */
const FOOTER_SHELL_BG = "#FFFFFF";
const FOOTER_RECAP_BG = "#E4F2F4";
const FOOTER_BORDER = "#D4E4E8";
const FOOTER_NAV_BG = "#FFFFFF";

const badgeIconSx = { fontSize: 16, color: "inherit", flexShrink: 0 } as const;

const ENV_ICONS: Record<SejourEnvKey, React.ComponentType<SvgIconProps>> = {
  mer: WavesRoundedIcon,
  montagne: LandscapeRoundedIcon,
  campagne: YardRoundedIcon,
  ski: DownhillSkiingRoundedIcon,
  fond: TerrainRoundedIcon,
};

function FooterBadge({
  icon,
  label,
  maxWidth,
}: {
  icon?: React.ReactNode;
  label: string;
  maxWidth?: number | string;
}) {
  const needTooltip = Boolean(maxWidth) || (label && label.length > 24);
  const content = (
    <Box
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: icon ? 0.5 : 0,
        py: 0.35,
        px: { xs: 1, sm: 1.35 },
        borderRadius: "9999px",
        bgcolor: "#FFFFFF",
        border: "1px solid #C5DDE3",
        color: "#00445A",
        maxWidth: maxWidth ?? "none",
      }}
    >
      {icon}
      <Typography
        component="span"
        sx={{
          fontSize: { xs: "var(--vtf-font-xs)", sm: "var(--vtf-font-sm)" },
          fontWeight: 950,
          lineHeight: 1.2,
          whiteSpace: "nowrap",
          overflow: maxWidth ? "hidden" : "visible",
          textOverflow: maxWidth ? "ellipsis" : "clip",
        }}
      >
        {label}
      </Typography>
    </Box>
  );

  return needTooltip ? (
    <Tooltip title={label} enterDelay={200} leaveDelay={50}>
      {content}
    </Tooltip>
  ) : (
    content
  );
}

function FamilyAmountCard({
  icon,
  countLabel,
  amount,
  subtext,
}: {
  icon: React.ReactNode;
  countLabel: string;
  amount: string;
  subtext?: string;
}) {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1,
        px: 1.15,
        py: 0.9,
        borderRadius: "14px",
        bgcolor: "#FFFFFF",
        border: "1px solid #C5DDE3",
        minWidth: { xs: "100%", sm: 180 },
        maxWidth: { sm: 240 },
        flex: { xs: "1 1 100%", sm: "0 0 auto" },
      }}
    >
      <Box
        sx={{
          width: 36,
          height: 36,
          borderRadius: "10px",
          bgcolor: "#E8F4F1",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {icon}
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Tooltip title={countLabel} enterDelay={200} leaveDelay={50}>
          <Typography
            sx={{
              fontSize: "var(--vtf-font-sm)",
              fontWeight: 900,
              color: "#3D6570",
              lineHeight: 1.25,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {countLabel}
          </Typography>
        </Tooltip>
        {subtext && (
          <Typography
            sx={{
              fontSize: "var(--vtf-font-xs)",
              fontWeight: 800,
              color: "#5A7A85",
              lineHeight: 1.1,
            }}
          >
            {subtext}
          </Typography>
        )}
      </Box>
      <Typography
        sx={{
          fontSize: "var(--vtf-font-md)",
          fontWeight: 950,
          color: "#00445A",
          lineHeight: 1,
          whiteSpace: "nowrap",
          px: 1,
          py: 0.4,
          borderRadius: "10px",
          bgcolor: "#E8F4F1",
          flexShrink: 0,
        }}
      >
        {amount}
      </Typography>
    </Box>
  );
}

/**
 * Step footer (static, not fixed): stay recap + prev/next navigation.
 */
export function SimulateurStepFooter({
  onPrevious,
  onNext,
  disablePrevious = false,
  disableNext = false,
  previousLabel,
  nextLabel,
  isLastStep = false,
  onViewDetails,
  viewDetailsLabel,
  showReset = false,
  onReset,
  resetLabel,
  family,
  sejour,
  village,
  serverEstimate = null,
  serverEstimateLoading = false,
  serverEstimateError = false,
  serverEstimateErrorMessage = null,
  onRetryEstimate,
}: SimulateurStepFooterProps) {
  const { t } = useTranslation();
  const prevLabel = previousLabel ?? t("simulateur.nav.previous");
  const nxtLabel = nextLabel ?? t("simulateur.nav.next");
  const detailsLabel = viewDetailsLabel ?? t("simulateur.recap.viewDetails");
  const resetBtnLabel = resetLabel ?? t("simulateur.nav.resetSimulation");
  const budgetLabel = t("simulateur.recap.estimatedBudget");

  const { data: envOptions = [] } = useEnvironments(
    sejour?.fSaison ?? undefined,
  );
  const envMeta = sejour?.fEnv
    ? envOptions.find((o) => o.key === sejour.fEnv)
    : undefined;

  const hasSeason = !!sejour?.fSaison;
  const hasVillage = !!sejour?.villageId;
  const hasFormule = !!sejour?.formule;
  const showRecap = hasSeason && !!family && !!sejour;
  const showServerSkeleton =
    serverEstimateLoading && hasVillage && hasFormule;
  const showEstimateError =
    serverEstimateError &&
    !serverEstimateLoading &&
    hasVillage &&
    hasFormule;

  const adultWord =
    family && family.adultes === 1
      ? t("simulateur.recap.adultOne")
      : t("simulateur.recap.adultMany");
  const childCount = family?.enfants.length ?? 0;
  const childWord =
    childCount === 1
      ? t("simulateur.recap.childOne")
      : t("simulateur.recap.childMany");

  const seasonPillKey = sejour
    ? recapSeasonPillKey(sejour)
    : null;

  const pills = showRecap ? (
    <>
      {seasonPillKey && (
        <FooterBadge
          label={t(`simulateur.recap.pillSeason.${seasonPillKey}`)}
        />
      )}
      {sejour.dateDebut && (
        <FooterBadge
          label={
            formatDateRangeDDMMYYYY(sejour.dateDebut, sejour.dateFin) ?? ""
          }
        />
      )}
      <FooterBadge
        icon={<NightsStayRoundedIcon sx={badgeIconSx} />}
        label={`${sejour.fNuits} ${sejour.fNuits > 1 ? t("simulateur.recap.nightPlural") : t("simulateur.recap.nightSingular")}`}
      />
      {sejour.fEnv &&
        (() => {
          const EnvIcon = ENV_ICONS[sejour.fEnv] ?? PlaceRoundedIcon;
          const envLabel = envMeta?.label ?? sejour.fEnv;
          return (
            <FooterBadge icon={<EnvIcon sx={badgeIconSx} />} label={envLabel} />
          );
        })()}
      {village?.nom && (
        <FooterBadge
          icon={<PlaceRoundedIcon sx={badgeIconSx} />}
          label={village.nom}
          maxWidth={240}
        />
      )}
      {Boolean(
        serverEstimate?.soloSupplement &&
          serverEstimate.soloSupplement > 0 &&
          family?.adultes === 1 &&
          (family?.enfants.length ?? 0) > 0,
      ) && (
        <FooterBadge
          icon={<PersonRoundedIcon sx={badgeIconSx} />}
          label={`${t("simulateur.recap.soloSupplement")} : ${formatEuro(serverEstimate!.soloSupplement)}`}
        />
      )}
    </>
  ) : null;

  const recapBlock = showRecap ? (
    <Box
      sx={{
        borderBottom: `1px solid ${FOOTER_BORDER}`,
        bgcolor: FOOTER_RECAP_BG,
      }}
    >
      {showServerSkeleton ? (
        <SimulateurStepFooterRecapSkeleton budgetLabel={budgetLabel} />
      ) : showEstimateError && !serverEstimate ? (
        <Box
          sx={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 1,
            px: { xs: 1.25, sm: 1.5 },
            py: { xs: 1.15, sm: 1.25 },
          }}
        >
          <Box sx={{ display: "flex", gap: 0.65, flexWrap: "wrap" }}>
            {pills}
          </Box>
          <Box
            sx={{
              flex: "1 1 220px",
              display: "flex",
              alignItems: "center",
              gap: 1,
              px: 1.15,
              py: 0.85,
              borderRadius: "14px",
              bgcolor: "#FFFFFF",
              border: "1px solid #F0C9B8",
            }}
          >
            <ErrorOutlineRoundedIcon
              sx={{ fontSize: 20, color: "var(--vtf-orange)", flexShrink: 0 }}
            />
            <Typography
              sx={{
                fontSize: "var(--vtf-font-sm)",
                fontWeight: 950,
                color: "var(--vtf-navy)",
                flex: 1,
              }}
            >
              {serverEstimateErrorMessage || t("simulateur.recap.estimateErrorTitle")}
            </Typography>
            {onRetryEstimate ? (
              <Button
                vtfVariant="orangeFillPill"
                size="small"
                onClick={onRetryEstimate}
                startIcon={<RefreshRoundedIcon sx={{ fontSize: 18 }} />}
                sx={{
                  flexShrink: 0,
                  fontWeight: 900,
                  fontSize: "var(--vtf-font-xs)",
                }}
              >
                {t("simulateur.family.retry")}
              </Button>
            ) : null}
          </Box>
        </Box>
      ) : (
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: {
              xs: "1fr",
              sm: "auto minmax(170px, 1fr) minmax(220px, auto)",
            },
            alignItems: "center",
            gap: { xs: 1, sm: 1.5, md: 2 },
            px: { xs: 1.25, sm: 1.5 },
            py: { xs: 1.15, sm: 1.25 },
          }}
        >
          <Box
            sx={{
              display: "flex",
              gap: 0.65,
              flexWrap: "wrap",
              justifyContent: { xs: "center", sm: "flex-start" },
              pr: { md: 2 },
              borderRight: {
                xs: "none",
                md: `1px solid ${FOOTER_BORDER}`,
              },
            }}
          >
            {pills}
          </Box>

          <Box
            sx={{
              textAlign: { xs: "center", sm: "left" },
              minWidth: { sm: 160, md: 200 },
              position: "relative",
            }}
          >
            <Typography
              sx={{
                fontSize: "var(--vtf-font-xs)",
                fontWeight: 950,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "#5A7A85",
                lineHeight: 1,
                mb: 0.4,
                whiteSpace: "nowrap",
                position: "relative",
                zIndex: 1,
              }}
            >
              {budgetLabel}
            </Typography>

            {serverEstimate ? (
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: { xs: "center", sm: "flex-start" },
                }}
              >
                <Typography
                  sx={{
                    fontSize: { xs: 22, sm: 24 },
                    fontWeight: 950,
                    color: "var(--vtf-navy)",
                    lineHeight: 1,
                    whiteSpace: "nowrap",
                    position: "relative",
                    zIndex: 1,
                    letterSpacing: "-0.02em",
                  }}
                >
                  {formatEuro(serverEstimate.total)}
                </Typography>
              </Box>
            ) : (
              <Typography
                sx={{
                  fontSize: "var(--vtf-font-sm)",
                  fontWeight: 850,
                  color: "#3D6570",
                }}
              >
                {hasVillage
                  ? hasFormule
                    ? (serverEstimateErrorMessage || t("simulateur.recap.estimateErrorMessage"))
                    : t("simulateur.sejour.blockingFormule")
                  : t("simulateur.sejour.blockingVillage")}
              </Typography>
            )}
          </Box>

          {serverEstimate && family ? (
            <Box
              sx={{
                display: "flex",
                flexDirection: "row",
                flexWrap: { xs: "wrap", sm: "nowrap" },
                gap: 0.6,
                justifyContent: { xs: "center", sm: "flex-end" },
                width: { xs: "100%", sm: "auto" },
                minWidth: { sm: 300 },
              }}
            >
              <FamilyAmountCard
                icon={<PeopleAltRoundedIcon sx={badgeIconSx} />}
                countLabel={`${family.adultes} ${adultWord}`}
                amount={formatEuro(serverEstimate.totalAdults)}
              />
              <FamilyAmountCard
                icon={<ChildCareRoundedIcon sx={badgeIconSx} />}
                countLabel={`${childCount} ${childWord}`}
                amount={formatEuro(serverEstimate.totalChildren)}
              />
            </Box>
          ) : null}
        </Box>
      )}
    </Box>
  ) : null;

  const rightAction = showReset ? (
    <Button
      type="button"
      variant="contained"
      vtfVariant="stepNext"
      onClick={onReset}
      endIcon={<RestartAltRoundedIcon />}
      sx={navBtnSx}
    >
      {resetBtnLabel}
    </Button>
  ) : isLastStep ? (
    <Button
      type="button"
      variant="contained"
      vtfVariant="stepNext"
      onClick={onViewDetails}
      endIcon={<OpenInNewRoundedIcon />}
      sx={navBtnSx}
    >
      {detailsLabel}
    </Button>
  ) : (
    <Button
      type="button"
      variant="contained"
      vtfVariant="stepNext"
      disabled={disableNext}
      onClick={() => onNext?.()}
      endIcon={<ChevronRightRoundedIcon />}
      sx={navBtnSx}
    >
      {nxtLabel}
    </Button>
  );

  return (
    <Box
      component="nav"
      aria-label={t("simulateur.nav.ariaLabel")}
      sx={{
        width: "100%",
        borderRadius: "20px",
        overflow: "hidden",
        bgcolor: FOOTER_SHELL_BG,
        border: `1px solid ${FOOTER_BORDER}`,
        boxShadow: "0 8px 28px #DCE8EB",
      }}
    >
      {recapBlock}

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 1.25,
          px: { xs: 1.25, sm: 1.75 },
          py: { xs: 1.25, sm: 1.5 },
          bgcolor: FOOTER_NAV_BG,
        }}
      >
        <Button
          type="button"
          variant="text"
          vtfVariant="stepPrevious"
          disabled={disablePrevious}
          onClick={onPrevious}
          startIcon={<ChevronLeftRoundedIcon />}
          sx={navBtnSx}
        >
          {prevLabel}
        </Button>

        {rightAction}
      </Box>
    </Box>
  );
}
