import { Box, Skeleton } from "../../ui";

export function PlanningScheduleSkeleton({
  dayCount = 3,
}: {
  dayCount?: number;
}) {
  const rows = Math.min(Math.max(dayCount, 2), 5);
  return (
    <Box sx={{ mt: 2, display: "flex", flexDirection: "column", gap: 1.5 }}>
      {Array.from({ length: rows }, (_, i) => (
        <Box
          key={i}
          sx={{
            borderRadius: 4,
            border: "1px solid rgba(15,23,42,0.10)",
            bgcolor: "rgba(255,255,255,0.65)",
            overflow: "hidden",
          }}
        >
          <Box
            sx={{
              px: 2.25,
              py: 1.5,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              bgcolor: "rgba(var(--vtf-navy-rgb), 0.04)",
            }}
          >
            <Skeleton width="45%" height={18} sx={{ borderRadius: 1 }} />
            <Skeleton width={72} height={22} sx={{ borderRadius: 99 }} />
          </Box>
          <Box
            sx={{ p: 2, display: "flex", flexDirection: "column", gap: 1.25 }}
          >
            {[1, 2, 3].map((slot) => (
              <Box
                key={slot}
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 2,
                }}
              >
                <Skeleton width={80} height={16} sx={{ borderRadius: 1 }} />
                <Skeleton width={120} height={32} sx={{ borderRadius: 2 }} />
              </Box>
            ))}
          </Box>
        </Box>
      ))}
    </Box>
  );
}
