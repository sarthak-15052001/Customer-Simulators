import { Box, Skeleton } from "../../ui";

function PromoCardSkeleton() {
  return (
    <Box
      sx={{
        display: "flex",
        gap: 1.5,
        p: 1.75,
        width: "100%",
        alignItems: "flex-start",
        borderRadius: 3,
        border: "1px solid rgba(15, 23, 42, 0.10)",
        bgcolor: "rgba(255, 255, 255, 0.55)",
      }}
    >
      <Skeleton
        variant="rounded"
        width={24}
        height={24}
        sx={{ borderRadius: 1, flexShrink: 0, mt: 0.15 }}
      />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 1,
          }}
        >
          <Skeleton width="55%" height={18} sx={{ borderRadius: 1 }} />
          <Skeleton
            width={44}
            height={22}
            sx={{ borderRadius: 99, flexShrink: 0 }}
          />
        </Box>
        <Skeleton width="85%" height={14} sx={{ mt: 0.75, borderRadius: 1 }} />
      </Box>
      <Skeleton
        variant="rounded"
        width={20}
        height={20}
        sx={{ borderRadius: 2, flexShrink: 0, mt: 0.15 }}
      />
    </Box>
  );
}

export function PromosStayPromosSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      {Array.from({ length: rows }, (_, i) => (
        <PromoCardSkeleton key={i} />
      ))}
    </Box>
  );
}
