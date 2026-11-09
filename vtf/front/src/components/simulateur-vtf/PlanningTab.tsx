import * as React from "react";
import { Box, Pill, Typography } from "../ui";

import type { FamilyState } from "../../types/familyTab";
import type { VtfVillage } from "../../data/vtfStay";
import type {
  PlanningItem,
  PlanningSlotKey,
  SejourState,
} from "../../types/stayTab";
import type { VtfSeasonKey } from "../../data/vtfExtras";
import { useSimulateurTabTranslation } from "../../hooks/useSimulateurTabTranslation";
import { NoticeBox } from "../shared/NoticeBox";
import CalendarMonthRoundedIcon from "@mui/icons-material/CalendarMonthRounded";
import { VtfGlassCard } from "../shared/VtfGlassCard";
import { VtfSectionHeading } from "../shared/VtfSectionHeading";
import KeyboardArrowDownRoundedIcon from "@mui/icons-material/KeyboardArrowDownRounded";
import KeyboardArrowUpRoundedIcon from "@mui/icons-material/KeyboardArrowUpRounded";
import {
  emptyDaySlots,
  getStayDays,
} from "../../utils/planningTab";
// import { PlanningBannerCard } from "./planning/PlanningBannerCard";
import { PlanningScheduleCard } from "./planning/PlanningScheduleCard";
import { PlanningScheduleSkeleton } from "./planning/PlanningScheduleSkeleton";
import { useAnimations } from "../../hooks/animations.hooks";
import { useRegionActivities } from "../../hooks/regionActivities.hooks";
import { useMeals } from "../../hooks/meals.hooks";
import { saisonKeyFromSejour } from "../../utils/extrasTab";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import ExploreRoundedIcon from "@mui/icons-material/ExploreRounded";
import LocalActivityRoundedIcon from "@mui/icons-material/LocalActivityRounded";
import RestaurantRoundedIcon from "@mui/icons-material/RestaurantRounded";
import BeachAccessRoundedIcon from "@mui/icons-material/BeachAccessRounded";

type Props = {
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
  onChange: (next: SejourState) => void;
  onSkip?: () => void;
};

export function PlanningTab({ sejour, village, onChange }: Props) {
  const tp = useSimulateurTabTranslation("planning");

  const patch = React.useCallback(
    (partial: Partial<SejourState>) => onChange({ ...sejour, ...partial }),
    [onChange, sejour],
  );

  const days = React.useMemo(
    () => getStayDays(sejour.dateDebut, sejour.dateFin),
    [sejour.dateDebut, sejour.dateFin],
  );
  const planning = React.useMemo(
    () => sejour.planning ?? {},
    [sejour.planning],
  );
  const region = village?.region?.trim() || null;
  const saisonKey =
    ((sejour.serverSeasonKey as VtfSeasonKey) || saisonKeyFromSejour(sejour)) ??
    null;

  const { data: mealsData = [] } = useMeals();
  const { data: animationsData = [] } = useAnimations();

  const freeQuery = useRegionActivities(region, {
    kind: "free",
    season: saisonKey,
  });
  const paidQuery = useRegionActivities(region, {
    kind: "paid",
    season: saisonKey,
  });
  const isPickerLoading =
    !!region && (freeQuery.isLoading || paidQuery.isLoading);

  const freeList = React.useMemo(() => {
    if (!region || !freeQuery.data) return [];
    return freeQuery.data.map((a) => ({ id: a.id, nom: a.nom, type: a.type }));
  }, [region, freeQuery.data]);

  const paidList = React.useMemo(() => {
    if (!region || !paidQuery.data) return [];
    return paidQuery.data
      .filter(
        (a) => !a.saisons?.length || a.saisons.includes(saisonKey ?? "ete"),
      )
      .map((a) => ({
        id: a.id,
        nom: a.nom,
        type: a.type,
        ad: a.ad,
        enf: a.enf,
      }));
  }, [region, paidQuery.data, saisonKey]);

  const pickerGroups = React.useMemo(() => {
    const includes: PlanningItem[] = animationsData.length
      ? animationsData.map((a) => ({
          label: a.nom,
          cat: "vtf" as const,
          icon: (
            <CheckCircleRoundedIcon
              sx={{ fontSize: 'var(--vtf-font-md)', color: "var(--vtf-teal)" }}
            />
          ),
          prix: 0,
        }))
      : [
          {
            label: tp("vtfKidsClubs"),
            cat: "vtf" as const,
            icon: (
              <CheckCircleRoundedIcon
                sx={{ fontSize: 'var(--vtf-font-md)', color: "var(--vtf-teal)" }}
              />
            ),
            prix: 0,
          },
          {
            label: tp("vtfDayAnim"),
            cat: "vtf" as const,
            icon: (
              <CheckCircleRoundedIcon
                sx={{ fontSize: 'var(--vtf-font-md)', color: "var(--vtf-teal)" }}
              />
            ),
            prix: 0,
          },
          {
            label: tp("vtfEvening"),
            cat: "vtf" as const,
            icon: (
              <CheckCircleRoundedIcon
                sx={{ fontSize: 'var(--vtf-font-md)', color: "var(--vtf-teal)" }}
              />
            ),
            prix: 0,
          },
          {
            label: tp("vtfHike"),
            cat: "vtf" as const,
            icon: (
              <CheckCircleRoundedIcon
                sx={{ fontSize: 'var(--vtf-font-md)', color: "var(--vtf-teal)" }}
              />
            ),
            prix: 0,
          },
        ];

    const free: PlanningItem[] = freeList.slice(0, 30).map((a) => ({
      label: `${a.type} ${a.nom}`,
      cat: "free" as const,
      icon: (
        <ExploreRoundedIcon sx={{ fontSize: 'var(--vtf-font-md)', color: "var(--vtf-teal)" }} />
      ),
      sourceId: a.id,
      prix: 0,
    }));

    const paid: PlanningItem[] = paidList.slice(0, 30).map((a) => ({
      label: a.nom,
      cat: "paid" as const,
      icon: (
        <LocalActivityRoundedIcon
          sx={{ fontSize: 'var(--vtf-font-md)', color: "var(--vtf-orange)" }}
        />
      ),
      sourceId: a.id,
      prix: 0,
    }));

    const meal: PlanningItem[] = mealsData.map((m) => ({
      label: m.label,
      cat: "repas" as const,
      icon: (
        <RestaurantRoundedIcon
          sx={{ fontSize: 'var(--vtf-font-md)', color: "var(--vtf-navy)" }}
        />
      ),
      prix: 0,
      sourceId: m.id,
    }));

    const freeTime: PlanningItem[] = [
      {
        label: tp("freeTime"),
        cat: "libre" as const,
        icon: (
          <BeachAccessRoundedIcon sx={{ fontSize: 'var(--vtf-font-md)', color: "#0ea5e9" }} />
        ),
        prix: 0,
      },
    ];

    const groups = [
      {
        key: "includes" as const,
        title: tp("groupIncludes"),
        icon: <CheckCircleRoundedIcon />,
        items: includes,
      },
      {
        key: "free" as const,
        title: tp("groupFree"),
        icon: <ExploreRoundedIcon />,
        items: free,
      },
      {
        key: "paid" as const,
        title: tp("groupPaid"),
        icon: <LocalActivityRoundedIcon />,
        items: paid,
      },
      {
        key: "meal" as const,
        title: tp("groupMeal"),
        icon: <RestaurantRoundedIcon />,
        items: meal,
      },
      {
        key: "freeTime" as const,
        title: tp("groupFreeTime"),
        icon: <BeachAccessRoundedIcon />,
        items: freeTime,
      },
    ];

    return groups
      .map((g) => {
        if (g.key === "includes" || g.key === "freeTime") return g;

        const filteredItems = g.items.filter((it) => {
          if (!it.sourceId) return true;

          const extra = sejour.extraActivities;
          const resto = sejour.resto?.qtyByMealId;

          if (g.key === "free")
            return (extra?.freeQtyById?.[it.sourceId] ?? 0) > 0;
          if (g.key === "paid")
            return (extra?.paidQtyById?.[it.sourceId] ?? 0) > 0;
          if (g.key === "meal") {
            const mealId = it.sourceId as keyof typeof resto;
            return (resto?.[mealId] ?? 0) > 0;
          }
          return true;
        });

        return { ...g, items: filteredItems };
      })
      .filter((g) => g.items.length > 0);
  }, [
    animationsData,
    freeList,
    paidList,
    mealsData,
    tp,
    sejour.extraActivities,
    sejour.resto?.qtyByMealId,
  ]);

  const placedCountBySourceId = React.useMemo(() => {
    const map = new Map<string, number>();
    for (const day of Object.values(planning)) {
      for (const slot of [day?.matin, day?.aprem, day?.soir]) {
        for (const it of slot ?? []) {
          if (!it?.sourceId) continue;
          map.set(it.sourceId, (map.get(it.sourceId) ?? 0) + 1);
        }
      }
    }
    return map;
  }, [planning]);

  const getStatsForSourceId = React.useCallback(
    (sourceId: string, cat: PlanningItem["cat"]) => {
      const extra = sejour.extraActivities;
      const resto = sejour.resto?.qtyByMealId;

      let total = 0;
      if (cat === "free") total = extra?.freeQtyById?.[sourceId] ?? 0;
      else if (cat === "paid") total = extra?.paidQtyById?.[sourceId] ?? 0;
      else if (cat === "repas")
        total = resto?.[sourceId as keyof typeof resto] ?? 0;

      if (!total) return null;

      const placed = placedCountBySourceId.get(sourceId) ?? 0;
      return { remaining: Math.max(0, total - placed), total, placed };
    },
    [placedCountBySourceId, sejour.extraActivities, sejour.resto?.qtyByMealId],
  );

  const setDaySlot = (
    dayKey: string,
    slot: PlanningSlotKey,
    next: PlanningItem[],
  ) => {
    const nextPlanning = { ...planning };
    const existing = nextPlanning[dayKey] ?? emptyDaySlots();
    nextPlanning[dayKey] = { ...existing, [slot]: next };
    patch({ planning: nextPlanning });
  };

  const removeItem = (dayKey: string, slot: PlanningSlotKey, idx: number) => {
    const existing = planning[dayKey]?.[slot] ?? [];
    const next = existing.slice();
    next.splice(idx, 1);
    setDaySlot(dayKey, slot, next);
  };

  const addItem = (
    dayKey: string,
    slot: PlanningSlotKey,
    item: PlanningItem,
  ) => {
    const existing = planning[dayKey]?.[slot] ?? [];
    setDaySlot(dayKey, slot, existing.concat(item));
  };

  // const proposeDefault = React.useCallback(() => {
  //   if (!days.length) return;

  //   const freeTimeFromPicker = pickerGroups.find((g) => g.key === "freeTime")
  //     ?.items[0];
  //   const freeTimeFallback: PlanningItem = freeTimeFromPicker ?? {
  //     label: tp("freeTime"),
  //     cat: "libre",
  //     icon: (
  //       <BeachAccessRoundedIcon sx={{ fontSize: 'var(--vtf-font-md)', color: "#0ea5e9" }} />
  //     ),
  //     prix: 0,
  //   };

  //   patch({
  //     planning: buildDefaultPlanning({
  //       days,
  //       groups: pickerGroups,
  //       extra: sejour.extraActivities,
  //       restoQty: sejour.resto?.qtyByMealId,
  //       freeTimeFallback,
  //     }),
  //   });
  // }, [
  //   days,
  //   pickerGroups,
  //   patch,
  //   sejour.extraActivities,
  //   sejour.resto?.qtyByMealId,
  //   tp,
  // ]);

  const [isOpen, setIsOpen] = React.useState(false);

  if (!sejour.dateDebut || !sejour.dateFin) {
    return (
      <Box
  className="vtf-tab-stack"
  sx={{
    overflow: "hidden",
    height: isOpen ? "auto" : "fit-content",
  }}
>
        <VtfGlassCard
          title={tp("title")}
          subtitle={tp("subtitle")}
          headingIcon={<CalendarMonthRoundedIcon />}
          headingAccent="navy"
        >
          <NoticeBox tone="orange" dense>
            {tp("needDates")}
          </NoticeBox>
        </VtfGlassCard>
      </Box>
    );
  }

  return (
    <Box className="vtf-tab-stack">
      <VtfGlassCard glassSx={{ p: { xs: 2.5, sm: 3 } }}>
        <Box
          onClick={() => setIsOpen((v) => !v)}
          sx={{ cursor: "pointer", "&:hover": { opacity: 0.9 } }}
        >
          <VtfSectionHeading
            title={
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <span>{tp("title")}</span>
                {isOpen ? (
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
            subtitle={tp("subtitle")}
            icon={<CalendarMonthRoundedIcon />}
            accent="navy"
            mb={isOpen ? 2 : 0}
            rightSlot={
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Pill
                  size="small"
                  label={`${days.length} ${tp("daysPill")}`}
                  vtfTone="softNavy"
                  sx={{
                    fontSize: "var(--vtf-font-sm)",
                    fontWeight: 950,
                    height: "auto",
                    py: 0.25,
                    display: { xs: "none", sm: "flex" },
                  }}
                />
                <Typography
                  sx={{
                    fontSize: "0.85rem",
                    fontWeight: 800,
                    color: "rgba(0,68,90,0.65)",
                    textTransform: "uppercase",
                    letterSpacing: "0.02em",
                    display: { xs: "none", sm: "block" },
                    ml: 1,
                  }}
                >
                  {isOpen ? tp("hide") : tp("show")}
                </Typography>
              </Box>
            }
          />
        </Box>

        {isOpen && (
          <Box sx={{ mt: 1 }}>
            {isPickerLoading ? (
              <PlanningScheduleSkeleton dayCount={days.length} />
            ) : (
              <PlanningScheduleCard
                days={days}
                planning={planning}
                slotLabels={{
                  morning: tp("slotMorning"),
                  afternoon: tp("slotAfternoon"),
                  evening: tp("slotEvening"),
                }}
                emptySlotLabel={tp("emptySlot")}
                removeAriaLabel={tp("removeAria")}
                dayHint={tp("dayHint")}
                itemsPillLabel={(n) => `${n} ${tp("itemsPill")}`}
                addSelectPlaceholder={tp("addSelectPlaceholder")}
                groups={pickerGroups}
                getStats={(it) =>
                  it.sourceId ? getStatsForSourceId(it.sourceId, it.cat) : null
                }
                onRemoveItem={removeItem}
                onAddItem={addItem}
              />
            )}
          </Box>
        )}
      </VtfGlassCard>
    </Box>
  );
}
