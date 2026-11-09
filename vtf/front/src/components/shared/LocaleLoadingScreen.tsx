import CircularProgress from "@mui/material/CircularProgress";
import { Box } from "../ui";

/**
 * Écran affiché pendant le chargement du fichier JSON de la langue active —
 * ne doit pas utiliser `t()`.
 */
export function LocaleLoadingScreen() {
  return (
    <Box
      sx={{
        minHeight: "100svh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        bgcolor: "var(--vtf-cream, #f7f4ef)",
      }}
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label="Loading"
    >
      <CircularProgress size={40} sx={{ color: "var(--vtf-teal, #00a8b5)" }} />
    </Box>
  );
}
