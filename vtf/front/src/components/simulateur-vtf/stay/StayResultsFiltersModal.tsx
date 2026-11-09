import * as React from "react";
import Dialog from "@mui/material/Dialog";
import DialogContent from "@mui/material/DialogContent";
import TuneRoundedIcon from "@mui/icons-material/TuneRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";

import { useTranslation } from "../../../contexts/LanguageContext";
import type { VtfFormule } from "../../../data/vtfStay";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";
import {
  Box,
  Button,
  IconButton,
  Skeleton,
  Typography,
  VtfSelect,
} from "../../ui";
import type { Option } from "../../ui/Select";
import { useFormules } from "../../../hooks/formules.hooks";
import { useRegions } from "../../../hooks/region.hooks";
import { StayFormulePickerSection } from "./StayFormulePicker.ui";
import {
  STAY_FILTER_MODAL_SECTION_LABEL_SX,
  STAY_FORMULE_SECTION_SURFACE_SX,
  resolveStayFormulePickerOptions,
} from "./StayFormulePicker.shared";
import { StayFormulePickerSkeleton } from "./StayFormulePickerSkeleton";

export type StayResultsFiltersSubmitPayload = {
  region: string;
  activityIds: string[];
  formule: VtfFormule | null;
};

export type StayResultsFiltersModalProps = {
  open: boolean;
  onClose: () => void;
  /** Région appliquée précédemment (utilisée pour initialiser l'état local à l'ouverture). */
  committedRegionFilter: string;
  /** Formule appliquée précédemment (utilisée pour initialiser l'état local à l'ouverture). */
  committedFormule: VtfFormule | null;
  selectedActivityIds: string[];
  onSubmit: (payload: StayResultsFiltersSubmitPayload) => void;
};

/**
 * Dialogue de filtres compact (région, etc.) — ouvert depuis le contrôle « + » des résultats.
 */
export function StayResultsFiltersModal({
  open,
  onClose,
  committedRegionFilter,
  committedFormule,
  selectedActivityIds,
  onSubmit,
}: StayResultsFiltersModalProps) {
  const { t } = useTranslation();
  const ts = React.useCallback((k: string) => t(`simulateur.sejour.${k}`), [t]);

  const { data: regionsData, isLoading: regionsLoading } = useRegions(open);
  const {
    data: apiFormules,
    isLoading: formulesLoading,
    isError: formulesError,
    refetch: refetchFormules,
  } = useFormules(open);

  const regionOptions = React.useMemo((): Option[] => {
    const all: Option = {
      value: "",
      label: t("simulateur.sejour.regionFilterAll"),
    };
    if (!regionsData?.length) return [all];
    return [
      all,
      ...regionsData.map((r) => ({
        value: r.key,
        label: r.key,
        badge: r.villageCount,
      })),
    ];
  }, [regionsData, t]);

  const [draftRegion, setDraftRegion] = React.useState("");
  const [draftActivityIds, setDraftActivityIds] = React.useState<string[]>([]);
  const [draftFormule, setDraftFormule] = React.useState<VtfFormule | null>(
    null,
  );

  React.useEffect(() => {
    if (!open) return;
    const id = window.requestAnimationFrame(() => {
      setDraftRegion(committedRegionFilter ?? "");
      setDraftActivityIds([...selectedActivityIds]);
      setDraftFormule(committedFormule);
    });
    return () => window.cancelAnimationFrame(id);
  }, [open, committedRegionFilter, committedFormule, selectedActivityIds]);

  const handleSubmit = React.useCallback(() => {
    onSubmit({
      region: draftRegion,
      activityIds: draftActivityIds,
      formule: draftFormule,
    });
  }, [draftActivityIds, draftFormule, draftRegion, onSubmit]);

  const formuleOptions = React.useMemo(
    () => resolveStayFormulePickerOptions({ apiFormules }),
    [apiFormules],
  );

  const filterDialogTitleId = "stay-results-filter-modal-title";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby={filterDialogTitleId}
      slotProps={{
        backdrop: { sx: { backdropFilter: "blur(8px)" } },
        paper: {
          sx: {
            borderRadius: "24px",
            width: "100%",
            maxWidth: { xs: "min(100%, calc(100vw - 20px))", sm: 520 },
            m: { xs: 1.25, sm: 2 },
            overflow: "hidden",
            boxShadow:
              "0 28px 64px -20px rgba(2, 8, 23, 0.48), 0 0 0 1px rgba(15, 23, 42, 0.06)",
          },
        },
      }}
    >
      <Box
        sx={{
          px: { xs: 2, sm: 2.25 },
          py: { xs: 1.5, sm: 1.65 },
          background:
            "linear-gradient(135deg, rgba(0, 168, 181, 0.12) 0%, rgba(255, 255, 255, 0.97) 42%, rgba(242, 166, 128, 0.11) 100%)",
          borderBottom: "1px solid rgba(15, 23, 42, 0.06)",
        }}
      >
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 1.25,
          }}
        >
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              minWidth: 0,
            }}
          >
            <Box
              sx={{
                width: 34,
                height: 34,
                borderRadius: "12px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                bgcolor: "rgba(255, 255, 255, 0.8)",
                border: "1px solid rgba(15, 23, 42, 0.07)",
                boxShadow: "0 6px 16px rgba(2, 8, 23, 0.05)",
                color: "var(--vtf-teal)",
              }}
            >
              <TuneRoundedIcon sx={{ fontSize: "var(--vtf-font-lg)" }} />
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography
                id={filterDialogTitleId}
                component="h2"
                sx={{
                  fontSize: "var(--vtf-font-sm)",
                  fontWeight: 950,
                  color: "var(--vtf-navy)",
                  letterSpacing: "-0.02em",
                  lineHeight: 1.2,
                }}
              >
                {ts("resultsFilterModalTitle")}
              </Typography>
              <Typography
                sx={{
                  fontSize: "var(--vtf-font-xs)",
                  fontWeight: 650,
                  color: "var(--vtf-navy)",
                  opacity: 0.5,
                  mt: 0.2,
                  lineHeight: 1.35,
                }}
              >
                {ts("resultsFilterModalSubtitle")}
              </Typography>
            </Box>
          </Box>
          <IconButton
            type="button"
            size="small"
            onClick={onClose}
            aria-label={ts("resultsFilterModalClose")}
            sx={{
              flexShrink: 0,
              color: "var(--vtf-navy)",
              opacity: 0.45,
              p: 0.5,
              "&:hover": { opacity: 0.8, bgcolor: "rgba(15, 23, 42, 0.06)" },
            }}
          >
            <CloseRoundedIcon sx={{ fontSize: 20 }} />
          </IconButton>
        </Box>
      </Box>

      <DialogContent
        className="vtf-scrollbar-thin"
        sx={{
          px: { xs: 2, sm: 2.25 },
          pt: { xs: 2, sm: 2.25 },
          pb: { xs: 1.5, sm: 1.75 },
          maxHeight: "min(78vh, 580px)",
          overflowY: "auto",
          scrollbarGutter: "stable",
        }}
      >
        {formulesLoading ? (
          <Box sx={STAY_FORMULE_SECTION_SURFACE_SX}>
            <Typography sx={STAY_FILTER_MODAL_SECTION_LABEL_SX}>
              {ts("stayFormulaTitle")}
            </Typography>
            <StayFormulePickerSkeleton mobileScroll scrollGridFrom="sm" />
          </Box>
        ) : formulesError ? (
          <Box sx={{ mb: 1.75 }}>
            <VtfErrorAlert
              title={ts("formulesLoadErrorTitle")}
              message={ts("formulesLoadError")}
              onRetry={() => void refetchFormules()}
              retryLabel={t("simulateur.family.retry")}
            />
          </Box>
        ) : (
          <StayFormulePickerSection
            title={ts("stayFormulaTitle")}
            options={formuleOptions}
            selectedFormule={draftFormule}
            onSelect={(f) =>
              setDraftFormule((prev) => (prev === f ? null : f))
            }
            layout="three"
            density="compact"
            labelSx={STAY_FILTER_MODAL_SECTION_LABEL_SX}
            scrollGridFrom="sm"
          />
        )}

        <Box sx={STAY_FORMULE_SECTION_SURFACE_SX}>
          <Typography sx={{ ...STAY_FILTER_MODAL_SECTION_LABEL_SX, mb: 0.95 }}>
            {ts("regionFilterLabel")}
          </Typography>
          {regionsLoading ? (
            <Skeleton
              variant="text"
              width={120}
              height={14}
              sx={{ mb: 0.75, borderRadius: 1 }}
            />
          ) : null}
          <VtfSelect
            className="vtf-select-age"
            variant="light"
            size="compact"
            width="100%"
            menuWidth={320}
            ariaLabel={ts("regionFilterLabel")}
            placeholder={ts("regionFilterAll")}
            options={regionOptions}
            value={draftRegion ?? ""}
            onChange={(v) => {
              setDraftRegion(v);
              setDraftActivityIds([]);
            }}
          />
          <Typography
            sx={{
              mt: 1,
              fontSize: "var(--vtf-font-xs)",
              fontWeight: 650,
              color: "var(--vtf-navy)",
              opacity: 0.45,
              lineHeight: 1.45,
            }}
          >
            {ts("regionFilterHint")}
          </Typography>
        </Box>
      </DialogContent>

      <Box
        sx={{
          px: { xs: 2, sm: 2.25 },
          pb: { xs: 2, sm: 2.25 },
          pt: 0,
          borderTop: "1px solid rgba(15, 23, 42, 0.05)",
          bgcolor: "rgba(255, 255, 255, 0.65)",
        }}
      >
        <Button
          type="button"
          fullWidth
          vtfVariant="orangeFillPill"
          onClick={handleSubmit}
          sx={{
            py: 1.1,
            fontWeight: 900,
            fontSize: "var(--vtf-font-sm)",
            borderRadius: "14px",
            boxShadow: "0 10px 28px rgba(242, 166, 128, 0.28)",
          }}
        >
          {ts("resultsFilterModalSubmit")}
        </Button>
      </Box>
    </Dialog>
  );
}
