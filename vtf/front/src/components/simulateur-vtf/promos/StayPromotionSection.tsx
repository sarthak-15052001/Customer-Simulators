import { Box } from "../../ui";
import { useTranslation } from "../../../contexts/LanguageContext";
import type { PromoChoice } from "../../../data/vtfPromos";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";
import { PromoCard } from "./PromoCard";
import { PromosStayPromosSkeleton } from "./PromosStayPromosSkeleton";

export function StayPromotionSection(props: {
  tp: (k: string) => string;
  catalog: PromoChoice[];
  available: PromoChoice[];
  selectedKey: PromoChoice["key"];
  hasStayDates?: boolean;
  hasVillage?: boolean;
  isCatalogLoading?: boolean;
  isCatalogError?: boolean;
  isAvailableLoading?: boolean;
  isAvailableError?: boolean;
  onRetryCatalog?: () => void;
  onRetryAvailable?: () => void;
  onSelectNone: () => void;
  onSelectPromo: (choice: PromoChoice) => void;
}) {
  const {
    tp,
    catalog,
    available,
    selectedKey,
    hasStayDates = false,
    hasVillage = false,
    isCatalogLoading = false,
    isCatalogError = false,
    isAvailableLoading = false,
    isAvailableError = false,
    onRetryCatalog,
    onRetryAvailable,
    onSelectNone,
    onSelectPromo,
  } = props;

  const { t } = useTranslation();
  const retryLabel = t("simulateur.family.retry");

  if (isCatalogLoading) {
    return <PromosStayPromosSkeleton rows={4} />;
  }

  if (isCatalogError) {
    return (
      <VtfErrorAlert
        title={tp("catalogLoadErrorTitle")}
        message={tp("catalogLoadError")}
        onRetry={onRetryCatalog}
        retryLabel={retryLabel}
      />
    );
  }

  const eligibilityKnown =
    hasStayDates && hasVillage && !isAvailableError && !isAvailableLoading;

  return (
    <>
      {hasStayDates && isAvailableError && (
        <Box sx={{ mb: 1.5 }}>
          <VtfErrorAlert
            title={tp("availableLoadErrorTitle")}
            message={tp("availableLoadError")}
            onRetry={onRetryAvailable}
            retryLabel={retryLabel}
          />
        </Box>
      )}

      <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
        <PromoCard
          icon="✨"
          label={tp("noneLabel")}
          description={tp("noneDesc")}
          tag="0%"
          selected={selectedKey === "none"}
          disabled={false}
          onClick={onSelectNone}
        />

        {hasStayDates && isAvailableLoading ? (
          <PromosStayPromosSkeleton rows={Math.max(catalog.length, 3)} />
        ) : (
          catalog.map((promo) => {
            const isAvailable =
              eligibilityKnown && available.some((a) => a.key === promo.key);
            const disabled = !eligibilityKnown || !isAvailable;
            const disabledNote = !hasStayDates
              ? tp("promoNeedsDates")
              : !hasVillage
                ? tp("promoNeedsVillage")
                : isAvailableError
                  ? tp("promoEligibilityUnknown")
                  : !isAvailable
                    ? tp("promoNotEligible")
                    : undefined;

            return (
              <PromoCard
                key={promo.key}
                icon={promo.icon}
                label={promo.label}
                description={promo.description}
                tag={promo.tag}
                selected={selectedKey === promo.key}
                auto={promo.kind === "auto"}
                disabled={disabled}
                disabledNote={disabledNote}
                onClick={() => {
                  if (!isAvailable) return;
                  if (selectedKey === promo.key) {
                    onSelectNone();
                  } else {
                    onSelectPromo(promo);
                  }
                }}
              />
            );
          })
        )}

        {!catalog.length && !isAvailableLoading && (
          <Box
            sx={{
              mt: 0.5,
              fontSize: 'var(--vtf-font-sm)',
              color: "text.secondary",
              background: "rgba(0, 68, 90, 0.06)",
              borderRadius: 2,
              padding: "10px 12px",
              border: "1px solid rgba(0, 68, 90, 0.10)",
              lineHeight: 1.45,
            }}
          >
            {tp("noAutoPromos")}
          </Box>
        )}
      </Box>
    </>
  );
}
