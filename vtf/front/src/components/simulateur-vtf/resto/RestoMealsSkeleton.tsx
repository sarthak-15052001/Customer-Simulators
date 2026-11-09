import { Box, Skeleton } from "../../ui";

export function RestoMealsSkeleton() {
  return (
    <Box sx={{ mt: 1.25, display: "flex", flexDirection: "column", gap: 1 }}>
      {[1, 2, 3].map((i) => (
        <Box
          key={i}
          sx={{
            display: "flex",
            alignItems: "center",
            px: { xs: 1.25, sm: 1.5 },
            py: 1.15,
            minHeight: { xs: 72, sm: 64 },
            borderRadius: "16px",
            border: "1px solid rgba(15, 23, 42, 0.07)",
            bgcolor: "white",
          }}
        >
          <Box sx={{ flex: 1, pr: { xs: 'var(--vtf-font-sm)', sm: 'var(--vtf-font-md)' } }}>
            <Skeleton width="60%" height={20} sx={{ borderRadius: 1 }} />
            <Skeleton
              width="40%"
              height={14}
              sx={{ mt: 0.5, borderRadius: 1 }}
            />
          </Box>
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              minWidth: 48,
              gap: 0.5,
            }}
          >
            <Skeleton width={32} height={18} sx={{ borderRadius: 1 }} />
            <Skeleton width={40} height={12} sx={{ borderRadius: 1 }} />
          </Box>
          <Box sx={{ ml: "auto", pl: 2 }}>
            <Skeleton
              variant="rectangular"
              width={100}
              height={32}
              sx={{ borderRadius: 2 }}
            />
          </Box>
        </Box>
      ))}
    </Box>
  );
}
