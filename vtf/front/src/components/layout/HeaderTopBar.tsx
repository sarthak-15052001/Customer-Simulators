import * as React from "react";
import { Box, Container } from "../ui";
import { VtfSelect } from "../ui/Select";
import { useTranslation } from "../../contexts/LanguageContext";
import type { Language } from "../../contexts/LanguageContext";
import { VTF_HEADER } from "./headerVtfStyles";
import { vtfTopbarFloralPatternOverlaySx } from "./vtfFloralPattern";
import { useHeaderBanner } from "../../hooks/headerBanner.hooks";

function TopbarLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <strong>
      <a
        className="vtf-topbar-link"
        href={href}
        target="_blank"
        rel="noopener noreferrer"
      >
        {children}
      </a>
    </strong>
  );
}

export function HeaderTopBar() {
  const { language, setLanguage } = useTranslation();

  const { data: bannerData } = useHeaderBanner(language);

  const hasDynamicBanner =
    bannerData?.is_active &&
    Array.isArray(bannerData.segments) &&
    bannerData.segments.length > 0;

  const langOptions = [
    { value: "FR", label: "FR" },
    { value: "GB", label: "GB" },
    { value: "ES", label: "ES" },
    { value: "NL", label: "NL" },
  ] as { value: Language; label: string }[];

  return (
    <Box
      className="vtf-topbar"
      sx={{
        boxSizing: "border-box",
        minHeight: `${VTF_HEADER.topbar.minHeight}px`,
        pt: VTF_HEADER.topbar.paddingTop,
        pb: VTF_HEADER.topbar.paddingBottom,
        position: "relative",
        zIndex: 11,
        overflow: "hidden",
        overflowY: "hidden",
      }}
    >
      <Box
        aria-hidden
        sx={vtfTopbarFloralPatternOverlaySx({
          opacity: VTF_HEADER.topbar.patternOpacity,
          tileSize: VTF_HEADER.topbar.patternSize,
        })}
      />
      <Container maxWidth="xl" sx={{ position: "relative", zIndex: 1 }}>
        <Box
          sx={{
            position: "relative",
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Box
            className="vtf-topbar-copy"
            sx={{
              width: "100%",
              pr: { xs: "70px", md: `${VTF_HEADER.topbar.langPaddingRight}px` },
              pl: { xs: "10px", md: "20px" },
              boxSizing: "border-box",
            }}
          >
            <p className="vtf-topbar-copy-line">
              {hasDynamicBanner
                ? bannerData.segments.map((seg, idx) => {
                    if (seg.type === "link" && seg.href) {
                      return (
                        <TopbarLink key={idx} href={seg.href}>
                          {seg.text || seg.value}
                        </TopbarLink>
                      );
                    }
                    return (
                      <React.Fragment key={idx}>
                        {seg.value || seg.text}
                      </React.Fragment>
                    );
                  })
                : null}
            </p>
          </Box>

          <Box
            sx={{
              position: "absolute",
              right: 0,
              top: "50%",
              transform: "translateY(-50%)",
              zIndex: 1,
              display: "flex",
              alignItems: "center",
            }}
          >
            <VtfSelect
              options={langOptions}
              value={language}
              onChange={(v) => setLanguage(v as Language)}
              variant="topbar"
              size="compact"
              showIcons={false}
              menuWidth={80}
              menuAlign="right"
              className="lang-selector-nav"
            />
          </Box>
        </Box>
      </Container>
    </Box>
  );
}
