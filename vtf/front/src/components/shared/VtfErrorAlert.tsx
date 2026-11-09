/* eslint-disable @typescript-eslint/no-explicit-any */
import { Box, Typography, Button } from "../ui";
import ErrorOutlineRoundedIcon from "@mui/icons-material/ErrorOutlineRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";

interface VtfErrorAlertProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  sx?: any;
}

export function VtfErrorAlert({
  title,
  message,
  onRetry,
  retryLabel = "Réessayer",
  sx = {},
}: VtfErrorAlertProps) {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: { xs: "column", sm: "row" },
        alignItems: { xs: "flex-start", sm: "center" },
        gap: 2,
        p: 2.5,
        borderRadius: "24px",
        background: "rgba(255, 255, 255, 0.65)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        border: "1px solid rgba(224, 138, 102, 0.4)",
        boxShadow: "0 8px 32px rgba(224, 138, 102, 0.12)",
        position: "relative",
        overflow: "hidden",
        ...sx,
      }}
    >
      <Box
        sx={{
          position: "absolute",
          top: -20,
          left: -20,
          width: 80,
          height: 80,
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(224, 138, 102, 0.15) 0%, transparent 70%)",
          zIndex: 0,
        }}
      />

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 44,
          height: 44,
          borderRadius: "14px",
          bgcolor: "rgba(224, 138, 102, 0.12)",
          color: "var(--vtf-orange-dark)",
          flexShrink: 0,
          zIndex: 1,
        }}
      >
        <ErrorOutlineRoundedIcon sx={{ fontSize: 26 }} />
      </Box>

      <Box sx={{ flex: 1, zIndex: 1 }}>
        {title && (
          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: 800,
              color: "var(--vtf-navy)",
              mb: 0.5,
              fontSize: 'var(--vtf-font-md)',
            }}
          >
            {title}
          </Typography>
        )}
        <Typography
          variant="body2"
          sx={{
            fontWeight: 600,
            color: "var(--vtf-navy)",
            opacity: 0.8,
            fontSize: 'var(--vtf-font-sm)',
            lineHeight: 1.5,
          }}
        >
          {message}
        </Typography>
      </Box>

      {onRetry && (
        <Button
          vtfVariant="orangeFillPill"
          size="small"
          onClick={onRetry}
          startIcon={<RefreshRoundedIcon />}
          sx={{
            py: 1,
            px: 2.5,
            fontSize: 'var(--vtf-font-sm)',
            fontWeight: 800,
            whiteSpace: "nowrap",
            alignSelf: { xs: "stretch", sm: "center" },
            boxShadow: "0 4px 12px rgba(var(--vtf-orange-rgb), 0.2)",
            zIndex: 1,
          }}
        >
          {retryLabel}
        </Button>
      )}
    </Box>
  );
}
