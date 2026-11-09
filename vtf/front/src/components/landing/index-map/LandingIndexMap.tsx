import ArrowForwardIosIcon from "@mui/icons-material/ArrowForwardIos";
import CloseIcon from "@mui/icons-material/Close";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import { useLandingIndexMap } from "../../../hooks/useLandingIndexMap";
import { useTranslation } from "../../../contexts/LanguageContext";
import { vtfUrl } from "../../../config/site";
import { activateOnKeyboard } from "../../../utils/a11y";
import { Box, Button, Typography, Skeleton } from "../../ui";

import {
  landingIndexMapAreaSx,
  landingIndexMapContentSx,
  landingIndexMapHeadSx,
  landingIndexMapInnerSx,
  landingIndexMapLayoutSx,
  landingIndexMapMarkerSx,
  landingIndexMapMobileTogglerSx,
  landingIndexMapPatternSx,
  landingIndexMapPopoverDetailsSx,
  landingIndexMapPopoverPlaceSx,
  landingIndexMapPopoverQuoteSx,
  landingIndexMapPopoverRegionSx,
  landingIndexMapPopoverSx,
  landingIndexMapRegionColSx,
  landingIndexMapRegionIconSx,
  landingIndexMapRegionItemSx,
  landingIndexMapRegionLabelSx,
  landingIndexMapRegionsListSx,
  landingIndexMapRegionsMenuSx,
  landingIndexMapRegionsRootSx,
  landingIndexMapSectionSx,
  landingIndexMapSvgHostSx,
  landingIndexMapTitleSx,
  landingIndexMapEyebrowSx,
} from "./landingIndexMap.ui";

type LandingIndexMapProps = {
  eyebrow: string;
  title: string;
  selectRegionLabel: string;
};

export function LandingIndexMap({
  eyebrow,
  title,
  selectRegionLabel,
}: LandingIndexMapProps) {
  const { t, language } = useTranslation();
  const {
    mapAreaRef,
    svgHostRef,
    activeTown,
    tooltipPos,
    dropdownOpen,
    dropdownLabel,
    regions,
    villages,
    isLoading,
    isError,
    selectRegion,
    selectTown,
    handleMapClick,
    setTownId,
    toggleDropdown,
  } = useLandingIndexMap(selectRegionLabel);

  const activeRegionName = regions.find(
    (region) => region.id === activeTown?.zoneId,
  )?.name;

  if (isError) return null;

  return (
    <Box
      component="section"
      id="anchor_button_map_search"
      sx={landingIndexMapSectionSx}
    >
      <Box aria-hidden sx={landingIndexMapPatternSx} />

      <Box sx={landingIndexMapInnerSx}>
        <Box sx={landingIndexMapLayoutSx}>
          <Box sx={landingIndexMapContentSx}>
            <Box component="header" sx={landingIndexMapHeadSx}>
              <Typography variant="h2" sx={{ m: 0 }}>
                <Typography component="span" sx={landingIndexMapEyebrowSx}>
                  {eyebrow}
                </Typography>
                <Typography component="span" sx={landingIndexMapTitleSx}>
                  {title}
                </Typography>
              </Typography>
            </Box>

            <Box sx={landingIndexMapRegionsRootSx}>
              {isLoading ? (
                <Skeleton
                  variant="rounded"
                  height={48}
                  sx={{ borderRadius: "999px", mb: 2 }}
                />
              ) : (
                <Button
                  type="button"
                  variant="contained"
                  onClick={toggleDropdown}
                  aria-expanded={dropdownOpen}
                  endIcon={
                    <KeyboardArrowDownIcon
                      sx={{
                        transition: "transform 0.3s",
                        transform: dropdownOpen
                          ? "rotate(180deg)"
                          : "rotate(0deg)",
                      }}
                    />
                  }
                  sx={landingIndexMapMobileTogglerSx}
                >
                  {dropdownLabel}
                </Button>
              )}

              <Box sx={landingIndexMapRegionsMenuSx(dropdownOpen)}>
                <Box component="ul" sx={landingIndexMapRegionsListSx}>
                  {isLoading
                    ? Array.from({ length: 6 }).map((_, i) => (
                        <Box key={i} component="li" sx={landingIndexMapRegionColSx}>
                          <Skeleton
                            variant="rounded"
                            height={52}
                            sx={{ borderRadius: "30px" }}
                          />
                        </Box>
                      ))
                    : regions.map((region) => (
                          <Box
                            component="li"
                            key={region.id}
                            sx={landingIndexMapRegionColSx}
                          >
                            <Box
                              role="button"
                              tabIndex={0}
                              data-id-zone={region.id}
                              onClick={() => selectRegion(region.id)}
                              onKeyDown={(e) =>
                                activateOnKeyboard(e, () =>
                                  selectRegion(region.id),
                                )
                              }
                              sx={landingIndexMapRegionItemSx}
                            >
                              <Typography
                                component="span"
                                sx={landingIndexMapRegionLabelSx}
                              >
                                {region.name}
                              </Typography>

                              <Box sx={landingIndexMapRegionIconSx}>
                                <ArrowForwardIosIcon sx={{ fontSize: 8 }} />
                              </Box>
                            </Box>
                          </Box>
                        ))}
                </Box>
              </Box>
            </Box>
          </Box>

          <Box
            onClick={handleMapClick}
            sx={{
              ...landingIndexMapAreaSx,
              position: "relative",
              borderRadius: "16px",
              padding: "12px",
              overflow: "visible",
            }}
          >
            <Box ref={mapAreaRef} sx={landingIndexMapSvgHostSx}>
              <Box ref={svgHostRef} sx={{ width: "100%" }} />

              {!isLoading &&
                villages.map((village) => (
                  <Box
                    key={village.id}
                    role="button"
                    tabIndex={0}
                    aria-label={village.title}
                    onClick={(e) => {
                      e.stopPropagation();
                      selectTown(village.id, e.clientX, e.clientY);
                    }}
                    onKeyDown={(e) => {
                      activateOnKeyboard(e, () =>
                        selectTown(village.id, 0, 0),
                      );
                    }}
                    sx={landingIndexMapMarkerSx(
                      village.coords.x,
                      village.coords.y,
                      activeTown?.id === village.id,
                    )}
                  >
                    <svg
                      width="20"
                      height="24"
                      viewBox="0 0 20 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        data-marker-pin
                        d="M10 0C4.47715 0 0 4.47715 0 10C0 17.5 10 24 10 24C10 24 20 17.5 20 10C20 4.47715 15.5228 0 10 0Z"
                      />
                      <circle data-marker-dot cx="10" cy="10" r="4" />
                    </svg>
                  </Box>
                ))}

              {activeTown && (
                <Box sx={landingIndexMapPopoverSx(tooltipPos.x, tooltipPos.y)}>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "flex-start",
                      justifyContent: "space-between",
                      gap: 1,
                    }}
                  >
                    <Box
                      component="a"
                      href={vtfUrl(activeTown.href, language)}
                      target="_blank"
                      rel="noopener noreferrer"
                      sx={{
                        cursor: "pointer",
                        color: "inherit",
                        textDecoration: "none",
                      }}
                    >
                      <Typography sx={landingIndexMapPopoverRegionSx}>
                        {activeRegionName}
                      </Typography>

                      <Typography sx={landingIndexMapPopoverQuoteSx}>
                        “{activeTown.title}”
                      </Typography>
                    </Box>

                    <Box
                      role="button"
                      tabIndex={0}
                      aria-label={t("landing.indexMap.closeMarker")}
                      onClick={(event) => {
                        event.stopPropagation();
                        setTownId(null);
                      }}
                      onKeyDown={(e) => {
                        activateOnKeyboard(e, () => setTownId(null));
                      }}
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: 24,
                        height: 24,
                        borderRadius: "50%",
                        cursor: "pointer",
                        transition: "all 0.2s ease",
                        "&:hover": {
                          backgroundColor: "rgba(0,0,0,0.06)",
                        },
                      }}
                    >
                      <CloseIcon sx={{ fontSize: "var(--vtf-font-md)" }} />
                    </Box>
                  </Box>

                  <Box>
                    {activeTown.department ? (
                      <Typography sx={landingIndexMapPopoverDetailsSx}>
                        {activeTown.department}
                      </Typography>
                    ) : null}

                    <Typography sx={landingIndexMapPopoverPlaceSx}>
                      {activeTown.place}
                    </Typography>
                  </Box>
                </Box>
              )}
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
