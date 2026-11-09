import * as React from "react";
import { useToast } from "../components/ui";
import { useTranslation } from "../contexts/LanguageContext";
import { buildSimulationPdfFileName } from "../utils/simulationPdfFileName";
import type { FamilyState } from "../types/familyTab";
import type { SejourState } from "../types/stayTab";
import type { VtfVillage } from "../data/vtfStay";
import type { SejourEstimate } from "../utils/stayEstimate";
import { useSimulateurTabTranslation } from "./useSimulateurTabTranslation";
import { useFormules } from "./formules.hooks";
import { getFormuleLabelFromCatalog } from "../components/simulateur-vtf/stay/StayFormulePicker.shared";
import { resolveStayIncludesText } from "../utils/stayEstimate";
import {
  simulationPdfApi,
  buildSimulationPdfPayload,
} from "../api/simulationPdf.api";

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName.endsWith(".pdf") ? fileName : `${fileName}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function useSimulationPdfDownload(args: {
  family: FamilyState;
  sejour: SejourState;
  village: VtfVillage | null;
  estimate: SejourEstimate | null;
  bookingUrl: string;
  disabled?: boolean;
}) {
  const { t, language } = useTranslation();
  const td = useSimulateurTabTranslation("details");
  const toast = useToast();
  const { data: apiFormules } = useFormules();

  const [isDownloading, setIsDownloading] = React.useState(false);

  const downloadPdf = React.useCallback(async () => {
    if (args.disabled || !args.estimate) return;

    setIsDownloading(true);
    try {
      const transportLabel =
        args.sejour.transport?.mode === "car"
          ? t("simulateur.transport.carOneWay").replace(
              "{{km}}",
              String(args.sejour.transport?.distanceOneWayKm || 0),
            )
          : args.sejour.transport?.mode === "train"
            ? t("simulateur.transport.trainTitle")
            : td("recapCard.details.transportTotalLine");

      const transportModeLabel =
        args.sejour.transport?.mode === "car"
          ? t("simulateur.transport.carTitle")
          : args.sejour.transport?.mode === "train"
            ? t("simulateur.transport.trainTitle")
            : td("recapCard.details.transportTotalLine");

      const formuleLabel = getFormuleLabelFromCatalog(
        args.sejour.formule,
        apiFormules,
      );

      const payload = buildSimulationPdfPayload({
        family: args.family,
        sejour: args.sejour,
        village: args.village,
        estimate: args.estimate,
        bookingUrl: args.bookingUrl,
        language,
        formuleLabel,
        formuleIncludesText:
          resolveStayIncludesText(
            args.sejour.formule,
            args.estimate.includes,
          ) ?? "",
        transportModeLabel,
        transportDetailNote: transportLabel ?? "",
      });

      const blob = await simulationPdfApi.generate(payload);
      downloadBlob(
        blob,
        buildSimulationPdfFileName(
          args.village?.nom,
          args.sejour.dateDebut,
          args.sejour.dateFin,
        ),
      );
    } catch (err) {
      console.error("[PDF] API download failed", err);
      toast.error(t("simulateur.details.print.downloadError"));
    } finally {
      setIsDownloading(false);
    }
  }, [
    apiFormules,
    args.bookingUrl,
    args.disabled,
    args.estimate,
    args.family,
    args.sejour,
    args.village,
    language,
    t,
    td,
    toast,
  ]);

  return { downloadPdf, isDownloading };
}
