import * as React from "react";
/**
 * Carte Quotient Familial
 * Permet d'estimer le QF et d'appliquer les tarifs solidaires.
 */
import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  Link,
  Pill,
  VtfSelect,
  TextField,
  Typography,
} from "../../ui";
import AccountBalanceWalletRoundedIcon from "@mui/icons-material/AccountBalanceWalletRounded";
import InputAdornment from "@mui/material/InputAdornment";
import type {
  FamilyState,
  FamilyTabTranslations,
  QfBadgeKind,
} from "../../../types/familyTab";
import { CAF_ATTESTATION_URL } from "../../../utils/familyTab";
import {
  vtfTransparentCardContentSx,
  vtfTransparentCardSx,
} from "../../ui/vtfCardPresets";
import { VtfSectionHeading } from "../../shared/VtfSectionHeading";
import { VtfErrorAlert } from "../../shared/VtfErrorAlert";
import { fillQfTemplate } from "../../../utils/familyTab";
import {
  getEstimateErrorMessage,
  getQfBadge,
  inputBaseSx,
  parseLocaleNumber,
  pillBaseSx,
  S,
} from "./FamilyQuotientCard.ui";

export type FamilyQfEstimateProps = {
  suggestedParts: number;
  isPending: boolean;
  error: Error | null;
  onSubmit: (netMonthlyIncome: number, parts: number) => void;
  onClear?: () => void;
};

type Props = {
  value: FamilyState;
  tf: FamilyTabTranslations;
  badgeKind: QfBadgeKind;
  onToggleMaxiFamily: (checked: boolean) => void;
  qfEstimate: FamilyQfEstimateProps;
};

export function FamilyQuotientCard({
  value,
  tf,
  badgeKind,
  onToggleMaxiFamily,
  qfEstimate,
}: Props) {
  const [incomeStr, setIncomeStr] = React.useState("");
  const [partsStr, setPartsStr] = React.useState(() => {
    const p = Math.min(5, Math.max(1, qfEstimate.suggestedParts));
    return String(p);
  });

  const badge = getQfBadge(badgeKind, tf);

  const partsOptions = React.useMemo(() => {
    const opts: { value: string; label: string }[] = [];
    for (let p = 1; p <= 5.0001; p += 0.5) {
      const v = p % 1 === 0 ? String(p) : p.toFixed(1);
      opts.push({ value: v, label: v }); // garde le format avec point : 2.5
    }
    return opts;
  }, []);

  const handleApiEstimate = () => {
    const income = parseLocaleNumber(incomeStr);
    if (income == null || income < 0) return;
    qfEstimate.onSubmit(income, Number(partsStr));
  };

  const estimateErrMsg = qfEstimate.error
    ? getEstimateErrorMessage(qfEstimate.error, tf)
    : null;

  const canSubmit = (() => {
    const inc = parseLocaleNumber(incomeStr);
    const parts = Number(partsStr);
    return (
      !qfEstimate.isPending &&
      inc != null &&
      inc >= 0 &&
      Number.isFinite(parts) &&
      parts >= 1
    );
  })();

  return (
    <Card sx={vtfTransparentCardSx}>
      <CardContent sx={vtfTransparentCardContentSx}>
        <Box className="vtf-glass-strong rounded-3xl p-4">
          <VtfSectionHeading
            accent="teal"
            icon={<AccountBalanceWalletRoundedIcon />}
            title={tf("quotientTitle")}
            rightSlot={
              badge ? (
                <Pill
                  label={badge.label}
                  vtfTone={badge.tone}
                  sx={{
                    ...pillBaseSx,
                    fontSize: { xs: "var(--vtf-font-xs)", sm: "var(--vtf-font-sm)" },
                    height: { xs: "auto", sm: 24 },
                    maxWidth: "100%",
                    "& .MuiChip-label": {
                      whiteSpace: { xs: "normal", sm: "nowrap" },
                      lineHeight: 1.25,
                      py: { xs: 0.3, sm: 0 },
                    },
                  }}
                />
              ) : null
            }
          />

          <Box className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Box>
              <Typography sx={S.hint}>
                {tf("qfEstimateInlineHint")}{" "}
                <Link
                  href={CAF_ATTESTATION_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={S.link}
                >
                  {tf("cafLink")}
                </Link>
              </Typography>
              <Typography sx={S.hint2}>
                {tf("qfSuggestedParts").replace(
                  "{{parts}}",
                  String(qfEstimate.suggestedParts),
                )}
              </Typography>

              <Box sx={S.inputWrap}>
                <Box sx={S.incomeWrap}>
                  <Box component="label" htmlFor="qf-income" sx={S.fieldLabel}>
                    {fillQfTemplate(tf("qfNetIncomeLabel"))}
                  </Box>
                  <TextField
                    id="qf-income"
                    fullWidth
                    size="small"
                    type="text"
                    inputMode="decimal"
                    value={incomeStr}
                    onChange={(ev) => {
                      const val = ev.target.value;
                      setIncomeStr(val);
                      if (!val) {
                        qfEstimate.onClear?.();
                        const p = Math.min(
                          5,
                          Math.max(1, qfEstimate.suggestedParts),
                        );
                        setPartsStr(String(p));
                      }
                    }}
                    placeholder={tf("qfPlaceholder")}
                    disabled={qfEstimate.isPending}
                    slotProps={{
                      input: {
                        endAdornment: (
                          <InputAdornment position="end">
                            <Typography
                              sx={{
                                fontWeight: 900,
                                fontSize: "var(--vtf-font-sm)",
                                color: "rgba(0, 68, 90, 0.55)",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {fillQfTemplate(tf("qfUnit"))}
                            </Typography>
                          </InputAdornment>
                        ),
                      },
                    }}
                    sx={inputBaseSx}
                  />
                </Box>

                <Box sx={S.partsWrap}>
                  <Typography sx={S.fieldLabel}>
                    {tf("qfPartsLabel")}
                  </Typography>
                  <VtfSelect
                    className="vtf-select-age"
                    size="compact"
                    variant="light"
                    menuWidth={120}
                    options={partsOptions}
                    value={partsStr}
                    onChange={setPartsStr}
                    ariaLabel={tf("qfPartsLabel")}
                    width="100%"
                  />
                </Box>

                <Box sx={{ display: "grid", gap: 0.5 }}>
                  <Typography sx={{ ...S.fieldLabelGhost, display: { xs: "none", sm: "block" } }}>
                    .
                  </Typography>
                  <Button
                    type="button"
                    vtfVariant="orangeFillPill"
                    disabled={!canSubmit}
                    onClick={handleApiEstimate}
                    sx={S.btn}
                  >
                    {qfEstimate.isPending
                      ? tf("qfEstimateLoading")
                      : tf("qfEstimateButton")}
                  </Button>
                </Box>
              </Box>

              {estimateErrMsg && (
                <VtfErrorAlert
                  message={estimateErrMsg}
                  sx={{
                    mt: 1.5,
                    p: 1.5,
                    borderRadius: "16px",
                    "& .MuiSvgIcon-root": { fontSize: 20 },
                    "& .MuiBox-root": { width: 36, height: 36 },
                  }}
                />
              )}

              {value.qfVal != null ? (
                <Box
                  sx={S.pillBox(
                    "rgba(var(--vtf-teal-rgb), 0.08)",
                    "1px solid rgba(var(--vtf-teal-rgb), 0.16)",
                  )}
                >
                  <Typography sx={S.okText}>
                    {fillQfTemplate(tf("qfApiResult"), {
                      amount: value.qfVal,
                    })}
                  </Typography>
                </Box>
              ) : null}
            </Box>

            <Box
              className="p-4 rounded-[24px] text-white relative overflow-hidden"
              sx={S.solCard}
            >
              <Box aria-hidden sx={S.solGlow} />
              <Typography sx={S.solTitle}>{tf("solidaireTitle")}</Typography>
              <Typography sx={S.solBody}>
                {tf("solidaireBody")}{" "}
                <Box
                  component="span"
                  sx={{ fontWeight: 800, color: "var(--vtf-mint)" }}
                >
                  {tf("solidaireNote")}
                </Box>
              </Typography>
            </Box>
          </Box>

          {value.enfants.length >= 3 && (
            <Box
              className={`mt-6 p-4 rounded-2xl border-2 transition-all duration-500 ${
                value.maxiFamily
                  ? "border-vtf-orange"
                  : "bg-vtf-cream/30 border-transparent"
              }`}
              sx={{
                ...(value.maxiFamily
                  ? {
                      bgcolor: "rgba(var(--vtf-orange-rgb), 0.05)",
                      boxShadow: "0 8px 20px rgba(var(--vtf-orange-rgb), 0.08)",
                    }
                  : {}),
              }}
            >
              <FormControlLabel
                sx={{ m: 0, width: "100%" }}
                control={
                  <Checkbox
                    checked={value.maxiFamily}
                    onChange={(_, checked) => onToggleMaxiFamily(checked)}
                    size="small"
                    sx={{
                      color: "var(--vtf-orange)",
                      "&.Mui-checked": { color: "var(--vtf-orange)" },
                    }}
                  />
                }
                label={
                  <Box className="ml-1">
                    <Typography
                      sx={{
                        fontSize: "var(--vtf-font-md)",
                        fontWeight: 900,
                        color: "var(--vtf-navy)",
                      }}
                    >
                      {tf("maxiTitle")}
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: "var(--vtf-font-sm)",
                        fontWeight: 600,
                        color: "var(--vtf-navy)",
                        opacity: 0.6,
                      }}
                    >
                      {tf("maxiSubtitle")}
                    </Typography>
                  </Box>
                }
              />
            </Box>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}
