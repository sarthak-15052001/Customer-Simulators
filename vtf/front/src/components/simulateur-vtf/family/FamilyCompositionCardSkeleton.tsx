import { Box, Skeleton } from "../../ui";
import { VtfGlassCard } from "../../shared/VtfGlassCard";

/** Full-card skeleton for FamilyCompositionCard while pricingRules API loads. */
export function FamilyCompositionCardSkeleton() {
  return (
    <VtfGlassCard>
      {/* Header row */}
      <Box className="mb-3 flex items-center justify-between">
        <Box className="flex items-center gap-2">
          <Skeleton
            variant="rounded"
            width={24}
            height={24}
            sx={{ borderRadius: "8px" }}
          />
          <Skeleton variant="text" width={140} height={18} />
        </Box>
        <Skeleton
          variant="rounded"
          width={72}
          height={22}
          sx={{ borderRadius: "16px" }}
        />
      </Box>

      {/* Grid: Adults + Children */}
      <Box className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Adults block */}
        <Box>
          <Skeleton variant="text" width={60} height={14} sx={{ mb: 1 }} />
          <Skeleton
            variant="rounded"
            width={120}
            height={40}
            sx={{ borderRadius: "12px" }}
          />
        </Box>

        {/* Children block */}
        <Box>
          <Box className="mb-2 flex items-center justify-between">
            <Skeleton variant="text" width={70} height={14} />
            <Skeleton
              variant="rounded"
              width={96}
              height={32}
              sx={{ borderRadius: "20px" }}
            />
          </Box>
          <Box className="rounded-xl border border-slate-200/70 bg-slate-50/70 p-2 flex flex-col gap-2">
            {[0, 1].map((i) => (
              <Box
                key={i}
                className="flex items-center gap-3 rounded-xl bg-white/80 p-2"
              >
                <Skeleton variant="circular" width={24} height={24} />
                <Skeleton
                  variant="rounded"
                  width="100%"
                  height={34}
                  sx={{ borderRadius: "8px", flex: 1 }}
                />
                <Skeleton
                  variant="rounded"
                  width={52}
                  height={22}
                  sx={{ borderRadius: "16px" }}
                />
                <Skeleton variant="circular" width={24} height={24} />
              </Box>
            ))}
          </Box>
        </Box>
      </Box>

      {/* Tip notice */}
      <Box
        sx={{
          mt: 3,
          p: 1.5,
          borderRadius: "12px",
          bgcolor: "rgba(0, 180, 160, 0.05)",
          border: "1px solid rgba(0, 180, 160, 0.12)",
          display: "flex",
          gap: 1.5,
        }}
      >
        <Skeleton variant="text" width={14} height={14} />
        <Skeleton variant="text" width="85%" height={14} />
      </Box>
    </VtfGlassCard>
  );
}
