import { Box, Skeleton } from "../../ui";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { VtfSectionHeading } from "../../shared/VtfSectionHeading";
import TravelExploreRoundedIcon from "@mui/icons-material/TravelExploreRounded";
import type { SejourMode } from "../../../types/stayTab";

export function StayResultsSkeleton({ mode }: { mode: SejourMode }) {
  return (
    <VtfGlassCard>
      <VtfSectionHeading
        accent="teal"
        icon={<TravelExploreRoundedIcon />}
        title={<Skeleton width={120} height={18} sx={{ borderRadius: 1 }} />}
        wrapTitle={false}
        rightSlot={
          <Box
            sx={{
              display: "flex",
              gap: 1,
              alignItems: "center",
              flexWrap: "wrap",
              width: "100%",
              justifyContent: { xs: "flex-start", sm: "flex-end" },
            }}
          >
            <Skeleton
              width={120}
              height={36}
              sx={{ borderRadius: "9999px", flex: { xs: 1, sm: "none" } }}
            />
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 0.75,
                flex: { xs: 1, sm: "none" },
                minWidth: 0,
              }}
            >
              <Skeleton
                width={120}
                height={36}
                sx={{ borderRadius: "9999px", flex: 1, minWidth: 0 }}
              />
              <Skeleton variant="circular" width={36} height={36} />
            </Box>
          </Box>
        }
      />

      {mode === "activite" ? (
        <Box>
          <Box className="grid grid-cols-2 gap-2">
            {[1, 2, 3, 4].map((i) => (
              <AttractionTileSkeleton key={i} />
            ))}
          </Box>
        </Box>
      ) : (
        <Box>
          {[1, 2, 3].map((i) => (
            <VillageCardSkeleton key={i} />
          ))}
        </Box>
      )}
    </VtfGlassCard>
  );
}

function VillageCardSkeleton() {
  return (
    <Box
      sx={{
        width: "100%",
        p: 2,
        mb: 1,
        borderRadius: "16px",
        border: "2px solid rgba(15, 23, 42, 0.08)",
        bgcolor: "white",
      }}
    >
      <Box className="flex items-start justify-between gap-2">
        <Box sx={{ flex: 1 }}>
          <Skeleton width="60%" height={24} sx={{ mb: 1 }} />
          <Skeleton width="40%" height={16} sx={{ mb: 0.5 }} />
          <Skeleton width="30%" height={16} />
        </Box>
        <Box className="text-right">
          <Skeleton width={40} height={20} sx={{ ml: "auto" }} />
          <Skeleton width={60} height={14} sx={{ ml: "auto" }} />
        </Box>
      </Box>

      <Box className="flex flex-wrap gap-1.5 mt-2">
        {[1, 2, 3].map((i) => (
          <Skeleton
            key={i}
            width={70}
            height={20}
            sx={{ borderRadius: "46px" }}
          />
        ))}
      </Box>

      <Box className="mt-2 flex items-center justify-between">
        <Skeleton width={100} height={14} />
        <Skeleton width={60} height={14} />
      </Box>
    </Box>
  );
}

function AttractionTileSkeleton() {
  return (
    <Box
      sx={{
        p: 1.25,
        borderRadius: "18px",
        minHeight: 96,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        bgcolor: "rgba(var(--vtf-cream-rgb), 0.35)",
        border: "1px solid rgba(15, 23, 42, 0.08)",
      }}
    >
      <Skeleton
        variant="circular"
        width={44}
        height={44}
        sx={{ mb: 1.15, borderRadius: "16px" }}
      />
      <Skeleton width="70%" height={16} sx={{ mb: 0.5 }} />
      <Skeleton width="40%" height={12} />
    </Box>
  );
}
