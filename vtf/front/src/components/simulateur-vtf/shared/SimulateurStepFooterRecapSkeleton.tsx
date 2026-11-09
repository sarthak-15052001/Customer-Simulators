import { Box, Skeleton, Typography } from "../../ui";
import NightsStayRoundedIcon from "@mui/icons-material/NightsStayRounded";
import PlaceRoundedIcon from "@mui/icons-material/PlaceRounded";

const softBlock = {
  borderRadius: "10px",
  bgcolor: "#FFFFFF",
  border: "1px solid #D4E4E8",
};

const amountCardSkeleton = {
  ...softBlock,
  borderRadius: "14px",
  height: 52,
  flex: { xs: "1 1 100%", sm: "1 1 auto" },
  minWidth: { xs: "100%", sm: 200 },
  maxWidth: { sm: 240 },
};

type Props = {
  budgetLabel: string;
};

export function SimulateurStepFooterRecapSkeleton({ budgetLabel }: Props) {
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: {
          xs: "1fr",
          sm: "auto 1fr",
          md: "auto 1fr auto",
        },
        alignItems: "center",
        gap: { xs: 1, sm: 1.5 },
        px: { xs: 1.25, sm: 1.5 },
        py: { xs: 1.15, sm: 1.25 },
      }}
    >
      <Box
        sx={{
          display: "flex",
          gap: 0.65,
          flexWrap: "wrap",
          justifyContent: { xs: "center", sm: "flex-start" },
        }}
      >
        <Skeleton
          animation="pulse"
          variant="rounded"
          sx={{ ...softBlock, width: 108, height: 24, borderRadius: "9999px" }}
        />
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <NightsStayRoundedIcon sx={{ fontSize: 17, color: "#00445A" }} />
          <Skeleton
            animation="pulse"
            variant="rounded"
            sx={{ ...softBlock, width: 72, height: 24, borderRadius: "9999px" }}
          />
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <PlaceRoundedIcon sx={{ fontSize: 17, color: "#00445A" }} />
          <Skeleton
            animation="pulse"
            variant="rounded"
            sx={{ ...softBlock, width: 88, height: 24, borderRadius: "9999px" }}
          />
        </Box>
      </Box>

      <Box sx={{ textAlign: { xs: "center", sm: "left" } }}>
        <Typography
          sx={{
            fontSize: "var(--vtf-font-xs)",
            fontWeight: 950,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: "#5A7A85",
            mb: 0.4,
          }}
        >
          {budgetLabel}
        </Typography>
        <Box
          sx={{
            display: "flex",
            gap: 1,
            justifyContent: { xs: "center", sm: "flex-start" },
            flexWrap: "wrap",
          }}
        >
          <Skeleton
            animation="pulse"
            variant="rounded"
            sx={{ ...softBlock, width: 110, height: 26 }}
          />
          <Skeleton
            animation="pulse"
            variant="rounded"
            sx={{ ...softBlock, width: 96, height: 16 }}
          />
        </Box>
      </Box>

      <Box
        sx={{
          display: "flex",
          flexDirection: { xs: "column", sm: "row" },
          flexWrap: "wrap",
          gap: 0.75,
          justifyContent: { xs: "center", sm: "flex-end" },
          width: "100%",
          gridColumn: { xs: "1", md: "auto" },
        }}
      >
        <Skeleton animation="pulse" variant="rounded" sx={amountCardSkeleton} />
        <Skeleton animation="pulse" variant="rounded" sx={amountCardSkeleton} />
      </Box>
    </Box>
  );
}
