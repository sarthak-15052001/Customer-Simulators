import { Box, Skeleton } from "../../ui";
import { Card, CardContent } from "../../ui";
import {
  vtfTransparentCardContentSx,
  vtfTransparentCardSx,
} from "../../ui/vtfCardPresets";

/** Full-card skeleton for FamilyQuotientCard while QF API call is pending. */
export function FamilyQuotientCardSkeleton() {
  return (
    <Card sx={vtfTransparentCardSx}>
      <CardContent sx={vtfTransparentCardContentSx}>
        <Box className="vtf-glass-strong rounded-3xl p-4">
          {/* Header */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              mb: 2.5,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
              <Skeleton
                variant="rounded"
                width={40}
                height={40}
                sx={{ borderRadius: "12px" }}
              />
              <Box>
                <Skeleton variant="text" width={180} height={18} />
                <Skeleton
                  variant="text"
                  width={90}
                  height={13}
                  sx={{ mt: 0.5 }}
                />
              </Box>
            </Box>
            <Skeleton
              variant="rounded"
              width={80}
              height={24}
              sx={{ borderRadius: "16px" }}
            />
          </Box>

          {/* Grid */}
          <Box className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Left: income form */}
            <Box>
              <Skeleton
                variant="text"
                width="90%"
                height={13}
                sx={{ mb: 0.5 }}
              />
              <Skeleton variant="text" width="70%" height={13} sx={{ mb: 2 }} />

              <Box
                sx={{
                  display: "grid",
                  gridTemplateColumns: { xs: "1fr", sm: "1fr 80px auto" },
                  gap: { xs: 1.25, sm: 1 },
                  alignItems: { xs: "stretch", sm: "flex-end" },
                }}
              >
                <Box sx={{ width: "100%" }}>
                  <Skeleton
                    variant="text"
                    width={90}
                    height={13}
                    sx={{ mb: 0.75 }}
                  />
                  <Skeleton
                    variant="rounded"
                    width="100%"
                    height={38}
                    sx={{ borderRadius: "10px" }}
                  />
                </Box>
                <Box sx={{ width: { xs: "100%", sm: 80 } }}>
                  <Skeleton
                    variant="text"
                    width={40}
                    height={13}
                    sx={{ mb: 0.75 }}
                  />
                  <Skeleton
                    variant="rounded"
                    width="100%"
                    height={38}
                    sx={{ borderRadius: "10px" }}
                  />
                </Box>
                <Box sx={{ width: { xs: "100%", sm: 100 } }}>
                  <Skeleton
                    variant="rounded"
                    width="100%"
                    height={38}
                    sx={{ borderRadius: "20px" }}
                  />
                </Box>
              </Box>
            </Box>

            {/* Right: solidarity card */}
            <Skeleton
              variant="rounded"
              width="100%"
              height={120}
              sx={{ borderRadius: "24px" }}
            />
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}
