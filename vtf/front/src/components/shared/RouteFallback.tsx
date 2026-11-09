import { Box } from "../ui";
import { SimulateurVtfPageSkeleton } from "../simulateur-vtf/shared/SimulateurVtfPageSkeleton";

/**
 * Fallback au niveau de la route pendant le chargement du chunk lazy
 * de `SimulateurVtfPage` — conserve la même structure visuelle que la page.
 */
export function RouteFallback() {
  return (
    <Box
      sx={{
        background:
          "linear-gradient(180deg, var(--vtf-cream) 0%, #ffffff 100%)",
        pb: { xs: 'var(--vtf-font-md)', sm: 'var(--vtf-font-md)' },
        minHeight: "calc(100vh - 160px)",
        display: "flex",
        flexDirection: "column",
      }}
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label="Loading simulator"
    >
      <Box
        className="mx-auto w-full max-w-[1120px] px-4 sm:px-6"
        sx={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          pt: { xs: 1.5, sm: 2 },
        }}
      >
        <SimulateurVtfPageSkeleton />
      </Box>
    </Box>
  );
}
