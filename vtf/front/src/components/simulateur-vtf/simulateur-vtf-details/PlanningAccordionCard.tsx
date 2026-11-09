import * as React from "react";
import { Box, Typography, Button, Pill } from "../../ui";
import WbSunnyRoundedIcon from "@mui/icons-material/WbSunnyRounded";
import LightModeRoundedIcon from "@mui/icons-material/LightModeRounded";
import NightsStayRoundedIcon from "@mui/icons-material/NightsStayRounded";
import KeyboardArrowDownRoundedIcon from "@mui/icons-material/KeyboardArrowDownRounded";
import KeyboardArrowUpRoundedIcon from "@mui/icons-material/KeyboardArrowUpRounded";
import EventNoteRoundedIcon from "@mui/icons-material/EventNoteRounded";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { VtfSectionHeading } from "../../shared/VtfSectionHeading";
import type {
  PlanningItem,
  PlanningSlotKey,
  SejourState,
} from "../../../types/stayTab";
import type { VtfVillage } from "../../../data/vtfStay";
import {
  appLanguageToIntlLocale,
  emptyDaySlots,
  formatPlanningDayLabel,
  planningItemKey,
} from "../../../utils/planningTab";
import { PlanningSlotAddSelect } from "../planning/PlanningSlotAddSelect";
import { useTranslation } from "../../../contexts/LanguageContext";
import { useSimulateurTabTranslation } from "../../../hooks/useSimulateurTabTranslation";
import { RECAP_META, RECAP_TYPO } from "./recapCard.ui";

type SlotDef = {
  key: PlanningSlotKey;
  label: string;
  icon: React.ReactElement;
};

export function PlanningAccordionCard({
  sejour,
  village,
  isEditable = false,
  days = [],
  groups = [],
  getStats = () => null,
  onAddItem,
  onRemoveItem,
  itemsPillLabel,
  dayHint,
  removeAriaLabel,
  emptySlotLabel,
}: {
  sejour: SejourState;
  village: VtfVillage | null;
  isEditable?: boolean;
  days?: {
    key: string;
    label: string;
    index?: number;
    isDeparture?: boolean;
  }[];
  groups?: {
    key: string;
    title: string;
    icon: React.ReactNode;
    items: PlanningItem[];
  }[];
  getStats?: (
    it: PlanningItem,
  ) => { remaining: number; total: number; placed: number } | null;
  onAddItem?: (dayKey: string, slot: PlanningSlotKey, it: PlanningItem) => void;
  onRemoveItem?: (dayKey: string, slot: PlanningSlotKey, idx: number) => void;
  itemsPillLabel?: (n: number) => string;
  dayHint?: string;
  removeAriaLabel?: string;
  emptySlotLabel?: string;
}) {
  const { t, language } = useTranslation();
  const intlLocale = appLanguageToIntlLocale(language);
  const td = useSimulateurTabTranslation("details");
  const tp = React.useCallback(
    (k: string) => t(`simulateur.planning.${k}`),
    [t],
  );
  const resolvedItemsPillLabel =
    itemsPillLabel ?? ((n: number) => `${n} ${tp("itemsPill")}`);
  const resolvedRemoveAriaLabel = removeAriaLabel ?? tp("removeAria");
  const resolvedEmptySlotLabel = emptySlotLabel ?? tp("emptySlot");

  const dateRangeLabel = React.useMemo(() => {
    if (!sejour.dateDebut) return "";
    const pad = (n: number) => String(n).padStart(2, "0");
    const start = new Date(sejour.dateDebut);
    const startLabel = `${start.getDate()}/${pad(start.getMonth() + 1)}`;
    if (!sejour.dateFin) return startLabel;
    const end = new Date(sejour.dateFin);
    const endLabel = `${pad(end.getDate())}/${pad(end.getMonth() + 1)}/${String(
      end.getFullYear(),
    ).slice(-2)}`;
    return `${tp("dateRangeFrom")} ${startLabel} ${tp("dateRangeTo")} ${endLabel}`;
  }, [sejour.dateDebut, sejour.dateFin, tp]);

  const villageLabel = village
    ? village.vtfCity &&
      village.vtfCity.trim().toLowerCase() !== village.nom.trim().toLowerCase()
      ? `${village.nom} ${village.vtfCity}`
      : village.nom
    : "";

  const subtitle = villageLabel
    ? [villageLabel, dateRangeLabel].filter(Boolean).join(" ")
    : td("planning.stayFallback");

  const [open, setOpen] = React.useState(false);
  const [openStates, setOpenStates] = React.useState<Record<string, boolean>>(
    {},
  );

  const toggleDay = (key: string) => {
    setOpenStates((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const planning = React.useMemo(
    () => sejour.planning ?? {},
    [sejour.planning],
  );
  const keys = React.useMemo(() => {
    if (isEditable) return days.map((d) => d.key);
    if (days.length) return days.map((d) => d.key);
    return Object.keys(planning).sort();
  }, [isEditable, days, planning]);

  const slots: SlotDef[] = React.useMemo(
    () => [
      {
        key: "matin",
        label: t("simulateur.planning.slotMorning"),
        icon: (
          <WbSunnyRoundedIcon
            sx={{ fontSize: "var(--vtf-font-md)", color: "#f59e0b" }}
          />
        ),
      },
      {
        key: "aprem",
        label: t("simulateur.planning.slotAfternoon"),
        icon: (
          <LightModeRoundedIcon
            sx={{ fontSize: "var(--vtf-font-md)", color: "#0ea5e9" }}
          />
        ),
      },
      {
        key: "soir",
        label: t("simulateur.planning.slotEvening"),
        icon: (
          <NightsStayRoundedIcon
            sx={{ fontSize: "var(--vtf-font-md)", color: "#6366f1" }}
          />
        ),
      },
    ],
    [t],
  );

  const content = (
    <Box sx={{ mt: 1.5 }}>
      {!keys.length ? (
        <Typography sx={RECAP_META.bodyMuted}>
          {td("planning.empty")}
        </Typography>
      ) : (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25 }}>
          {keys.map((k) => {
            const day = planning[k] ?? emptyDaySlots();
            const dayCount =
              (day.matin?.length ?? 0) +
              (day.aprem?.length ?? 0) +
              (day.soir?.length ?? 0);
            const isDayOpen = isEditable ? (openStates[k] ?? true) : true;

            return (
              <Box
                key={k}
                sx={{
                  borderRadius: 3,
                  border: "1px solid rgba(15,23,42,0.10)",
                  bgcolor: "rgba(255,255,255,0.75)",
                  overflow: "hidden",
                }}
              >
                <Box
                  onClick={() => isEditable && toggleDay(k)}
                  sx={{
                    px: 2,
                    py: 1.25,
                    bgcolor: isDayOpen
                      ? "rgba(var(--vtf-navy-rgb), 0.04)"
                      : "transparent",
                    color: "var(--vtf-navy)",
                    borderBottom: isDayOpen
                      ? "1px solid rgba(15,23,42,0.08)"
                      : "0px solid transparent",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    cursor: isEditable ? "pointer" : "default",
                    transition: "all 0.2s ease",
                    "&:hover": {
                      bgcolor: "rgba(var(--vtf-navy-rgb), 0.06)",
                    },
                  }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <Typography
                      sx={{ fontSize: "var(--vtf-font-sm)", fontWeight: 950 }}
                    >
                      {(() => {
                        const d = days.find((day) => day.key === k);
                        if (d && d.index) {
                          const pattern = d.isDeparture
                            ? t("simulateur.planning.dayDeparture")
                            : t("simulateur.planning.dayLabel");
                          return pattern.replace("{{index}}", String(d.index));
                        }
                        return k;
                      })()}{" "}
                      · {formatPlanningDayLabel(k, intlLocale)}
                    </Typography>

                    {isEditable && dayHint && (
                      <Typography sx={RECAP_META.bodyMuted}>
                        - {dayHint}
                      </Typography>
                    )}
                  </Box>

                  {isEditable && (
                    <Box
                      sx={{ display: "flex", alignItems: "center", gap: 1.5 }}
                    >
                      <Pill
                        size="small"
                        label={resolvedItemsPillLabel(dayCount)}
                        vtfTone="softTeal"
                        sx={{
                          fontSize: "var(--vtf-font-xs)",
                          fontWeight: 950,
                          height: "auto",
                          py: 0.25,
                          px: 1,
                          border: "1px solid rgba(var(--vtf-teal-rgb), 0.15)",
                        }}
                      />
                      {isDayOpen ? (
                        <KeyboardArrowUpRoundedIcon
                          sx={{
                            color: "var(--vtf-navy)",
                            fontSize: "var(--vtf-font-lg)",
                          }}
                        />
                      ) : (
                        <KeyboardArrowDownRoundedIcon
                          sx={{
                            color: "var(--vtf-navy)",
                            fontSize: "var(--vtf-font-lg)",
                          }}
                        />
                      )}
                    </Box>
                  )}
                </Box>

                {!isDayOpen ? null : (
                  <Box
                    sx={{
                      bgcolor: isEditable
                        ? "rgba(255,255,255,0.4)"
                        : "transparent",
                    }}
                  >
                    {slots.map((slot) => {
                      const items = day[slot.key] ?? [];
                      return (
                        <Box
                          key={slot.key}
                          sx={{
                            px: 2,
                            py: 1,
                            borderTop: "1px solid rgba(15,23,42,0.08)",
                            display: "grid",
                            gridTemplateColumns: isEditable
                              ? {
                                  xs: "1fr",
                                  sm: "auto minmax(0, 1fr) auto",
                                }
                              : {
                                  xs: "1fr",
                                  sm: "auto minmax(0, 1fr)",
                                },
                            gap: 1.25,
                            alignItems: "center",
                          }}
                        >
                          <Typography
                            component="div"
                            sx={{
                              ...RECAP_TYPO.tagline,
                              color:
                                "color-mix(in srgb, var(--vtf-navy) 70%, transparent)",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 1.25,
                              flexShrink: 0,
                              whiteSpace: "nowrap",
                            }}
                          >
                            <Box
                              sx={{
                                display: "flex",
                                alignItems: "center",
                                opacity: 0.85,
                              }}
                            >
                              {slot.icon}
                            </Box>
                            {slot.label}
                          </Typography>
                          <Box
                            sx={{
                              display: "flex",
                              gap: 1,
                              flexWrap: "wrap",
                              alignItems: "center",
                              minWidth: 0,
                            }}
                          >
                            {items.length ? (
                              items.map((it, idx) => (
                                <Box
                                  key={`${planningItemKey(it)}:${idx}`}
                                  sx={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: 1,
                                    px: 1.25,
                                    py: 0.5,
                                    borderRadius: "10px",
                                    bgcolor: "rgba(255, 255, 255, 0.9)",
                                    border: "1px solid rgba(15, 23, 42, 0.12)",
                                    boxShadow:
                                      "0 2px 8px rgba(0, 68, 90, 0.04)",
                                    transition: isEditable
                                      ? "all 0.2s ease"
                                      : "none",
                                    "&:hover": isEditable
                                      ? {
                                          borderColor:
                                            "rgba(var(--vtf-orange-rgb), 0.4)",
                                          transform: "translateY(-1px)",
                                        }
                                      : {},
                                  }}
                                >
                                  <Box
                                    component="span"
                                    sx={{
                                      display: "flex",
                                      alignItems: "center",
                                      opacity: 0.85,
                                    }}
                                  >
                                    {it.icon}
                                  </Box>
                                  <Typography sx={RECAP_META.body}>
                                    {it.label}
                                  </Typography>
                                  {isEditable && (
                                    <Button
                                      vtfVariant="iconRemove"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        onRemoveItem?.(k, slot.key, idx);
                                      }}
                                      aria-label={resolvedRemoveAriaLabel}
                                      sx={{
                                        minWidth: 22,
                                        width: 22,
                                        height: 22,
                                        borderRadius: "9px",
                                        fontSize: "var(--vtf-font-sm)",
                                        ml: 0.25,
                                      }}
                                    >
                                      ×
                                    </Button>
                                  )}
                                </Box>
                              ))
                            ) : (
                              <Typography
                                sx={{
                                  ...RECAP_META.caption,
                                  fontStyle: "italic",
                                }}
                              >
                                {resolvedEmptySlotLabel}
                              </Typography>
                            )}
                          </Box>

                          {isEditable && (
                            <Box
                              onClick={(e) => e.stopPropagation()}
                              sx={{
                                display: "flex",
                                gap: 1,
                                alignItems: "center",
                                justifyContent: {
                                  xs: "flex-start",
                                  sm: "flex-end",
                                },
                                flexShrink: 0,
                              }}
                            >
                              <PlanningSlotAddSelect
                                groups={groups}
                                getStats={getStats}
                                addPlaceholder={tp("addSelectPlaceholder")}
                                selectWidth={140}
                                onAdd={(it) => onAddItem?.(k, slot.key, it)}
                              />
                            </Box>
                          )}
                        </Box>
                      );
                    })}
                  </Box>
                )}
              </Box>
            );
          })}
        </Box>
      )}
    </Box>
  );

  if (isEditable) {
    return content;
  }

  return (
    <VtfGlassCard glassSx={{ p: { xs: 2.5, sm: 3 } }}>
      <Box
        onClick={() => setOpen((v) => !v)}
        sx={{ cursor: "pointer", "&:hover": { opacity: 0.9 } }}
      >
        <VtfSectionHeading
          title={td("planning.title")}
          subtitle={subtitle}
          icon={<EventNoteRoundedIcon />}
          accent="navy"
          mb={open ? 2 : 0}
          rightSlot={
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography
                sx={{
                  ...RECAP_TYPO.tagline,
                  textTransform: "uppercase",
                  letterSpacing: "0.02em",
                  display: { xs: "none", sm: "block" },
                }}
              >
                {open ? td("planning.hide") : td("planning.show")}
              </Typography>
              {open ? (
                <KeyboardArrowUpRoundedIcon
                  sx={{
                    color: "var(--vtf-navy)",
                    fontSize: "var(--vtf-font-lg)",
                  }}
                />
              ) : (
                <KeyboardArrowDownRoundedIcon
                  sx={{
                    color: "var(--vtf-navy)",
                    fontSize: "var(--vtf-font-lg)",
                  }}
                />
              )}
            </Box>
          }
        />
      </Box>

      {open && content}
    </VtfGlassCard>
  );
}
