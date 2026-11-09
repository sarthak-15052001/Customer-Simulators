import { useTranslation } from "../../../contexts/LanguageContext";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";

export function DetailsEstimateErrorState({
  onRetry,
  errorMessage,
}: {
  onRetry?: () => void;
  errorMessage?: string | null;
}) {
  const { t } = useTranslation();

  return (
    <VtfErrorAlert
      title={t("simulateur.recap.estimateErrorTitle")}
      message={errorMessage || t("simulateur.recap.estimateErrorMessage")}
      onRetry={onRetry}
      retryLabel={t("simulateur.family.retry")}
    />
  );
}
