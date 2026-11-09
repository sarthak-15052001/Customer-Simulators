import {
  Box,
  Button,
  IconButton,
  Pagination,
  SelectedBadge,
  Typography,
} from "../../ui";
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import CheckRoundedIcon from "@mui/icons-material/CheckRounded";
import HomeRoundedIcon from "@mui/icons-material/HomeRounded";
import AutoAwesomeRoundedIcon from "@mui/icons-material/AutoAwesomeRounded";
import HolidayVillageOutlinedIcon from "@mui/icons-material/HolidayVillageOutlined";
import TravelExploreRoundedIcon from "@mui/icons-material/TravelExploreRounded";
import type { VtfVillage } from "../../../data/vtfStay";
import type { SejourMode } from "../../../types/stayTab";
import type { MergedAttraction, VillagesPaging } from "./stayResultsCardModel";
import {
  StayResultsS,
  attractionIconWrapSx,
  attractionTileSx,
  searchNoMatchSx,
} from "./StayResultsCard.ui";
import { StayVillageResultRow } from "./StayVillageResultRow";
import { VtfSearchField } from "../../shared/VtfSearchField";
import { VtfSectionHeading } from "../../shared/VtfSectionHeading";

export function StayResultsCardHeader(props: {
  mode: SejourMode;
  ts: (k: string) => string;
  searchValue: string;
  onSearchChange: (v: string) => void;
  onVillageMode: () => void;
  onActivityMode: () => void;
  onOpenFilters: () => void;
  hasActiveFilters: boolean;
  onClearFilters: () => void;
}) {
  const {
    mode,
    ts,
    onVillageMode,
    onActivityMode,
    onOpenFilters,
    hasActiveFilters,
    onClearFilters,
  } = props;
  return (
    <VtfSectionHeading
      accent="teal"
      icon={<TravelExploreRoundedIcon />}
      title={ts("resultsTitle")}
      rightSlot={
        <Box sx={StayResultsS.toolbar}>
          {mode === "village" && (
            <Box sx={{ width: { xs: "100%", sm: 320 }, maxWidth: "100%", flexShrink: 0 }}>
              <VtfSearchField
                value={props.searchValue}
                onChange={props.onSearchChange}
                placeholder={ts("resultsSearchPlaceholder")}
                aria-label={ts("resultsSearchAria")}
              />
            </Box>
          )}
          <Box
            className="max-sm:vtf-horizontal-scroll max-sm:vtf-horizontal-scroll--prominent"
            sx={StayResultsS.toolbarScrollRow}
          >
            <Button
              vtfVariant="modePickerPill"
              segmentAccent="teal"
              segmentSelected={mode === "village"}
              onClick={onVillageMode}
              sx={StayResultsS.modeBtnText}
            >
              {mode === "village" ? (
                <CheckRoundedIcon sx={StayResultsS.checkIconTeal} />
              ) : (
                <HomeRoundedIcon sx={{ fontSize: "var(--vtf-font-md)" }} />
              )}
              {ts("resultsByVillage")}
            </Button>
            <Box sx={StayResultsS.activityBtnRow}>
              <Button
                vtfVariant="modePickerPill"
                segmentAccent="orange"
                segmentSelected={mode === "activite"}
                onClick={onActivityMode}
                sx={StayResultsS.modeBtnText}
              >
                {mode === "activite" ? (
                  <CheckRoundedIcon sx={StayResultsS.checkIconOrange} />
                ) : (
                  <AutoAwesomeRoundedIcon
                    sx={{ fontSize: "var(--vtf-font-md)" }}
                  />
                )}
                {ts("resultsByActivity")}
              </Button>
              <IconButton
                type="button"
                size="small"
                onClick={onOpenFilters}
                aria-label={ts("resultsFilterModalAria")}
                sx={StayResultsS.filterFab}
              >
                <AddRoundedIcon sx={{ fontSize: 22 }} />
              </IconButton>
              {hasActiveFilters && (
                <IconButton
                  type="button"
                  size="small"
                  onClick={onClearFilters}
                  aria-label={ts("clearFiltersAria")}
                  sx={StayResultsS.filterFab}
                >
                  <CloseRoundedIcon sx={{ fontSize: 22 }} />
                </IconButton>
              )}
            </Box>
          </Box>
        </Box>
      }
    />
  );
}


function SearchNoMatch({
  message,
  compact,
}: {
  message: string;
  compact?: boolean;
}) {
  return <Typography sx={searchNoMatchSx(compact)}>{message}</Typography>;
}

function AttractionTile({
  a,
  selected,
  onToggle,
}: {
  a: MergedAttraction;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <Button
      vtfVariant="selectableTileOrange"
      tileSelected={selected}
      tileMinHeight={96}
      onClick={onToggle}
      sx={attractionTileSx(selected)}
    >
      {selected && <SelectedBadge accent="orange" />}
      <Box
        sx={{
          width: "100%",
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <Box sx={attractionIconWrapSx(selected)}>
          <Box sx={{ fontSize: 22, lineHeight: 1 }}>{a.icon}</Box>
        </Box>
        <Typography
          sx={{
            fontSize: "var(--vtf-font-sm)",
            fontWeight: 950,
            color: selected ? "var(--vtf-orange)" : "var(--vtf-navy)",
            textAlign: "center",
            lineHeight: 1.1,
          }}
        >
          {a.nom}
        </Typography>
        <Typography
          sx={{
            fontSize: "var(--vtf-font-xs)",
            fontWeight: 750,
            color: "var(--vtf-navy)",
            opacity: 0.55,
            textAlign: "center",
          }}
        >
          {a.type}
          {a.minKm > 0 ? ` · ${a.minKm}km` : null}
        </Typography>
      </Box>
    </Button>
  );
}

export function StayResultsActivitySection(props: {
  searchQNorm: string;
  displayAttractions: MergedAttraction[];
  attractionNom: string | null;
  displayActivityVillages: VtfVillage[];
  villageId: string | null;
  formuleFilter?: string | null;
  ts: (k: string) => string;
  onAttractionClick: (
    nom: string,
    id: string,
    currentlySelected: boolean,
  ) => void;
  onSelectVillage: (v: VtfVillage) => void;
}) {
  const {
    searchQNorm,
    displayAttractions,
    attractionNom,
    displayActivityVillages,
    villageId,
    formuleFilter,
    ts,
    onAttractionClick,
    onSelectVillage,
  } = props;

  return (
    <Box>
      {displayAttractions.length === 0 && searchQNorm ? (
        <SearchNoMatch message={ts("resultsSearchNoMatch")} />
      ) : (
        <Box className="grid grid-cols-2 gap-2">
          {displayAttractions.map((a) => {
            const sel = attractionNom === a.nom;
            return (
              <AttractionTile
                key={a.nom}
                a={a}
                selected={sel}
                onToggle={() => onAttractionClick(a.nom, a.id, sel)}
              />
            );
          })}
        </Box>
      )}

      {attractionNom && (
        <Box className="mt-4">
          {displayActivityVillages.length === 0 && searchQNorm ? (
            <SearchNoMatch message={ts("resultsSearchNoMatch")} compact />
          ) : (
            displayActivityVillages.map((v) => (
              <StayVillageResultRow
                key={v.id}
                village={v}
                selected={villageId === v.id}
                accent="orange"
                onSelect={() => onSelectVillage(v)}
                selectLabel={ts("select")}
                selectedLabel={ts("selected")}
                locSuffixLabel={ts("resultsLocSuffix")}
                formuleFilter={formuleFilter}
                t={ts}
              />
            ))
          )}
        </Box>
      )}
    </Box>
  );
}

export function StayResultsEmptyDataset(props: { ts: (k: string) => string }) {
  const { ts } = props;
  return (
    <Box sx={StayResultsS.emptyDatasetWrap}>
      <Box sx={StayResultsS.emptyDatasetIcon}>
        <HolidayVillageOutlinedIcon
          sx={{ fontSize: 30, color: "var(--vtf-teal)", opacity: 0.92 }}
        />
      </Box>
      <Typography sx={StayResultsS.emptyDatasetTitle}>
        {ts("resultsEmptyTitle")}
      </Typography>
      <Typography sx={StayResultsS.emptyDatasetSubtitle}>
        {ts("resultsEmptySubtitle")}
      </Typography>
    </Box>
  );
}

export function StayResultsVillageListSection(props: {
  searchQNorm: string;
  displayVillageItems: VtfVillage[];
  villageId: string | null;
  formuleFilter?: string | null;
  mode: SejourMode;
  villagesPaging?: VillagesPaging;
  ts: (k: string) => string;
  onSelectVillage: (v: VtfVillage) => void;
}) {
  const {
    searchQNorm,
    displayVillageItems,
    villageId,
    formuleFilter,
    mode,
    villagesPaging,
    ts,
    onSelectVillage,
  } = props;

  return (
    <Box>
      {displayVillageItems.length === 0 && searchQNorm ? (
        <SearchNoMatch message={ts("resultsSearchNoMatch")} />
      ) : (
        displayVillageItems.map((v) => (
          <StayVillageResultRow
            key={v.id}
            village={v}
            selected={villageId === v.id}
            accent="teal"
            onSelect={() => onSelectVillage(v)}
            selectLabel={ts("select")}
            selectedLabel={ts("selected")}
            locSuffixLabel={ts("resultsLocSuffix")}
            formuleFilter={formuleFilter}
            t={ts}
          />
        ))
      )}
      {mode === "village" && villagesPaging ? (
        <Pagination
          totalCount={villagesPaging.totalCount}
          pageSize={villagesPaging.pageSize}
          offset={villagesPaging.offset}
          onOffsetChange={villagesPaging.onOffsetChange}
        />
      ) : null}
    </Box>
  );
}
