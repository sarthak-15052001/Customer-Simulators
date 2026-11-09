import * as React from "react";
import { Box, Button, TextField, Typography } from "../../ui";
import LocalHotelRoundedIcon from "@mui/icons-material/LocalHotelRounded";
import DatePicker, { registerLocale } from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import "../../../styles/react-datepicker-vtf.css";
import { format, parseISO } from "date-fns";
import { fr, es, nl, enGB } from "date-fns/locale";
import { createPortal } from "react-dom";
import { useTranslation } from "../../../contexts/LanguageContext";
import { addDaysIso, diffNuits, todayIsoLocal } from "../../../utils/stayTab";
import type { MarketingSeason } from "../../../api/season.api";
import { QuantityStepper } from "../../shared/QuantityStepper";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { VtfSectionHeading } from "../../shared/VtfSectionHeading";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";
import { StayNightsS } from "./StayNightsCard.ui";

registerLocale("fr", fr);
registerLocale("es", es);
registerLocale("nl", nl);
registerLocale("en", enGB);

const NUIT_SHORTCUTS = [2, 3, 7, 10, 14] as const;


function nightsChipKey(n: (typeof NUIT_SHORTCUTS)[number]): string {
  return `nightsChip${n}`;
}

function draftFromCommitted(
  v: {
    fNuits: number;
    dateDebut: string | null;
    dateFin: string | null;
  },
  activeSeason?: MarketingSeason,
) {
  const d0 = v.dateDebut ?? activeSeason?.defaultDate ?? todayIsoLocal();
  const n = v.fNuits;
  return {
    fNuits: n,
    dateDebut: d0,
    dateFin: v.dateFin ?? addDaysIso(d0, n),
  };
}

type Props = {
  value: {
    fNuits: number;
    dateDebut: string | null;
    dateFin: string | null;
  };
  onChange: (next: {
    fNuits: number;
    dateDebut: string | null;
    dateFin: string | null;
  }) => void;
  onVillageMaybeInvalid: () => void;
  onApplied?: () => void;
  activeSeason?: MarketingSeason;
  isError?: boolean;
  onRetry?: () => void;
};

export function StayNightsCard({
  value,
  onChange,
  onVillageMaybeInvalid,
  onApplied,
  activeSeason,
  isError,
  onRetry,
}: Props) {
  const { t, language } = useTranslation();
  const ts = React.useCallback((k: string) => t(`simulateur.sejour.${k}`), [t]);

  const datePickerLocale = React.useMemo(() => {
    switch (language) {
      case "FR":
        return "fr";
      case "ES":
        return "es";
      case "NL":
        return "nl";
      case "GB":
        return "en";
      default:
        return "fr";
    }
  }, [language]);

  const [prevValue, setPrevValue] = React.useState(value);
  const [prevSeason, setPrevSeason] = React.useState(activeSeason);
  const [draft, setDraft] = React.useState(() =>
    draftFromCommitted(value, activeSeason),
  );

  if (
    value.dateDebut !== prevValue.dateDebut ||
    value.dateFin !== prevValue.dateFin ||
    value.fNuits !== prevValue.fNuits ||
    activeSeason !== prevSeason
  ) {
    setPrevValue(value);
    setPrevSeason(activeSeason);
    setDraft(draftFromCommitted(value, activeSeason));
  }

  const dateToIso = React.useCallback((d: Date) => format(d, "yyyy-MM-dd"), []);
  const isoToDate = React.useCallback(
    (iso: string | null) => (iso ? parseISO(iso) : null),
    [],
  );

  const arrivalDate = React.useMemo(
    () => isoToDate(draft.dateDebut),
    [draft.dateDebut, isoToDate],
  );
  const departureDate = React.useMemo(
    () => isoToDate(draft.dateFin),
    [draft.dateFin, isoToDate],
  );

  const activeStartDate = activeSeason?.startDate;
  const activeEndDate = activeSeason?.endDate;

  const minArrivalDate = React.useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (!activeStartDate) return today;

    const start = parseISO(activeStartDate);
    start.setHours(0, 0, 0, 0);
    return start > today ? start : today;
  }, [activeStartDate]);

  const maxArrivalDate = React.useMemo(
    () =>
      activeEndDate
        ? parseISO(activeEndDate)
        : parseISO("2026-12-31"),
    [activeEndDate],
  );

  const dirty = React.useMemo(
    () =>
      draft.fNuits !== value.fNuits ||
      draft.dateDebut !== value.dateDebut ||
      draft.dateFin !== value.dateFin,
    [draft, value.fNuits, value.dateDebut, value.dateFin],
  );

  const setDraftNuits = (n: number) => {
    const nextN = Math.max(1, Math.min(14, n));
    setDraft((d) => ({
      fNuits: nextN,
      dateDebut: d.dateDebut,
      dateFin: addDaysIso(d.dateDebut, nextN),
    }));
  };

  const onPickArrival = (d: Date | null) => {
    if (!d) {
      const d0 = activeSeason?.defaultDate ?? todayIsoLocal();
      setDraft((prev) => ({
        ...prev,
        dateDebut: d0,
        dateFin: addDaysIso(d0, prev.fNuits),
      }));
      return;
    }
    const dateDebut = dateToIso(d);
    setDraft((prev) => ({
      ...prev,
      dateDebut,
      dateFin: addDaysIso(dateDebut, prev.fNuits),
    }));
  };

  const applyDraft = () => {
    onChange({
      fNuits: draft.fNuits,
      dateDebut: draft.dateDebut,
      dateFin: draft.dateFin,
    });
    onVillageMaybeInvalid();
    onApplied?.();
  };

  const popperContainer = React.useCallback(
    ({ children }: { children?: React.ReactNode }) =>
      createPortal(children ?? null, document.body),
    [],
  );

  const nuits = diffNuits(draft.dateDebut, draft.dateFin);

  const stepperUnitLabel =
    draft.fNuits === 7
      ? ts("nightsStepperWeek1")
      : draft.fNuits === 14
        ? ts("nightsStepperWeek2")
        : draft.fNuits === 21
          ? ts("nightsStepperWeek3")
          : draft.fNuits === 1
            ? ts("nightsStepperUnitOne")
            : ts("nightsStepperUnitMany");

  return (
    <VtfGlassCard>
      <VtfSectionHeading
        accent="navy"
        icon={<LocalHotelRoundedIcon />}
        title={ts("nightsTitle")}
      />

      <QuantityStepper
        value={draft.fNuits}
        counterSize="md"
        plusTone="navy"
        onDec={() => setDraftNuits(draft.fNuits - 1)}
        onInc={() => setDraftNuits(draft.fNuits + 1)}
        decDisabled={draft.fNuits <= 1}
        incDisabled={draft.fNuits >= 14}
        containerSx={StayNightsS.stepperWrap}
      >
        <Box sx={StayNightsS.stepperValueWrap}>
          <Typography sx={StayNightsS.stepperValue}>{draft.fNuits}</Typography>
          <Typography sx={StayNightsS.stepperUnit}>
            {stepperUnitLabel}
          </Typography>
        </Box>
      </QuantityStepper>

      <Box
        className="vtf-horizontal-scroll"
        sx={{
          ...StayNightsS.shortcutsRow,
          overflowX: { xs: "auto", md: "visible" },
          flexWrap: { xs: "nowrap", md: "wrap" },
          pb: { xs: 0.25, md: 0 },
        }}
      >
        {NUIT_SHORTCUTS.map((n) => {
          const active = draft.fNuits === n;
          return (
            <Button
              key={n}
              vtfVariant="navyFilterPill"
              filterActive={active}
              onClick={() => setDraftNuits(n)}
            >
              {ts(nightsChipKey(n))}
            </Button>
          );
        })}
      </Box>

      <Box sx={StayNightsS.datesGrid}>
        <Box sx={StayNightsS.dateField}>
          <Typography component="label" sx={StayNightsS.fieldLabel}>
            {ts("arrivalOptional")}
          </Typography>
          <DatePicker
            locale={datePickerLocale}
            selected={arrivalDate}
            onChange={(d: Date | null) => onPickArrival(d)}
            dateFormat="dd/MM/yyyy"
            openToDate={arrivalDate ?? minArrivalDate}
            minDate={minArrivalDate}
            maxDate={maxArrivalDate}
            popperClassName="vtf-react-datepicker-popper"
            popperContainer={popperContainer}
            popperPlacement="bottom-start"
            customInput={
              <TextField
                fullWidth
                size="small"
                className="vtf-react-datepicker-input"
                slotProps={{
                  htmlInput: { "aria-label": ts("arrivalOptional") },
                }}
              />
            }
          />
        </Box>

        <Box sx={StayNightsS.dateField}>
          <Typography component="label" sx={StayNightsS.fieldLabel}>
            {ts("departureComputed")}
          </Typography>
          <DatePicker
            locale={datePickerLocale}
            selected={departureDate}
            onChange={() => {}}
            dateFormat="dd/MM/yyyy"
            disabled
            popperClassName="vtf-react-datepicker-popper"
            popperContainer={popperContainer}
            popperPlacement="bottom-start"
            customInput={
              <TextField
                fullWidth
                size="small"
                disabled
                className="vtf-react-datepicker-input vtf-react-datepicker-input--disabled"
                slotProps={{
                  htmlInput: { "aria-label": ts("departureComputed") },
                }}
              />
            }
          />
        </Box>
      </Box>

      {typeof nuits === "number" && nuits < 1 && (
        <Box sx={StayNightsS.warningBox}>
          <Typography sx={StayNightsS.warningText}>
            {ts("departureAfterArrival")}
          </Typography>
        </Box>
      )}

      <Box sx={StayNightsS.footerRow}>
        {dirty ? (
          <Typography sx={StayNightsS.draftHint}>
            {ts("nightsDraftHint")}
          </Typography>
        ) : (
          <Box />
        )}
        <Button
          type="button"
          vtfVariant="navyFillPill"
          disabled={!dirty}
          onClick={applyDraft}
          sx={StayNightsS.applyBtn}
        >
          {ts("nightsApplyDates")}
        </Button>
      </Box>

      {isError && (
        <VtfErrorAlert
          title={ts("errorDetailsLoad")}
          message={ts("errorSubtitle")}
          onRetry={onRetry}
          retryLabel={t("simulateur.family.retry")}
          sx={{ mt: 3 }}
        />
      )}
    </VtfGlassCard>
  );
}
