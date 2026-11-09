import { Box, Skeleton } from "../../ui";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { StayEnvironmentSkeleton } from "./StayEnvironmentSkeleton";

export function StaySeasonDetailsSkeleton() {
  return (
    <>
      <VtfGlassCard glassSx={{ mt: 0 }}>
        <Box className="flex items-center gap-2 mb-4">
          <Skeleton
            variant="rounded"
            width={32}
            height={32}
            sx={{ borderRadius: "16px" }}
          />
          <Skeleton variant="text" width={160} height={18} />
        </Box>
        <Skeleton
          variant="rounded"
          width="100%"
          height={44}
          sx={{ borderRadius: "16px", mb: 2 }}
        />
        <Box className="flex flex-wrap gap-2 mb-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton
              key={i}
              variant="rounded"
              width={56}
              height={32}
              sx={{ borderRadius: "12px" }}
            />
          ))}
        </Box>
        <Box className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Skeleton
            variant="rounded"
            height={48}
            sx={{ borderRadius: "14px" }}
          />
          <Skeleton
            variant="rounded"
            height={48}
            sx={{ borderRadius: "14px" }}
          />
        </Box>
      </VtfGlassCard>
      <StayEnvironmentSkeleton />
    </>
  );
}
