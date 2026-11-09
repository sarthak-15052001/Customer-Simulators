import * as React from "react";
import { Box, Button, Typography, IconButton, Tooltip } from "../../ui";
import CircularProgress from "@mui/material/CircularProgress";
import ShareRoundedIcon from "@mui/icons-material/ShareRounded";
import PrintRoundedIcon from "@mui/icons-material/PrintRounded";
import EmailRoundedIcon from "@mui/icons-material/EmailRounded";
import LaunchRoundedIcon from "@mui/icons-material/LaunchRounded";
import { VtfGlassCard } from "../../shared/VtfGlassCard";

import type { FamilyState } from "../../../types/familyTab";
import type { SejourState } from "../../../types/stayTab";
import type { VtfVillage } from "../../../data/vtfStay";
import type { SejourEstimate } from "../../../utils/stayEstimate";
import { formatEuro } from "./_format";
import { useTranslation } from "../../../contexts/LanguageContext";
import { useSimulateurTabTranslation } from "../../../hooks/useSimulateurTabTranslation";
import { RECAP_META, RECAP_SURFACE } from "./recapCard.ui";

import { EmailSimulationModal } from "./EmailSimulationModal";

export function CtaActionsCard({
  family,
  sejour,
  village,
  estimate,
  bookingUrl,
  bookingUrlReady = true,
  onDownloadPdf,
  pdfDownloading = false,
  pdfDisabled = false,
}: {
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
  estimate: SejourEstimate | null;
  bookingUrl: string;
  bookingUrlReady?: boolean;
  onDownloadPdf?: () => void | Promise<void>;
  pdfDownloading?: boolean;
  pdfDisabled?: boolean;
}) {
  const { t } = useTranslation();
  const td = useSimulateurTabTranslation("details");

  const [emailOpen, setEmailOpen] = React.useState(false);
  const [feedback, setFeedback] = React.useState<string | null>(null);

  const shareText = React.useMemo(() => {
    const title = t("simulateur.details.page.title");
    const summary = estimate
      ? `${t("simulateur.recap.estimatedBudget")}: ${formatEuro(estimate.total)}`
      : `${t("simulateur.recap.estimatedBudget")}: -`;
    const dest = village
      ? td("cta.shareDestination").replace("{{name}}", village.nom)
      : td("cta.shareDestination").replace("{{name}}", "-");
    const dates =
      sejour.dateDebut && sejour.dateFin
        ? td("cta.shareDates")
            .replace("{{start}}", sejour.dateDebut)
            .replace("{{end}}", sejour.dateFin)
        : "";
    const linkLine = td("cta.shareVtfLinkLine").replace("{{url}}", bookingUrl);
    return [title, summary, dest, dates, linkLine].filter(Boolean).join("\n");
  }, [bookingUrl, estimate, sejour.dateDebut, sejour.dateFin, t, td, village]);

  const onShare = async () => {
    setFeedback(null);
    try {
      if (navigator.share) {
        await navigator.share({
          title: t("simulateur.header.title"),
          text: shareText,
        });
        setFeedback(td("cta.shared"));
        return;
      }
      await navigator.clipboard.writeText(bookingUrl);
      setFeedback(td("cta.copied"));
    } catch {
      setFeedback(td("cta.shareError"));
    }
    setTimeout(() => setFeedback(null), 3000);
  };

  return (
    <VtfGlassCard
      glassSx={{
        textAlign: "center",
        bgcolor: RECAP_SURFACE.ctaCard.bg,
        backgroundImage: "url(/estimation_bg.png)",
        backgroundSize: "cover",
        backgroundPosition: "center",
        border: `1.25px solid ${RECAP_SURFACE.ctaCard.border}`,
        p: { xs: 2.5, sm: 3 },
        borderRadius: 3,
        boxShadow: "0 16px 40px rgba(242, 166, 128, 0.1)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <LaunchRoundedIcon
        sx={{
          position: "absolute",
          right: -20,
          top: -20,
          fontSize: 120,
          opacity: 0.03,
          color: "var(--vtf-orange)",
          transform: "rotate(-15deg)",
        }}
      />

      <Box sx={{ position: "relative", zIndex: 1 }}>
        <Typography
          sx={{
            fontSize: "var(--vtf-font-sm)",
            color: "var(--vtf-orange)",
            fontWeight: 950,
            textTransform: "uppercase",
            letterSpacing: "0.15em",
            mb: 1,
          }}
        >
          {td("cta.header")}
        </Typography>

        <Typography
          variant="h4"
          sx={{
            fontSize: { xs: 20, sm: 24 },
            fontWeight: 980,
            color: "var(--vtf-navy)",
            mb: 1.25,
            letterSpacing: "-0.025em",
            lineHeight: 1.1,
          }}
        >
          {village ? village.nom : "-"}
        </Typography>

        <Box
          sx={{
            display: "inline-flex",
            alignItems: "center",
            gap: 1.5,
            mb: 2.5,
            px: 1.75,
            py: 0.6,
            borderRadius: "99px",
            bgcolor: "rgba(242,166,128,0.08)",
            border: "1px solid rgba(242,166,128,0.12)",
          }}
        >
          <Typography sx={RECAP_META.bodyStrong}>
            {sejour.fNuits}{" "}
            {t(
              `simulateur.recap.night${sejour.fNuits > 1 ? "Plural" : "Singular"}`,
            )}
          </Typography>
          <Box
            sx={{
              width: 4,
              height: 4,
              borderRadius: "50%",
              bgcolor: "rgba(0,68,90,0.15)",
            }}
          />
          <Typography
            sx={{ ...RECAP_META.bodyStrong, color: "var(--vtf-orange)" }}
          >
            {sejour.fSaison || "-"}
          </Typography>
        </Box>

        <Box sx={{ mb: 3 }}>
          <Button
            vtfVariant="orangeFill"
            {...({
              component: "a",
              href: bookingUrlReady ? bookingUrl : undefined,
              target: "_blank",
              rel: "noopener noreferrer",
            } as const)}
            aria-disabled={!bookingUrlReady}
            onClick={(e) => {
              if (!bookingUrlReady) e.preventDefault();
            }}
            sx={{
              py: 1.5,
              px: { xs: 3, sm: 5 },
              fontSize: "var(--vtf-font-md)",
              fontWeight: 980,
              borderRadius: "14px",
              boxShadow: "0 8px 24px rgba(212,112,42,0.2)",
              textTransform: "none",
              width: { xs: "100%", sm: "auto" },
              transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
              pointerEvents: bookingUrlReady ? "auto" : "none",
              opacity: bookingUrlReady ? 1 : 0.55,
              textDecoration: "none",
              color: "inherit",
              "&:hover": {
                bgcolor: "#f2a680",
                transform: bookingUrlReady ? "translateY(-2px)" : "none",
                boxShadow: bookingUrlReady
                  ? "0 12px 32px rgba(212,112,42,0.25)"
                  : "0 8px 24px rgba(212,112,42,0.2)",
              },
            }}
          >
            <LaunchRoundedIcon
              sx={{ fontSize: "var(--vtf-font-lg)", mr: 1.25 }}
            />
            {td("cta.vtfLink")}
          </Button>
        </Box>

        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 2,
          }}
        >
          <Box
            sx={{
              display: "flex",
              width: "100%",
              alignItems: "center",
              gap: 2,
              mb: 1,
              "&::before, &::after": {
                content: '""',
                flex: 1,
                height: "1px",
                bgcolor: "#e2e8ec",
              },
            }}
          >
            <Typography
              sx={{
                ...RECAP_META.captionStrong,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              {td("cta.shareDivider")}
            </Typography>
          </Box>

          <Box
            sx={{
              display: "flex",
              justifyContent: "center",
              gap: 1.5,
              flexWrap: "wrap",
            }}
          >
            <Tooltip title={td("cta.share")}>
              <IconButton
                type="button"
                onClick={onShare}
                aria-label={td("cta.share")}
                sx={actionIconSx}
              >
                <ShareRoundedIcon />
              </IconButton>
            </Tooltip>

            <Tooltip title={td("cta.email")}>
              <IconButton
                type="button"
                onClick={() => setEmailOpen(true)}
                aria-label={td("cta.email")}
                sx={actionIconSx}
              >
                <EmailRoundedIcon />
              </IconButton>
            </Tooltip>

            <Tooltip title={td("cta.downloadPdf")}>
              <span>
                <IconButton
                  type="button"
                  onClick={() => void onDownloadPdf?.()}
                  disabled={pdfDisabled || pdfDownloading || !onDownloadPdf}
                  aria-label={td("cta.downloadPdf")}
                  aria-busy={pdfDownloading}
                  sx={actionIconSx}
                >
                  {pdfDownloading ? (
                    <CircularProgress
                      size={22}
                      sx={{ color: "var(--vtf-navy)" }}
                    />
                  ) : (
                    <PrintRoundedIcon />
                  )}
                </IconButton>
              </span>
            </Tooltip>
          </Box>
        </Box>
      </Box>

      {feedback && (
        <Typography sx={{ ...RECAP_META.note, mt: 2 }}>{feedback}</Typography>
      )}

      <EmailSimulationModal
        open={emailOpen}
        onClose={() => setEmailOpen(false)}
        family={family}
        sejour={sejour}
        village={village}
        estimate={estimate}
        bookingUrl={bookingUrl}
      />
    </VtfGlassCard>
  );
}

const actionIconSx = {
  width: 44,
  height: 44,
  bgcolor: "white",
  border: "1.5px solid rgba(0,68,90,0.06)",
  color: "var(--vtf-navy)",
  transition: "all 0.2s ease",
  "&:hover": {
    bgcolor: "rgba(0,68,90,0.03)",
    borderColor: "rgba(0,68,90,0.12)",
    transform: "translateY(-1px)",
  },
  "& svg": { fontSize: 20 },
};
