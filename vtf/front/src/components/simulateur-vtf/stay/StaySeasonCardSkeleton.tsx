import { Box, Skeleton } from "../../ui";
import { VtfGlassCard } from "../../shared/VtfGlassCard";

export function StaySeasonCardSkeleton() {
  return (
    <VtfGlassCard>
      <Box className="flex items-center justify-between gap-2 mb-4">
        <Box className="flex items-center gap-2">
          <Skeleton variant="rounded" width={32} height={32} sx={{ borderRadius: "16px" }} />
          <Skeleton variant="text" width={140} height={18} />
        </Box>
        <Box className="hidden sm:flex items-center shrink-0">
          <Skeleton variant="rounded" width={80} height={22} sx={{ borderRadius: "16px" }} />
        </Box>
      </Box>

      <Box className="grid grid-cols-2 gap-3">
        {[0, 1, 2, 3].map((i) => (
          <Box
            key={i}
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 0.5,
              bgcolor: "rgba(255,255,255,0.45)",
              border: "1px solid rgba(15, 23, 42, 0.05)",
              borderRadius: "20px",
              p: 2,
            }}
          >
            <Skeleton
              variant="rounded"
              width={44}
              height={44}
              sx={{ borderRadius: "16px", mb: 1.25 }}
            />
            <Skeleton variant="text" width={70} height={14} />
            <Skeleton variant="text" width={100} height={10} sx={{ mt: 0.75 }} />
          </Box>
        ))}
      </Box>
    </VtfGlassCard>
  );
}
