import { Box, Skeleton } from "../../ui";

type StayFormulePickerSkeletonProps = {
  count?: number;
  mobileScroll?: boolean;
  scrollGridFrom?: string;
};

export function StayFormulePickerSkeleton({
  count = 3,
}: StayFormulePickerSkeletonProps) {
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: count <= 2 ? "repeat(2, 1fr)" : "repeat(3, 1fr)",
        gap: 1.5,
      }}
    >
      {Array.from({ length: count }, (_, i) => (
        <Box
          key={i}
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
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
  );
}
