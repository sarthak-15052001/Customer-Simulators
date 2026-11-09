import { Box, Skeleton } from "../../ui";

/** Squelette pour une ligne de sortie gratuite */
function FreeRowSkeleton() {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: { xs: 1.25, sm: 1.5 },
        py: 1.15,
        px: { xs: 1.25, sm: 1.5 },
        borderBottom: "1px solid rgba(15,23,42,0.06)",
        "&:last-child": { borderBottom: 0 },
      }}
    >
      {/* Carré pour le bouton toggle */}
      <Skeleton
        variant="rounded"
        width={40}
        height={36}
        sx={{ borderRadius: "10px", opacity: 0.6 }}
      />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {/* Ligne pour le titre de l'activité */}
        <Skeleton
          sx={{ height: 16, width: "65%", mb: 0.5, borderRadius: "4px" }}
        />
        <Skeleton sx={{ height: 10, width: "35%", borderRadius: "4px" }} />
      </Box>
      {/* Badge gratuité */}
      <Skeleton
        variant="rounded"
        width={56}
        height={22}
        sx={{ borderRadius: "8px", opacity: 0.5 }}
      />
    </Box>
  );
}

/** Squelette pour une ligne d'activité payante */
function PaidRowSkeleton() {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "flex-start",
        gap: { xs: 1.25, sm: 1.5 },
        py: 1.25,
        px: { xs: 1.25, sm: 1.5 },
        borderBottom: "1px solid rgba(15,23,42,0.06)",
        "&:last-child": { borderBottom: 0 },
      }}
    >
      <Skeleton
        variant="rounded"
        width={40}
        height={36}
        sx={{ borderRadius: "10px", opacity: 0.6, mt: 0.25 }}
      />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Skeleton
          sx={{ height: 16, width: "80%", mb: 0.75, borderRadius: "4px" }}
        />
        <Skeleton sx={{ height: 11, width: "50%", borderRadius: "4px" }} />
      </Box>
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-end",
          gap: 0.5,
        }}
      >
        <Skeleton sx={{ width: 52, height: 18, borderRadius: "4px" }} />
        <Skeleton sx={{ width: 44, height: 10, borderRadius: "2px" }} />
      </Box>
    </Box>
  );
}

export function ExtrasFreeActivitiesSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", opacity: 0.8 }}>
      {Array.from({ length: rows }, (_, i) => (
        <FreeRowSkeleton key={i} />
      ))}
    </Box>
  );
}

export function ExtrasPaidActivitiesSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", opacity: 0.8 }}>
      {Array.from({ length: rows }, (_, i) => (
        <PaidRowSkeleton key={i} />
      ))}
    </Box>
  );
}

/** Correspond à la ligne orange "Total prestataires" pendant le chargement. */
export function ExtrasPaidActivitiesTotalSkeleton() {
  return (
    <Box
      sx={{
        mt: 1,
        p: 1.75,
        borderRadius: "16px",
        bgcolor: "rgba(var(--vtf-orange-rgb), 0.05)",
        border: "1px solid rgba(var(--vtf-orange-rgb), 0.12)",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}
    >
      <Skeleton sx={{ height: 14, width: "45%", borderRadius: "4px" }} />
      <Skeleton
        variant="rounded"
        sx={{ height: 24, width: 64, borderRadius: "6px" }}
      />
    </Box>
  );
}
