import * as React from "react";
import { Box, VtfSelect } from "../../ui";
import type { Option } from "../../ui/Select";
import type { PlanningItem } from "../../../types/stayTab";
import {
  formatPlanningPickerLabel,
  planningItemKey,
} from "../../../utils/planningTab";
import { useTranslation } from "../../../contexts/LanguageContext";

export function PlanningSlotAddSelect({
  groups,
  getStats,
  onAdd,
  addPlaceholder,
  selectWidth = 180,
}: {
  groups: {
    key: string;
    title: string;
    icon: React.ReactNode;
    items: PlanningItem[];
  }[];
  getStats: (
    it: PlanningItem,
  ) => { remaining: number; total: number; placed: number } | null;
  onAdd: (it: PlanningItem) => void;
  addPlaceholder: string;
  selectWidth?: number;
}) {
  const { t } = useTranslation();
  const [value, setValue] = React.useState("");

  const { options, byValue } = React.useMemo(() => {
    const opts: Option[] = [];
    const map = new Map<string, PlanningItem>();

    for (const g of groups) {
      opts.push({
        value: `__hdr:${g.key}`,
        label: g.title,
        disabled: true,
        icon: g.icon,
      });

      for (const it of g.items) {
        const v = planningItemKey(it);
        const stats = getStats(it);
        const disabled = stats ? stats.remaining <= 0 : false;
        const label = formatPlanningPickerLabel(it.label, stats, t);
        opts.push({ value: v, label, disabled, icon: it.icon });
        map.set(v, it);
      }
    }

    return { options: opts, byValue: map };
  }, [getStats, groups, t]);

  const onChange = React.useCallback(
    (v: string) => {
      setValue(v);
      const it = byValue.get(v) ?? null;
      if (!it) return;
      onAdd(it);
      setValue("");
    },
    [byValue, onAdd],
  );

  return (
    <Box sx={{ display: "flex", alignItems: "center" }}>
      <VtfSelect
        className="vtf-select-age"
        options={options}
        value={value}
        onChange={onChange}
        ariaLabel={addPlaceholder}
        placeholder={addPlaceholder}
        width={selectWidth}
        menuWidth={280}
        showIcons
        variant="light"
        size="compact"
      />
    </Box>
  );
}
