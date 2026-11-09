import type { ReactNode } from "react";
import { Box, Skeleton } from "../../ui";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { RECAP_SURFACE } from "./recapCard.ui";

const PAD = { p: { xs: 2.5, sm: 3 } };
const METRICS = ["family", "stay", "formula", "budget"] as const;
const BAR_W = [42, 28, 18, 12];

function Sk({
  w,
  h,
  sx,
}: {
  w?: number | string;
  h: number;
  sx?: object;
}) {
  return <Skeleton width={w} height={h} sx={{ borderRadius: 1, ...sx }} />;
}

function Head({ mb = 2 }: { mb?: number }) {
  return (
    <Box sx={{ display: "flex", gap: 1.25, mb }}>
      <Skeleton variant="rounded" width={40} height={40} sx={{ borderRadius: 14 }} />
      <Sk w="38%" h={18} />
    </Box>
  );
}

function Glass({ children }: { children: ReactNode }) {
  return <VtfGlassCard glassSx={PAD}>{children}</VtfGlassCard>;
}

function RecapBlock() {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.25 }}>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
          gap: 1.25,
        }}
      >
        {METRICS.map((k) => (
          <Box
            key={k}
            sx={{
              p: 1.5,
              borderRadius: 2.5,
              bgcolor: RECAP_SURFACE.metric[k].bg,
              border: `1px solid ${RECAP_SURFACE.metric[k].border}`,
            }}
          >
            <Box sx={{ display: "flex", gap: 1, mb: 1 }}>
              <Skeleton variant="rounded" width={32} height={32} sx={{ borderRadius: 2 }} />
              <Sk w="50%" h={11} />
            </Box>
            <Sk w="75%" h={15} sx={{ mb: 0.5 }} />
            <Sk w="88%" h={11} />
          </Box>
        ))}
      </Box>
      <Box
        sx={{
          p: { xs: 1.25, sm: 1.5 },
          borderRadius: 2,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          bgcolor: RECAP_SURFACE.total.bg,
          border: `1px solid ${RECAP_SURFACE.total.border}`,
        }}
      >
        <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
          <Skeleton variant="rounded" width={40} height={40} sx={{ borderRadius: 14 }} />
          <Sk w={120} h={16} />
        </Box>
        <Sk w={72} h={24} />
      </Box>
    </Box>
  );
}

function BarsBlock() {
  return (
    <Glass>
      <Head />
      <Sk w="65%" h={10} sx={{ mb: 1 }} />
      {BAR_W.map((pct, i) => (
        <Box key={i} sx={{ mt: i ? 1.75 : 0 }}>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1, px: 0.5 }}>
            <Sk w="38%" h={14} />
            <Sk w={52} h={14} />
          </Box>
          <Box sx={{ height: 12, borderRadius: 99, bgcolor: "rgba(15,23,42,0.06)", overflow: "hidden" }}>
            <Skeleton height="100%" sx={{ width: `${pct}%`, borderRadius: 99 }} />
          </Box>
        </Box>
      ))}
    </Glass>
  );
}

function ComparatorBlock() {
  return (
    <Glass>
      <Head />
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", sm: "1fr auto 1fr" },
          gap: 2,
          alignItems: "center",
          mb: 2,
        }}
      >
        <Skeleton variant="rounded" height={118} sx={{ borderRadius: 4 }} />
        <Sk w={24} h={14} sx={{ mx: "auto" }} />
        <Skeleton variant="rounded" height={118} sx={{ borderRadius: 4 }} />
      </Box>
      <Skeleton variant="rounded" height={84} sx={{ borderRadius: 4 }} />
    </Glass>
  );
}

function PlanningBlock() {
  return (
    <Glass>
      <Head mb={1.5} />
      {[0, 1].map((i) => (
        <Skeleton
          key={i}
          variant="rounded"
          height={i === 0 ? 108 : 52}
          sx={{ mb: 1.25, borderRadius: 3 }}
        />
      ))}
    </Glass>
  );
}

function CtaBlock() {
  return (
    <VtfGlassCard glassSx={{ ...PAD, textAlign: "center", borderRadius: 3 }}>
      <Sk w={100} h={10} sx={{ mx: "auto", mb: 1 }} />
      <Sk w="55%" h={24} sx={{ mx: "auto", mb: 1.25 }} />
      <Sk w={180} h={28} sx={{ mx: "auto", mb: 2, borderRadius: 99 }} />
      <Skeleton variant="rounded" height={48} sx={{ maxWidth: 320, mx: "auto", mb: 2.5, borderRadius: 14 }} />
      <Sk w={140} h={10} sx={{ mx: "auto", mb: 1.5 }} />
      <Box sx={{ display: "flex", justifyContent: "center", gap: 1.5 }}>
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} variant="circular" width={44} height={44} />
        ))}
      </Box>
    </VtfGlassCard>
  );
}

/** Details tab loading — same order as loaded content. */
export function DetailsTabSkeleton() {
  return (
    <Box
      role="status"
      aria-busy="true"
      sx={{ display: "flex", flexDirection: "column", gap: 3 }}
    >
      <RecapBlock />
      <BarsBlock />
      <ComparatorBlock />
      <PlanningBlock />
      <CtaBlock />
    </Box>
  );
}
