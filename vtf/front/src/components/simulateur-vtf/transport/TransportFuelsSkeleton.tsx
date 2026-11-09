import { Box, Skeleton } from "../../ui";

export function TransportFuelsSkeleton() {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        gap: 1.25,
        mt: 1.25,
      }}
    >
      {[1, 2].map((i) => (
        <Box
          key={i}
          sx={{
            display: "flex",
            alignItems: "center",
            px: 2,
            py: 1.25,
            minHeight: 52,
            borderRadius: "16px",
            border: "1px solid rgba(15, 23, 42, 0.08)",
            bgcolor: "white",
          }}
        >
          <Box sx={{ flex: 1 }}>
            <Skeleton width="40%" height={20} sx={{ borderRadius: 1 }} />
          </Box>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Skeleton
              variant="circular"
              width={20}
              height={20}
              sx={{ opacity: 0.6 }}
            />
          </Box>
        </Box>
      ))}
    </Box>
  );
}
