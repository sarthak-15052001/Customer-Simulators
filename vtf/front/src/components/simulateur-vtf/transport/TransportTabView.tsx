import CommuteRoundedIcon from "@mui/icons-material/CommuteRounded";
import DirectionsCarRoundedIcon from "@mui/icons-material/DirectionsCarRounded";
import PlaceRoundedIcon from "@mui/icons-material/PlaceRounded";
import TrainRoundedIcon from "@mui/icons-material/TrainRounded";
import { Box, Button, Pill, Skeleton, Typography } from "../../ui";
import { NoticeBox } from "../../shared/NoticeBox";

import type { FuelOption } from "../../../api/transport.api";
import {
  VTF_TRANSPORT_DEFAULTS,
  type TransportMode,
} from "../../../data/vtfTransport";
import type { FuelKey } from "../../../data/vtfTransport";
import { formatEuro } from "../../../utils/currency";
import { useTranslation } from "../../../contexts/LanguageContext";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";
import { VtfGlassCard } from "../../shared/VtfGlassCard";
import { TransportFuelsSkeleton } from "./TransportFuelsSkeleton";

type TransportTabViewProps = {
  tt: (k: string) => string;
  mode: TransportMode;
  fuel: FuelKey;
  distanceOneWayKm: number;
  fuels: FuelOption[];
  isFuelsLoading?: boolean;
  isFuelsError?: boolean;
  onRetryFuels?: () => void;
  onRetryCar?: () => void;
  onRetryTrain?: () => void;
  onSetMode: (mode: TransportMode) => void;
  onSetFuel: (fuel: FuelKey) => void;
  onSetDistance: (distanceOneWayKm: number) => void;
  car: { kmAR: number; fuelCost: number; tollCost: number; total: number };
  trainTotal: number;
  trainAdultOneWay?: number;
  trainChildOneWay?: number;
  isCarEstimateLoading?: boolean;
  isTrainEstimateLoading?: boolean;
  isCarEstimateError?: boolean;
  isTrainEstimateError?: boolean;
};

export function TransportTabView({
  tt,
  mode,
  fuel,
  distanceOneWayKm,
  fuels,
  isFuelsLoading = false,
  isFuelsError = false,
  onRetryFuels,
  onRetryCar,
  onRetryTrain,
  onSetMode,
  onSetFuel,
  onSetDistance,
  car,
  trainTotal,
  trainAdultOneWay,
  trainChildOneWay,
  isCarEstimateLoading = false,
  isTrainEstimateLoading = false,
  isCarEstimateError = false,
  isTrainEstimateError = false,
}: TransportTabViewProps) {
  const { t } = useTranslation();
  const sectionTitleSx = {
    mt: 1.75,
    fontSize: "var(--vtf-font-sm)",
    fontWeight: 950,
    letterSpacing: "0.14em",
    textTransform: "uppercase",
    color: "rgba(0, 68, 90, 0.62)",
  } as const;

  const pillBtnSx = {
    display: "inline-flex",
    gap: 0.75,
    alignItems: "center",
    minHeight: "36px !important",
    px: "12px !important",
    py: "6px !important",
  } as const;

  return (
    <Box className="vtf-tab-stack">
      <VtfGlassCard
        title={tt("title")}
        subtitle={tt("subtitle")}
        headingIcon={<CommuteRoundedIcon />}
        headingAccent="teal"
        rightSlot={
          <Pill
            size="small"
            label={tt(
              mode === "car"
                ? "modeCar"
                : mode === "train"
                  ? "modeTrain"
                  : "modeOnSite",
            )}
            vtfTone="softTeal"
            sx={{
              fontSize: "var(--vtf-font-sm)",
              fontWeight: 550,
              height: "auto",
              py: 0.35,

              letterSpacing: "0.12em",
              border: "1px solid rgba(var(--vtf-teal-rgb), 0.18)",
              whiteSpace: "nowrap",
            }}
          />
        }
      >
        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
          <Button
            vtfVariant="modePickerPill"
            segmentSelected={mode === "car"}
            segmentAccent="teal"
            onClick={() => onSetMode("car")}
            sx={pillBtnSx}
          >
            <DirectionsCarRoundedIcon
              sx={{ fontSize: "var(--vtf-font-md)", opacity: 0.85 }}
            />
            {tt("modeCar")}
          </Button>
          <Button
            vtfVariant="modePickerPill"
            segmentSelected={mode === "train"}
            segmentAccent="teal"
            onClick={() => onSetMode("train")}
            sx={pillBtnSx}
          >
            <TrainRoundedIcon
              sx={{ fontSize: "var(--vtf-font-md)", opacity: 0.85 }}
            />
            {tt("modeTrain")}
          </Button>
          <Button
            vtfVariant="modePickerPill"
            segmentSelected={mode === "onSite"}
            segmentAccent="teal"
            onClick={() => onSetMode("onSite")}
            sx={pillBtnSx}
          >
            <PlaceRoundedIcon
              sx={{ fontSize: "var(--vtf-font-md)", opacity: 0.85 }}
            />
            {tt("modeOnSite")}
          </Button>
        </Box>

        {mode === "car" ? (
          <>
            <Typography sx={sectionTitleSx}>{tt("fuelTitle")}</Typography>

            {isFuelsLoading ? (
              <TransportFuelsSkeleton />
            ) : isFuelsError ? (
              <VtfErrorAlert
                title={tt("fuelsLoadErrorTitle")}
                message={tt("fuelsLoadError")}
                onRetry={onRetryFuels}
                retryLabel={t("simulateur.family.retry")}
                sx={{ mt: 1 }}
              />
            ) : (
              <Box sx={{ mt: 1, display: "flex", gap: 1, flexWrap: "wrap" }}>
                {fuels.map((f) => {
                  const selected = fuel === f.key;
                  return (
                    <Button
                      key={f.key}
                      vtfVariant="modePickerPill"
                      segmentSelected={selected}
                      segmentAccent="orange"
                      onClick={() => onSetFuel(f.key)}
                      sx={{
                        ...pillBtnSx,
                        ...(selected
                          ? {
                              color: "rgba(185, 28, 28, 0.9)",
                              boxShadow: "0 10px 24px rgba(212, 112, 42, 0.14)",
                            }
                          : {}),
                      }}
                    >
                      {f.label}
                      <Box
                        component="span"
                        sx={{
                          fontSize: "var(--vtf-font-sm)",
                          fontWeight: 900,
                          px: 0.75,
                          py: 0.2,
                          borderRadius: 999,
                          bgcolor: selected
                            ? "rgba(var(--vtf-orange-rgb), 0.14)"
                            : "rgba(15, 23, 42, 0.06)",
                          color: selected
                            ? "rgba(185, 28, 28, 0.85)"
                            : "rgba(0, 68, 90, 0.55)",
                        }}
                      >
                        {formatEuro(f.costPerKm, {
                          compact: false,
                          suffix: "/km",
                          decimals: 2,
                        })}
                      </Box>
                    </Button>
                  );
                })}
              </Box>
            )}

            <Typography sx={sectionTitleSx}>
              {tt("distanceTitle")}{" "}
              <Box
                component="span"
                sx={{ color: "var(--vtf-orange)", fontWeight: 980 }}
              >
                {distanceOneWayKm} km
              </Box>
            </Typography>

            <Box sx={{ mt: 1 }}>
              <Box
                component="div"
                sx={{
                  width: "100%",
                  '& input[type="range"]': {
                    width: "100%",
                    WebkitAppearance: "none",
                    appearance: "none",
                    height: 8,
                    borderRadius: 999,
                    background: "rgba(15, 23, 42, 0.10)",
                    outline: "none",
                  },
                  '& input[type="range"]::-webkit-slider-thumb': {
                    WebkitAppearance: "none",
                    appearance: "none",
                    width: 18,
                    height: 18,
                    borderRadius: 999,
                    background: "var(--vtf-orange)",
                    border: "3px solid rgba(255,255,255,0.9)",
                    boxShadow: "0 8px 18px rgba(212, 112, 42, 0.25)",
                    cursor: "pointer",
                  },
                  '& input[type="range"]::-moz-range-thumb': {
                    width: 18,
                    height: 18,
                    borderRadius: 999,
                    background: "var(--vtf-orange)",
                    border: "3px solid rgba(255,255,255,0.9)",
                    boxShadow: "0 8px 18px rgba(212, 112, 42, 0.25)",
                    cursor: "pointer",
                  },
                  '& input[type="range"]::-moz-range-track': {
                    height: 8,
                    borderRadius: 999,
                    background: "rgba(15, 23, 42, 0.10)",
                  },
                }}
              >
                <input
                  type="range"
                  min={VTF_TRANSPORT_DEFAULTS.distanceMinKm}
                  max={VTF_TRANSPORT_DEFAULTS.distanceMaxKm}
                  step={VTF_TRANSPORT_DEFAULTS.distanceStepKm}
                  value={distanceOneWayKm}
                  onChange={(e) =>
                    onSetDistance(Number((e.target as HTMLInputElement).value))
                  }
                />
              </Box>
            </Box>

            {isCarEstimateError ? (
              <VtfErrorAlert
                title={tt("carEstimateErrorTitle")}
                message={tt("carEstimateError")}
                onRetry={onRetryCar}
                retryLabel={t("simulateur.family.retry")}
                sx={{ mt: 2 }}
              />
            ) : (
              <NoticeBox
                tone="orange"
                sx={{
                  color: "rgba(0, 68, 90, 0.78)",
                  background: "rgba(var(--vtf-orange-rgb), 0.08)",
                  fontWeight: 800,
                  opacity: isCarEstimateLoading ? 0.65 : 1,
                }}
              >
                {tt("carRoundTrip").replace("{{km}}", String(car.kmAR))} ·{" "}
                {tt("fuel")} ~{formatEuro(car.fuelCost)} · {tt("tolls")} ~
                {formatEuro(car.tollCost)} →{" "}
                <Box
                  component="span"
                  sx={{ fontWeight: 980, color: "rgba(185, 28, 28, 0.9)" }}
                >
                  {tt("total")} ~{formatEuro(car.total)}
                  {isCarEstimateLoading ? (
                    <Skeleton
                      component="span"
                      width={28}
                      height={14}
                      sx={{
                        display: "inline-block",
                        verticalAlign: "middle",
                        ml: 0.5,
                      }}
                    />
                  ) : null}
                </Box>
              </NoticeBox>
            )}
          </>
        ) : mode === "train" ? (
          isTrainEstimateError ? (
            <VtfErrorAlert
              title={tt("trainEstimateErrorTitle")}
              message={tt("trainEstimateError")}
              onRetry={onRetryTrain}
              retryLabel={t("simulateur.family.retry")}
              sx={{ mt: 2 }}
            />
          ) : (
            <NoticeBox
              tone="navy"
              sx={{
                color: "rgba(0, 68, 90, 0.78)",
                background: "rgba(0, 68, 90, 0.05)",
                opacity: isTrainEstimateLoading ? 0.65 : 1,
              }}
            >
              {trainAdultOneWay != null && trainChildOneWay != null ? (
                <>
                  {tt("trainNote")
                    .replace("{{adult}}", formatEuro(trainAdultOneWay))
                    .replace("{{child}}", formatEuro(trainChildOneWay))}
                  <br />
                  <Box
                    component="span"
                    sx={{ fontWeight: 980, color: "rgba(0, 68, 90, 0.92)" }}
                  >
                    {tt("trainTotal")}: {formatEuro(trainTotal)}
                    {isTrainEstimateLoading ? (
                      <Skeleton
                        component="span"
                        width={28}
                        height={14}
                        sx={{
                          display: "inline-block",
                          verticalAlign: "middle",
                          ml: 0.5,
                        }}
                      />
                    ) : null}
                  </Box>
                </>
              ) : (
                <Box
                  component="span"
                  sx={{ fontWeight: 980, color: "rgba(0, 68, 90, 0.92)" }}
                >
                  {tt("trainTotal")}: {formatEuro(trainTotal)}
                  {isTrainEstimateLoading ? (
                    <Skeleton
                      component="span"
                      width={28}
                      height={14}
                      sx={{
                        display: "inline-block",
                        verticalAlign: "middle",
                        ml: 0.5,
                      }}
                    />
                  ) : null}
                </Box>
              )}
            </NoticeBox>
          )
        ) : (
          <NoticeBox tone="green">{tt("onSiteNote")}</NoticeBox>
        )}
      </VtfGlassCard>
    </Box>
  );
}
