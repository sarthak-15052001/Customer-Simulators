import { Box, Skeleton } from "../../ui";
import AutoGraphRoundedIcon from "@mui/icons-material/AutoGraphRounded";

export function SimulateurVtfPageSkeleton() {
  return (
    <Box>
      <Box
        className="rounded-3xl p-4 sm:p-5"
        sx={{
          background: `
      linear-gradient(
        135deg,
        rgba(255,255,255,0.94) 0%,
        rgba(252,249,246,0.98) 26%,
        rgba(174,218,196,0.18) 72%,
        rgba(0,168,181,0.08) 100%
      )
    `,
          border: "1px solid rgba(0,68,90,0.07)",
          boxShadow: "0 18px 42px rgba(0,68,90,0.08)",
          backdropFilter: "blur(18px)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <Box
          sx={{
            position: "absolute",
            top: -40,
            right: -40,
            width: 140,
            height: 140,
            borderRadius: "50%",
            background: "rgba(242,166,128,0.12)",
            filter: "blur(45px)",
            pointerEvents: "none",
          }}
        />

        <Box className="flex items-start gap-3 relative z-10">
          <Box
            className="w-11 h-11 rounded-2xl flex items-center justify-center"
            sx={{
              background: `
          linear-gradient(
            135deg,
            rgba(242,166,128,0.20) 0%,
            rgba(255,255,255,0.96) 55%,
            rgba(174,218,196,0.22) 100%
          )
        `,
              border: "1px solid rgba(0,68,90,0.08)",
              boxShadow: `
          0 10px 24px rgba(0,68,90,0.08),
          inset 0 2px 8px rgba(255,255,255,0.55)
        `,
              flexShrink: 0,
            }}
          >
            <AutoGraphRoundedIcon
              sx={{
                color: "var(--vtf-navy)",
                fontSize: 20,
              }}
            />
          </Box>

          <Box className="min-w-0" sx={{ width: "100%" }}>
            <Skeleton
              variant="text"
              width="40%"
              height={32}
              sx={{ mb: 1, borderRadius: "4px" }}
            />
            <Skeleton
              variant="text"
              width="60%"
              height={20}
              sx={{ borderRadius: "4px" }}
            />
          </Box>
        </Box>
      </Box>

      {/* Tabs list skeleton */}
      <Box
        className="rounded-3xl p-3 mt-1.5 sm:mt-2"
        sx={{
          display: "flex",
          gap: 1.5,
          overflowX: "hidden",
          background: `
          linear-gradient(
            135deg,
            rgba(255,255,255,0.92) 0%,
            rgba(252,249,246,0.96) 30%,
            rgba(174,218,196,0.18) 68%,
            rgba(0,168,181,0.08) 100%
          )
        `,
          border: "1px solid rgba(0,68,90,0.06)",
          boxShadow: "0 14px 38px rgba(0,68,90,0.08)",
          backdropFilter: "blur(18px)",
        }}
      >
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <Box
            key={i}
            className="m-0 inline-flex flex-col items-center justify-center shrink-0 min-w-[82px] sm:min-w-[102px] md:min-w-[112px] h-14 rounded-2xl border px-2 py-1.5"
            sx={{
              borderColor: "rgba(0,68,90,0.06)",
              background:
                "linear-gradient(135deg,rgba(255,255,255,0.88) 0%,rgba(252,249,246,0.95) 100%)",
            }}
          >
            <Skeleton
              variant="circular"
              width={24}
              height={24}
              sx={{ mb: 0.5 }}
            />
            <Skeleton variant="text" width={40} height={12} />
          </Box>
        ))}
      </Box>

      {/* Content area skeleton */}
      <Box sx={{ mt: 2, display: "flex", flexDirection: "column", gap: 2 }}>
        <Skeleton
          variant="rounded"
          width="100%"
          height={240}
          sx={{ borderRadius: "24px" }}
        />
        <Skeleton
          variant="rounded"
          width="100%"
          height={180}
          sx={{ borderRadius: "24px" }}
        />
      </Box>
    </Box>
  );
}
