import * as React from "react";

import { Box, Button, Pill, Typography } from "../../ui";
import type { PlanningItem, PlanningSlotKey } from "../../../types/stayTab";
import {
  emptyDaySlots,
  formatPlanningDayLabel,
  planningItemKey,
} from "../../../utils/planningTab";
import { PlanningSlotAddSelect } from "./PlanningSlotAddSelect";
import WbSunnyRoundedIcon from "@mui/icons-material/WbSunnyRounded";
import LightModeRoundedIcon from "@mui/icons-material/LightModeRounded";
import NightsStayRoundedIcon from "@mui/icons-material/NightsStayRounded";
import { useTranslation } from "../../../contexts/LanguageContext";

export function PlanningScheduleCard({
  days,
  planning,
  slotLabels,
  emptySlotLabel,
  removeAriaLabel,
  dayHint,
  itemsPillLabel,
  addSelectPlaceholder,
  groups,
  getStats,
  onRemoveItem,
  onAddItem,
}: {
  days: { key: string; label: string; index: number; isDeparture: boolean }[];
  planning: Record<
    string,
    { matin?: PlanningItem[]; aprem?: PlanningItem[]; soir?: PlanningItem[] }
  >;
  slotLabels: { morning: string; afternoon: string; evening: string };
  emptySlotLabel: string;
  removeAriaLabel: string;
  dayHint: string;
  itemsPillLabel: (n: number) => string;
  addSelectPlaceholder: string;
  groups: {
    key: string;
    title: string;
    icon: React.ReactNode;
    items: PlanningItem[];
  }[];
  getStats: (
    it: PlanningItem,
  ) => { remaining: number; total: number; placed: number } | null;
  onRemoveItem: (dayKey: string, slot: PlanningSlotKey, idx: number) => void;
  onAddItem: (dayKey: string, slot: PlanningSlotKey, it: PlanningItem) => void;
}) {
  const { t } = useTranslation();
  const slots: {
    key: PlanningSlotKey;
    label: string;
    icon: React.ReactNode;
  }[] = React.useMemo(
    () => [
      {
        key: "matin",
        label: slotLabels.morning,
        icon: (
          <WbSunnyRoundedIcon
            sx={{ fontSize: "var(--vtf-font-lg)", color: "#f59e0b" }}
          />
        ),
      },
      {
        key: "aprem",
        label: slotLabels.afternoon,
        icon: (
          <LightModeRoundedIcon
            sx={{ fontSize: "var(--vtf-font-lg)", color: "#0ea5e9" }}
          />
        ),
      },
      {
        key: "soir",
        label: slotLabels.evening,
        icon: (
          <NightsStayRoundedIcon
            sx={{ fontSize: "var(--vtf-font-lg)", color: "#6366f1" }}
          />
        ),
      },
    ],
    [slotLabels],
  );

  return (
    <Box sx={{ mt: 2, display: "flex", flexDirection: "column", gap: 1.5 }}>
      {days.map((d) => {
        const day = planning[d.key] ?? emptyDaySlots();
        const dayCount =
          (day.matin?.length ?? 0) +
          (day.aprem?.length ?? 0) +
          (day.soir?.length ?? 0);
        return (
          <Box
            key={d.key}
            sx={{
              borderRadius: 4,
              border: "1px solid rgba(15,23,42,0.12)",
              bgcolor: "rgba(255,255,255,0.65)",
              overflow: "hidden",
              transition: "all 0.3s ease",
              "&:hover": {
                borderColor: "rgba(var(--vtf-teal-rgb), 0.25)",
                boxShadow: "0 10px 30px rgba(2, 8, 23, 0.04)",
              },
            }}
          >
            <Box
              sx={{
                px: 2.25,
                py: 1.5,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 2,
                bgcolor: "rgba(var(--vtf-navy-rgb), 0.04)",
                borderBottom: "1px solid rgba(15,23,42,0.06)",
              }}
            >
              <Box sx={{ minWidth: 0 }}>
                <Typography
                  sx={{
                    fontSize: "var(--vtf-font-sm)",
                    fontWeight: 950,
                    color: "var(--vtf-navy)",
                    letterSpacing: "-0.01em",
                  }}
                >
                  {(() => {
                    const pattern = d.isDeparture
                      ? t("simulateur.planning.dayDeparture")
                      : t("simulateur.planning.dayLabel");
                    return pattern.replace("{{index}}", String(d.index));
                  })()}{" "}
                  · {formatPlanningDayLabel(d.key)}
                </Typography>
                <Typography
                  sx={{
                    fontSize: "var(--vtf-font-sm)",
                    fontWeight: 800,
                    color: "rgba(0,68,90,0.65)",
                    mt: 0.25,
                  }}
                >
                  {dayHint}
                </Typography>
              </Box>
              <Pill
                size="small"
                label={itemsPillLabel(dayCount)}
                vtfTone="softTeal"
                sx={{
                  fontSize: "var(--vtf-font-sm)",
                  fontWeight: 950,
                  height: "auto",
                  py: 0.35,
                  px: 1.25,
                  border: "1px solid rgba(var(--vtf-teal-rgb), 0.22)",
                  boxShadow: "0 2px 6px rgba(0, 168, 181, 0.08)",
                }}
              />
            </Box>

            {slots.map((slot) => {
              const slotItems = day[slot.key] ?? [];
              return (
                <Box
                  key={slot.key}
                  sx={{
                    px: 2,
                    py: 1.25,
                    borderTop: "1px solid rgba(15,23,42,0.08)",
                    display: "grid",
                    gridTemplateColumns: {
                      xs: "1fr",
                      sm: "auto minmax(0, 1fr) auto",
                    },
                    gap: 1.5,
                    alignItems: "center",
                  }}
                >
                  <Box
                    sx={{
                      display: "flex",
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
                    <Typography
                      sx={{
                        fontSize: "var(--vtf-font-sm)",
                        fontWeight: 950,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        color: "rgba(0,68,90,0.70)",
                      }}
                    >
                      {slot.label}
                    </Typography>
                  </Box>

                  <Box
                    sx={{
                      display: "flex",
                      gap: 1,
                      flexWrap: "wrap",
                      alignItems: "center",
                      minWidth: 0,
                    }}
                  >
                    {slotItems.length === 0 ? (
                      <Typography
                        sx={{
                          fontSize: "var(--vtf-font-sm)",
                          color: "rgba(0,68,90,0.55)",
                          fontWeight: 700,
                        }}
                      >
                        {emptySlotLabel}
                      </Typography>
                    ) : (
                      slotItems.map((it, idx) => (
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
                            boxShadow: "0 2px 8px rgba(0, 68, 90, 0.04)",
                            transition: "all 0.2s ease",
                            "&:hover": {
                              borderColor: "rgba(var(--vtf-orange-rgb), 0.4)",
                              transform: "translateY(-1px)",
                            },
                          }}
                        >
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              opacity: 0.85,
                            }}
                          >
                            {it.icon}
                          </Box>
                          <Typography
                            sx={{
                              fontSize: "var(--vtf-font-sm)",
                              fontWeight: 950,
                              color: "var(--vtf-navy)",
                            }}
                          >
                            {it.label}
                          </Typography>
                          <Button
                            vtfVariant="iconRemove"
                            onClick={() => onRemoveItem(d.key, slot.key, idx)}
                            aria-label={removeAriaLabel}
                            sx={{
                              minWidth: 22,
                              width: 22,
                              height: 22,
                              borderRadius: "9px",
                              fontSize: "var(--vtf-font-sm)",
                            }}
                          >
                            ×
                          </Button>
                        </Box>
                      ))
                    )}
                  </Box>

                  <Box
                    sx={{
                      display: "flex",
                      gap: 1,
                      alignItems: "center",
                      justifyContent: { xs: "flex-start", sm: "flex-end" },
                      flexShrink: 0,
                    }}
                  >
                    <PlanningSlotAddSelect
                      groups={groups}
                      getStats={getStats}
                      addPlaceholder={addSelectPlaceholder}
                      onAdd={(it) => onAddItem(d.key, slot.key, it)}
                    />
                  </Box>
                </Box>
              );
            })}
          </Box>
        );
      })}
    </Box>
  );
}
