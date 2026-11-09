import { Box, Skeleton } from "../../ui";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { VtfSectionHeading } from "../../shared/VtfSectionHeading";
import PlaceRoundedIcon from "@mui/icons-material/PlaceRounded";

export function StayEnvironmentSkeleton() {
  return (
    <VtfGlassCard>
      <VtfSectionHeading
        accent="orange"
        icon={<PlaceRoundedIcon />}
        title={<Skeleton width={130} height={18} sx={{ borderRadius: 1 }} />}
        wrapTitle={false}
      />

      <Box className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {[1, 2, 3].map((i) => (
          <Box
            key={i}
            sx={{
              minHeight: { xs: 124, sm: 152 },
              p: 2,
              borderRadius: "22px",
              border: "1px solid rgba(148, 163, 184, 0.35)",
              bgcolor: "rgba(15, 23, 42, 0.025)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Skeleton
              variant="circular"
              width={44}
              height={44}
              sx={{ mb: 1.25, borderRadius: "16px" }}
            />
            <Skeleton width="60%" height={16} sx={{ mb: 0.75 }} />
            <Skeleton width="40%" height={12} />
          </Box>
        ))}
      </Box>
    </VtfGlassCard>
  );
}
