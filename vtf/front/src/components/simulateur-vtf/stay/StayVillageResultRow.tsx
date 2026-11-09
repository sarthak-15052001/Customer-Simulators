import { useTranslation } from "../../../contexts/LanguageContext";
import PlaceRoundedIcon from "@mui/icons-material/PlaceRounded";
import { Box, Button, Pill, Typography } from "../../ui";
import type { VtfVillage } from "../../../data/vtfStay";
import { formatEuro } from "../../../utils/currency";
import { getHighlights } from "../../../utils/stayTab";
import { getDynamicPriceSuffix } from "../../../utils/tariffUnit";

export function StayVillageResultRow({
  village,
  selected,
  accent,
  onSelect,
  selectLabel,
  selectedLabel,
  locSuffixLabel,
  formuleFilter,
  t,
}: {
  village: VtfVillage;
  selected: boolean;
  accent: "teal" | "orange";
  onSelect: () => void;
  selectLabel: string;
  selectedLabel: string;
  locSuffixLabel: string;
  formuleFilter?: string | null;
  t: (key: string) => string;
}) {
  const { language } = useTranslation();
  const hl = getHighlights(village, t);
  const titleColor = selected
    ? accent === "teal"
      ? "var(--vtf-teal)"
      : "var(--vtf-orange)"
    : "var(--vtf-navy)";
  const chipBg = accent === "teal" ? "var(--vtf-teal)" : "rgb(249 115 22)";

  const displayPrice = village.staySubtotal ?? village.perAdultBase;
  const isAccommodation = Boolean(
    village.staySubtotal != null ||
      formuleFilter === "LOC" ||
      (village.formules.length === 1 && village.formules[0] === "LOC"),
  );

  return (
    <Button
      vtfVariant="stayVillageRow"
      villageRowAccent={accent}
      villageRowSelected={selected}
      onClick={onSelect}
    >
      <Box sx={{ width: "100%" }}>
        <Box className="flex items-start justify-between gap-2">
          <Box className="flex flex-col items-start gap-0.5">
            <Box className="flex items-center gap-2 flex-wrap">
              <Typography
                sx={{
                  fontSize: "var(--vtf-font-sm)",
                  fontWeight: 950,
                  color: titleColor,
                }}
              >
                {village.env} {village.nom}
              </Typography>
              <Box
                sx={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 0.5,
                  px: 1,
                  py: 0.2,
                  borderRadius: 1.5,
                  bgcolor: "rgba(0, 68, 90, 0.05)",
                  border: "1px solid rgba(0, 68, 90, 0.12)",
                  whiteSpace: "nowrap",
                  flexShrink: 0,
                }}
              >
                <PlaceRoundedIcon
                  sx={{ fontSize: 13, color: "var(--vtf-orange)" }}
                />
                <Typography
                  sx={{
                    fontSize: "var(--vtf-font-xs)",
                    fontWeight: 850,
                    color: "var(--vtf-navy)",
                  }}
                >
                  {village.region}
                </Typography>
              </Box>
            </Box>
            {village.nom2 && (
              <Typography
                sx={{
                  fontSize: "var(--vtf-font-xs)",
                  color: "var(--vtf-navy)",
                  opacity: 0.55,
                }}
              >
                {village.nom2}
              </Typography>
            )}
          </Box>

          {Boolean(displayPrice && displayPrice > 0) && (
            <Box className="text-right flex-shrink-0">
              <Typography
                sx={{
                  fontSize: "var(--vtf-font-sm)",
                  fontWeight: 950,
                  color: "var(--vtf-orange)",
                }}
              >
                ~ {formatEuro(displayPrice!)}
              </Typography>
              <Typography
                sx={{
                  fontSize: "var(--vtf-font-xs)",
                  color: "var(--vtf-navy)",
                  opacity: 0.55,
                }}
              >
                {getDynamicPriceSuffix(
                  village.tarif_unit || village.tarifUnit,
                  t,
                  language,
                  isAccommodation,
                )}
              </Typography>
            </Box>
          )}
        </Box>

        <Box className="flex flex-wrap gap-1.5 mt-2">
          {hl.map((h) => (
            <Pill
              key={h.txt}
              size="small"
              label={`${h.icon} ${h.txt}`}
              vtfTone="softNavy"
              sx={{
                fontSize: "var(--vtf-font-sm)",
                fontWeight: 850,
                height: "auto",
                py: 0.2,
                border: "1px solid rgba(148, 163, 184, 0.35)",
              }}
            />
          ))}
        </Box>

        <Box className="mt-2 flex items-center justify-between flex-wrap gap-2">
          <Typography
            sx={{
              fontSize: "var(--vtf-font-sm)",
              color: "var(--vtf-navy)",
              opacity: 0.55,
              fontWeight: 700,
            }}
          >
            {village.formules.join(" · ")}
            {village.hasLoc && !village.formules.includes("LOC")
              ? locSuffixLabel
              : ""}
          </Typography>
          {selected ? (
            <Pill
              size="small"
              label={selectedLabel}
              vtfTone={accent === "teal" ? "softTeal" : "softOrange"}
              sx={{
                fontSize: "var(--vtf-font-sm)",
                fontWeight: 950,
                height: "auto",
                py: 0.2,
                bgcolor: chipBg,
                color: "white",
              }}
            />
          ) : (
            <Typography
              sx={{
                fontSize: "var(--vtf-font-sm)",
                fontWeight: 900,
                color:
                  accent === "teal" ? "var(--vtf-teal)" : "var(--vtf-orange)",
              }}
            >
              {selectLabel}
            </Typography>
          )}
        </Box>
      </Box>
    </Button>
  );
}
