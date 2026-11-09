import { Box, Typography } from "../../ui";

const gateSx = {
  p: 1.5,
  borderRadius: "14px",
  bgcolor: "rgba(var(--vtf-orange-rgb), 0.08)",
  border: "1px solid rgba(var(--vtf-orange-rgb), 0.16)",
} as const;

const messageSx = {
  fontSize: 'var(--vtf-font-sm)',
  fontWeight: 800,
  color: "var(--vtf-navy)",
} as const;

export function ExtrasRegionGate({ message }: { message: string }) {
  return (
    <Box sx={gateSx}>
      <Typography sx={messageSx}>{message}</Typography>
    </Box>
  );
}
