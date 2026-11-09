import * as React from "react";
import { Box, Toolbar, Button, Container, Link } from "../ui";
import PersonOutlineRoundedIcon from "@mui/icons-material/PersonOutlineRounded";
import { useTranslation } from "../../contexts/LanguageContext";
import { useNavigate } from "react-router-dom";
import { getVtfOrigin, vtfUrl } from "../../config/site";
import { HeaderVillageSearchTrigger } from "./HeaderVillageSearchTrigger";
import { VtfCallBackIcon, VtfCountryFlag } from "./HeaderIcons";
import { VTF_HEADER, headerSearchFieldSx } from "./headerVtfStyles";
import { VTF_FONT } from "../ui/vtfTypography";
import { VtfLogoMark } from "../shared/VtfLogoMark";

const loadHeaderVillageSearch = () => import("./HeaderVillageSearch");
const HeaderVillageSearch = React.lazy(loadHeaderVillageSearch);

function customerAreaUrl(path: string) {
  if (path.startsWith("http")) return path;
  return `${getVtfOrigin()}/${path.replace(/^\/+/, "")}`;
}

const searchFallbackSx = {
  ...headerSearchFieldSx,
  display: { xs: "none", sm: "block" },
  bgcolor: "#ffffff",
  border: VTF_HEADER.search.border,
  borderRadius: VTF_HEADER.search.borderRadius,
} as const;

export function HeaderMainBar() {
  const { t, language } = useTranslation();
  const navigate = useNavigate();
  const [searchActive, setSearchActive] = React.useState(false);
  const myAccountUrl = customerAreaUrl(t("header.mainBar.myAccountUrl"));

  const prefetchVillageSearch = React.useCallback(() => {
    void loadHeaderVillageSearch();
  }, []);

  React.useEffect(() => {
    prefetchVillageSearch();
  }, [prefetchVillageSearch]);

  return (
    <Toolbar
      disableGutters
      sx={{
        minHeight: VTF_HEADER.main.minHeight,
        height: VTF_HEADER.main.minHeight,
        px: 0,
        bgcolor: "#ffffff",
      }}
    >
      <Container maxWidth="xl" sx={{ position: "relative" }}>
        <Box
          sx={{
            position: "relative",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "44px",
            width: "100%",
          }}
        >
          <Box
            sx={{
              display: "inline-flex",
              alignItems: "center",
              height: VTF_HEADER.main.minHeight,
              cursor: "pointer",
              flexShrink: 0,
            }}
            onClick={() => navigate("/")}
          >
            <Box sx={{ display: { xs: "block", md: "none" } }}>
              <VtfLogoMark height={VTF_HEADER.logo.heightSm} />
            </Box>
            <Box
              sx={{
                display: { xs: "none", md: "block" },
                pb: 1,
              }}
            >
              <VtfLogoMark height={VTF_HEADER.logo.height} />
            </Box>
          </Box>

          <Box
            sx={{
              display: { xs: "none", lg: "inline-flex" },
              alignItems: "center",
              height: VTF_HEADER.main.minHeight,
              pl: "55px",
              flexShrink: 0,
            }}
          >
            <VtfCallBackIcon />
            <Box sx={{ ml: "15px", mr: "20px" }}>
              <Link
                href={vtfUrl(t("header.mainBar.contactUrl"), language)}
                target="_blank"
                rel="noopener noreferrer"
                sx={{
                  fontFamily: "var(--sans)",
                  fontSize: VTF_HEADER.contact.linkFontSize,
                  lineHeight: VTF_HEADER.contact.linkLineHeight,
                  fontWeight: VTF_HEADER.contact.linkWeight,
                  color: VTF_HEADER.contact.linkColor,
                  textDecoration: "underline",
                  display: "block",
                }}
              >
                {t("header.mainBar.contact")}
              </Link>
              <Box
                sx={{
                  display: "flex",
                  gap: "1rem",
                  flexWrap: "wrap",
                  mt: "0.1rem",
                }}
              >
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                  }}
                >
                  <VtfCountryFlag src={VTF_HEADER.flags.france} alt="France" />
                  <Link
                    href="tel:0442123200"
                    sx={{
                      fontFamily: "var(--sans)",
                      fontSize: VTF_HEADER.contact.phoneFontSize,
                      lineHeight: VTF_HEADER.contact.phoneLineHeight,
                      fontWeight: VTF_HEADER.contact.phoneWeight,
                      color: VTF_HEADER.contact.phoneColor,
                      textDecoration: "none",
                    }}
                  >
                    04 42 123 200
                  </Link>
                </Box>
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                  }}
                >
                  <VtfCountryFlag
                    src={VTF_HEADER.flags.belgique}
                    alt="Belgique"
                  />
                  <Link
                    href="tel:+3225461410"
                    sx={{
                      fontFamily: "var(--sans)",
                      fontSize: VTF_HEADER.contact.phoneFontSize,
                      lineHeight: VTF_HEADER.contact.phoneLineHeight,
                      fontWeight: VTF_HEADER.contact.phoneWeight,
                      color: VTF_HEADER.contact.phoneColor,
                      textDecoration: "none",
                    }}
                  >
                    +32 2 546 14 10
                  </Link>
                </Box>
              </Box>
            </Box>
          </Box>

          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              height: VTF_HEADER.main.minHeight,
              ml: "auto",
              gap: 0,
            }}
          >
            {searchActive ? (
              <React.Suspense fallback={<Box sx={searchFallbackSx} />}>
                <HeaderVillageSearch autoFocus />
              </React.Suspense>
            ) : (
              <HeaderVillageSearchTrigger
                placeholder={t("header.mainBar.searchDestination")}
                onPrefetch={prefetchVillageSearch}
                onActivate={() => setSearchActive(true)}
              />
            )}

            <Button
              onClick={() => window.open(myAccountUrl, "_blank")}
              sx={{
                ml: "10px",
                minWidth: VTF_HEADER.accountBtn.minWidth,
                height: VTF_HEADER.accountBtn.height,
                px: VTF_HEADER.accountBtn.px,
                py: VTF_HEADER.accountBtn.py,
                bgcolor: VTF_HEADER.accountBtn.bg,
                color: "#ffffff",
                borderRadius: VTF_HEADER.accountBtn.borderRadius,
                fontFamily: "var(--sans)",
                fontSize: VTF_HEADER.accountBtn.fontSize,
                lineHeight: VTF_HEADER.accountBtn.lineHeight,
                fontWeight: VTF_HEADER.accountBtn.fontWeight,
                textTransform: "none",
                boxShadow: "none",
                whiteSpace: "nowrap",
                "&:hover": {
                  bgcolor: VTF_HEADER.accountBtn.hoverBg,
                  boxShadow: "none",
                },
              }}
              startIcon={
                <PersonOutlineRoundedIcon
                  sx={{
                    fontSize: `${VTF_FONT.lg} !important`,
                    color: "#ffffff",
                  }}
                />
              }
            >
              {t("header.mainBar.myAccount")}
            </Button>
          </Box>
        </Box>
      </Container>
    </Toolbar>
  );
}
