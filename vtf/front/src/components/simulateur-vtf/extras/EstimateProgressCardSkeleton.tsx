import { Box, Skeleton } from "../../ui";

const sk = {
  borderRadius: "8px",
  bgcolor: "rgba(255,255,255,0.6)",
  border: "1px solid rgba(0, 68, 90, 0.06)",
};

export function EstimateProgressCardSkeletonBody() {
  return (
    <>
      <Box
        sx={{
          display: "flex",
          alignItems: "baseline",
          gap: 1,
          flexWrap: "wrap",
        }}
      >
        <Skeleton
          animation="pulse"
          variant="rounded"
          sx={{ ...sk, width: 112, height: 26 }}
        />
        <Skeleton
          animation="pulse"
          variant="rounded"
          sx={{ ...sk, width: 72, height: 12 }}
        />
      </Box>
      <Box
        sx={{
          mt: 1,
          pt: 1,
          borderTop: "1px solid rgba(0, 68, 90, 0.08)",
          display: "flex",
          flexDirection: "column",
          gap: 0.5,
        }}
      >
        {[0, 1].map((i) => (
          <Box
            key={i}
            sx={{ display: "flex", justifyContent: "space-between", gap: 1 }}
          >
            <Skeleton
              animation="pulse"
              variant="rounded"
              sx={{ ...sk, flex: 1, maxWidth: 120, height: 10 }}
            />
            <Skeleton
              animation="pulse"
              variant="rounded"
              sx={{ ...sk, width: 44, height: 10, flexShrink: 0 }}
            />
          </Box>
        ))}
      </Box>
    </>
  );
}
