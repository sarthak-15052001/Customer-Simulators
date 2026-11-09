/* eslint-disable @typescript-eslint/no-explicit-any */
import * as React from "react";
import {
  Dialog,
  IconButton,
  Box,
  Typography,
  TextField,
  Button,
} from "@mui/material";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import EmailRoundedIcon from "@mui/icons-material/EmailRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import ErrorRoundedIcon from "@mui/icons-material/ErrorRounded";
import { useMutation } from "@tanstack/react-query";
import { mailerApi } from "../../../api/mailer.api";
import { buildEstimateStayRequestBody } from "../../../api/stayEstimate.api";
import type { VtfVillage } from "../../../data/vtfStay";
import type { SejourEstimate } from "../../../utils/stayEstimate";
import type { FamilyState } from "../../../types/familyTab";
import type { SejourState } from "../../../types/stayTab";
import { useFormules } from "../../../hooks/formules.hooks";
import { useSimulateurTabTranslation } from "../../../hooks/useSimulateurTabTranslation";
import { useTranslation } from "../../../contexts/LanguageContext";
import { getFormuleLabelFromCatalog } from "../stay/StayFormulePicker.shared";
import { resolveStayIncludesText } from "../../../utils/stayEstimate";
import { RECAP_META } from "./recapCard.ui";

export type EmailSimulationModalProps = {
  open: boolean;
  onClose: () => void;
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
  estimate: SejourEstimate | null;
  bookingUrl: string;
};

export function EmailSimulationModal({
  open,
  onClose,
  family,
  sejour,
  village,
  estimate,
  bookingUrl,
}: EmailSimulationModalProps) {
  const { t } = useTranslation();
  const [email, setEmail] = React.useState("");
  const [isSuccess, setIsSuccess] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const td = useSimulateurTabTranslation("details");
  const { data: apiFormules } = useFormules();

  const sendMutation = useMutation({
    mutationFn: mailerApi.sendSimulation,
    onSuccess: () => {
      setIsSuccess(true);
      setTimeout(() => {
        setIsSuccess(false);
        setEmail("");
        onClose();
      }, 2500);
    },
    onError: (err: any) => {
      setError(err.message || td("cta.sendError") || "Error sending email");
    },
  });

  const handleSubmit = () => {
    setError(null);
    const addr = email.trim();
    const isValidEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(addr);
    if (!addr || !isValidEmail) {
      setError(td("cta.emailInvalid") || "Email invalide");
      return;
    }

    const simulationData = buildEstimateStayRequestBody({
      villageId: sejour.villageId,
      family,
      sejour,
    });

    if (!simulationData) {
      setError(td("cta.invalidData") || "Données de simulation invalides");
      return;
    }

    const childAges =
      family.enfants.length > 0
        ? family.enfants.map((e) => `${e.age} ${td("stay.years")}`).join(" · ")
        : "";

    const transportLabel =
      sejour.transport?.mode === "car"
        ? t("simulateur.transport.carOneWay").replace(
            "{{km}}",
            String(sejour.transport?.distanceOneWayKm || 0),
          )
        : sejour.transport?.mode === "train"
          ? t("simulateur.transport.trainTitle")
          : td("recapCard.details.transportTotalLine");

    sendMutation.mutate({
      recipientEmail: addr,
      villageName: village?.nom ?? "",
      nuits: estimate?.nuits ?? sejour.fNuits ?? 0,
      saison: estimate?.saisonKey ?? sejour.fSaison ?? "",
      dateDebut: sejour.dateDebut ?? "",
      dateFin: sejour.dateFin ?? "",
      adultes: family.adultes,
      formule: getFormuleLabelFromCatalog(sejour.formule, apiFormules),
      perPersonPerDay: estimate?.displayMetrics?.perPersonPerDay ?? 0,
      perDayFamily: estimate?.displayMetrics?.perDayFamily ?? 0,
      total: estimate?.total ?? 0,
      perPerson: estimate?.perPerson ?? 0,
      perAdultBase: estimate?.perAdultBase ?? 0,
      totalAdults: estimate?.totalAdults ?? 0,
      totalChildren: estimate?.totalChildren ?? 0,
      adhesion: estimate?.adhesion ?? 0,
      staySubtotal: estimate?.staySubtotal ?? 0,
      activitiesTotal: estimate?.activitiesTotal ?? 0,
      restoTotal: estimate?.restoTotal ?? 0,
      transportTotal: estimate?.transportTotal ?? 0,
      hotelEstimate: estimate?.hotelEstimate ?? 0,
      hotelSavings: estimate?.hotelSavings ?? 0,
      savingsPct: estimate?.displayMetrics?.savingsPct ?? 0,
      formulaIncludes:
        resolveStayIncludesText(sejour.formule, estimate?.includes) ?? "",
      childAges,
      transportLabel: transportLabel ?? "",
      bookingUrl,
      simulationData,
    });
  };

  const dialogTitleId = "email-simulation-dialog-title";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      aria-labelledby={dialogTitleId}
      slotProps={{
        paper: {
          sx: {
            borderRadius: 5,
            bgcolor: "#ffffff",
            backgroundImage: "url(/estimation_bg.png)",
            backgroundSize: "cover",
            backgroundPosition: "center",
            backdropFilter: "blur(30px)",
            border: "1.5px solid rgba(242, 166, 128, 0.25)",
            width: "100%",
            maxWidth: 440,
            p: 0.5,
            boxShadow: "0 32px 80px rgba(0,0,0,0.15)",
            position: "relative",
            overflow: "hidden",
          },
        },
      }}
    >
      <EmailRoundedIcon
        sx={{
          position: "absolute",
          right: -30,
          bottom: -30,
          fontSize: 180,
          opacity: 0.035,
          color: "var(--vtf-orange)",
          transform: "rotate(-10deg)",
          zIndex: 0,
        }}
      />

      <IconButton
        type="button"
        onClick={onClose}
        aria-label={t("simulateur.stay.resultsFilterModalClose")}
        sx={{
          position: "absolute",
          right: 12,
          top: 12,
          bgcolor: "white",
          zIndex: 10,
          boxShadow: "0 6px 16px rgba(0,0,0,0.06)",
          border: "1px solid rgba(0,0,0,0.04)",
          color: "var(--vtf-navy)",
          transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
          "&:hover": { bgcolor: "#f1f5f9", transform: "rotate(90deg)" },
        }}
      >
        <CloseRoundedIcon sx={{ fontSize: 'var(--vtf-font-lg)' }} />
      </IconButton>

      <Box
        sx={{
          p: { xs: 4, sm: 5 },
          textAlign: "center",
          position: "relative",
          zIndex: 1,
        }}
      >
        {isSuccess ? (
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              py: 4,
            }}
          >
            <Box
              sx={{
                width: 80,
                height: 80,
                borderRadius: "50%",
                bgcolor: "rgba(0,168,181,0.1)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                mb: 3,
                animation: "pulse 2s infinite",
              }}
            >
              <CheckCircleRoundedIcon
                sx={{ fontSize: 40, color: "var(--vtf-teal)" }}
              />
            </Box>
            <Typography
              sx={{
                fontSize: 20,
                fontWeight: 980,
                color: "var(--vtf-navy)",
                mb: 1,
              }}
            >
              {td("cta.successTitle") || "C'est parti !"}
            </Typography>
            <Typography sx={RECAP_META.bodyMuted}>
              {td("cta.emailOpening") || "L'email a été envoyé avec succès."}
            </Typography>
          </Box>
        ) : sendMutation.isError ? (
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              py: 4,
            }}
          >
            <Box
              sx={{
                width: 80,
                height: 80,
                borderRadius: "50%",
                bgcolor: "rgba(211, 47, 47, 0.1)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                mb: 3,
              }}
            >
              <ErrorRoundedIcon sx={{ fontSize: 40, color: "#d32f2f" }} />
            </Box>
            <Typography
              sx={{
                fontSize: 20,
                fontWeight: 980,
                color: "var(--vtf-navy)",
                mb: 1,
              }}
            >
              {td("cta.errorTitle") || "Oups !"}
            </Typography>
            <Typography sx={{ ...RECAP_META.bodyMuted, mb: 4 }}>
              {sendMutation.error?.message ||
                td("cta.sendError") ||
                "Une erreur est survenue lors de l'envoi."}
            </Typography>
            <Button
              variant="contained"
              onClick={() => sendMutation.reset()}
              sx={{
                bgcolor: "var(--vtf-navy)",
                color: "white",
                height: 48,
                borderRadius: "12px",
                px: 4,
                fontSize: 'var(--vtf-font-md)',
                fontWeight: 900,
                textTransform: "none",
                "&:hover": { bgcolor: "#003344" },
              }}
            >
              {td("cta.retry") || "Réessayer"}
            </Button>
          </Box>
        ) : (
          <>
            <Box
              sx={{
                width: 72,
                height: 72,
                borderRadius: "24px",
                bgcolor: "white",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                mx: "auto",
                mb: 3,
                boxShadow: "0 12px 24px rgba(242,166,128,0.15)",
                border: "1px solid rgba(242,166,128,0.1)",
              }}
            >
              <EmailRoundedIcon
                sx={{ fontSize: 36, color: "var(--vtf-orange)" }}
              />
            </Box>

            <Typography
              id={dialogTitleId}
              component="h2"
              sx={{
                fontSize: 22,
                fontWeight: 980,
                color: "var(--vtf-navy)",
                mb: 1.5,
                letterSpacing: "-0.02em",
                lineHeight: 1.2,
              }}
            >
              {td("cta.emailTitle")}
            </Typography>

            <Typography sx={{ ...RECAP_META.bodyMuted, mb: 4, px: 2 }}>
              {td("cta.emailDesc")}
            </Typography>

            <Box
              component="form"
              noValidate
              onSubmit={(e: React.FormEvent) => {
                e.preventDefault();
                handleSubmit();
              }}
              sx={{ position: "relative" }}
            >
              <TextField
                fullWidth
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                
                placeholder={td("cta.emailPlaceholder")}
                error={!!error}
                helperText={error}
                disabled={sendMutation.isPending}
                slotProps={{
                  htmlInput: {
                    type: "email",
                    autoComplete: "email",
                    "aria-label": td("cta.emailPlaceholder"),
                  },
                }}
                sx={{
                  mb: 2.5,
                  "& .MuiOutlinedInput-root": {
                    borderRadius: "16px",
                    bgcolor: "white",
                    fontWeight: 850,
                    fontSize: 'var(--vtf-font-md)',
                    height: 54,
                    boxShadow: "0 2px 8px rgba(0,0,0,0.02)",
                    "& fieldset": { borderColor: "rgba(0,68,90,0.1)" },
                    "&:hover fieldset": {
                      borderColor: "rgba(242,166,128,0.3)",
                    },
                    "&.Mui-focused fieldset": {
                      borderColor: "var(--vtf-orange)",
                      borderWidth: 1.5,
                    },
                  },
                  "& .MuiFormHelperText-root": {
                    fontWeight: 850,
                    mx: 1,
                    fontSize: 'var(--vtf-font-sm)',
                  },
                }}
              />

              <Button
                type="submit"
                fullWidth
                variant="contained"
                disabled={sendMutation.isPending}
                sx={{
                  bgcolor: "var(--vtf-orange)",
                  color: "white",
                  height: 54,
                  borderRadius: "16px",
                  fontSize: 'var(--vtf-font-md)',
                  fontWeight: 980,
                  textTransform: "none",
                  boxShadow: "0 12px 32px rgba(242,166,128,0.3)",
                  transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                  "&:hover": {
                    bgcolor: "#e57c45",
                    transform: "translateY(-2px)",
                    boxShadow: "0 16px 40px rgba(242,166,128,0.4)",
                  },
                  "&.Mui-disabled": {
                    bgcolor: "rgba(242,166,128,0.5)",
                    color: "rgba(255,255,255,0.8)",
                  },
                }}
              >
                {sendMutation.isPending
                  ? td("cta.sending") || "Envoi en cours..."
                  : td("cta.send")}
              </Button>
            </Box>
          </>
        )}
      </Box>
    </Dialog>
  );
}
