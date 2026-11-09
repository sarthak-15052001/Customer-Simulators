import { Box, Button, Typography } from "../../ui";

export function PlanningBannerCard({
  bannerTitle,
  bannerBody,
  defaultLabel,
  onDefault,
}: {
  bannerTitle: string;
  bannerBody: string;
  defaultLabel: string;
  onDefault: () => void;
}) {
  return (
    <Box>
      <Box
        sx={{
          background:
            "linear-gradient(135deg, rgba(var(--vtf-teal-rgb), 0.1) 0%, rgba(var(--vtf-navy-rgb), 0.05) 100%)",
          border: "1px solid rgba(var(--vtf-teal-rgb), 0.25)",
          borderRadius: 4,
          p: 2.25,
          display: "flex",
          gap: 2,
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          transition: "all 0.3s ease",
          "&:hover": {
            boxShadow: "0 8px 24px rgba(0, 168, 181, 0.08)",
            borderColor: "rgba(var(--vtf-teal-rgb), 0.35)",
          },
        }}
      >
        <Box sx={{ minWidth: 240 }}>
          <Typography
            sx={{ fontWeight: 950, color: "var(--vtf-teal)", fontSize: 'var(--vtf-font-sm)' }}
          >
            {bannerTitle}
          </Typography>
          <Typography
            sx={{
              fontSize: 'var(--vtf-font-sm)',
              fontWeight: 700,
              color: "rgba(0,68,90,0.78)",
              mt: 0.5,
            }}
          >
            {bannerBody}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
          <Button
            vtfVariant="navyFillPill"
            size="small"
            startIcon={<Box component="span">✨</Box>}
            onClick={onDefault}
            sx={{
              height: 34,
              borderRadius: 99,
              textTransform: "uppercase",
              letterSpacing: "0.10em",
              fontSize: 'var(--vtf-font-sm)',
              fontWeight: 950,
              px: 2,
              boxShadow: "0 4px 12px rgba(0, 68, 90, 0.15)",
              "&:hover": {
                transform: "translateY(-1px)",
                boxShadow: "0 6px 16px rgba(0, 68, 90, 0.2)",
              }
            }}
          >
            {defaultLabel}
          </Button>
        </Box>
      </Box>
    </Box>
  );
}
