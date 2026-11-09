import { Box } from "../ui";

export function LandingHeroCurve() {
  return (
    <Box
      sx={{
        position: "absolute",
        bottom: -1,
        left: 0,
        width: "100%",
        lineHeight: 0,
        zIndex: 1,
        color: "var(--vtf-cream)",
      }}
    >
      <svg
        viewBox="0 0 1440 100"
        fill="currentColor"
        preserveAspectRatio="none"
        style={{ width: "100%", height: 85 }}
        aria-hidden
      >
        <path d="M0,48L80,53.3C160,59,320,69,480,64C640,59,800,37,960,32C1120,27,1280,37,1360,42.7L1440,48L1440,100L1360,100C1280,100,1120,100,960,100C800,100,640,100,480,100C320,100,160,100,80,100L0,100Z" />
      </svg>
    </Box>
  );
}
