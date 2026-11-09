import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import type { SxProps, Theme } from "@mui/material/styles";

import { useTranslation } from "../../contexts/LanguageContext";
import { fillPaginationTemplate } from "../../utils/paginationTemplate";
import { Box } from "./Box";
import { Button } from "./Button";
import { IconButton } from "./IconButton";
import { Typography } from "./Typography";

export type PaginationProps = {
  totalCount: number;
  pageSize: number;
  offset: number;
  onOffsetChange: (nextOffset: number) => void;
  /** Optional layout overrides */
  sx?: SxProps<Theme>;
};

/** Page indices (1-based) with ellipsis gaps for large totals. */
function getVisiblePageItems(
  currentPage: number,
  totalPages: number,
): Array<number | "ellipsis"> {
  if (totalPages <= 1) return [1];
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }
  const set = new Set<number>();
  set.add(1);
  set.add(totalPages);
  for (let d = -2; d <= 2; d++) {
    const p = currentPage + d;
    if (p >= 1 && p <= totalPages) set.add(p);
  }
  const sorted = [...set].sort((a, b) => a - b);
  const out: Array<number | "ellipsis"> = [];
  for (let i = 0; i < sorted.length; i++) {
    const p = sorted[i]!;
    if (i > 0) {
      const prev = sorted[i - 1]!;
      if (p - prev > 1) out.push("ellipsis");
    }
    out.push(p);
  }
  return out;
}

const roundNavBtnSx = {
  width: 40,
  height: 40,
  padding: 0,
  borderRadius: "50%",
  border: "1.5px solid rgba(var(--vtf-orange-rgb), 0.42)",
  bgcolor: "rgba(255, 255, 255, 0.92)",
  color: "var(--vtf-orange)",
  boxShadow: "0 6px 16px rgba(242, 166, 128, 0.18)",
  transition:
    "background-color 0.18s ease, box-shadow 0.18s ease, transform 0.15s ease",
  "&:hover": {
    bgcolor: "rgba(var(--vtf-orange-rgb), 0.14)",
    boxShadow: "0 8px 20px rgba(242, 166, 128, 0.26)",
    transform: "translateY(-1px)",
  },
  "&:active": { transform: "translateY(0)" },
  "&.Mui-disabled": {
    borderColor: "rgba(148, 163, 184, 0.35)",
    color: "rgba(15, 23, 42, 0.28)",
    bgcolor: "rgba(248, 250, 252, 0.9)",
    boxShadow: "none",
  },
} as const;

/**
 * Offset-based pagination (`limit` / `offset` / `count`).
 * Labels use `common.pagination.*` in locale files.
 */
export function Pagination({
  totalCount,
  pageSize,
  offset,
  onOffsetChange,
  sx,
}: PaginationProps) {
  const { t, language } = useTranslation();

  if (totalCount <= 0) return null;

  const from = Math.min(totalCount, offset + 1);
  const to = Math.min(totalCount, offset + pageSize);
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const currentPage = Math.floor(offset / pageSize) + 1;
  const canPrev = offset > 0;
  const canNext = offset + pageSize < totalCount;

  const goPrev = () => {
    if (!canPrev) return;
    onOffsetChange(Math.max(0, offset - pageSize));
  };
  const goNext = () => {
    if (!canNext) return;
    onOffsetChange(offset + pageSize);
  };

  const goToPage = (page: number) => {
    const next = (page - 1) * pageSize;
    if (next === offset) return;
    if (next < 0 || next >= totalCount) return;
    onOffsetChange(next);
  };

  const pageItems = getVisiblePageItems(currentPage, totalPages);
  const navAria = fillPaginationTemplate(t("common.pagination.page"), {
    current: currentPage,
    pages: totalPages,
  });

  const singularPrefixByLang: Record<string, string> = {
    fr: "Résultat",
    en: "Result",
    es: "Resultado",
    nl: "Resultaat",
  };

  const rangeTemplate =
    totalCount === 1
      ? // replace first token (the plural noun) by a singular one for clarity
        t("common.pagination.range").replace(
          /^[^\s]+/,
          singularPrefixByLang[language] ?? "Résultat",
        )
      : t("common.pagination.range");

  return (
    <Box
      component="nav"
      aria-label={navAria}
      sx={{
        mt: 2.5,
        pt: 2.25,
        borderTop: "1px solid rgba(var(--vtf-orange-rgb), 0.14)",
        display: "flex",
        flexDirection: { xs: "column", md: "row" },
        alignItems: "center",
        justifyContent: "space-between",
        gap: 2,
        ...sx,
      }}
    >
      <Box sx={{ minWidth: 0, textAlign: { xs: "center", md: "left" } }}>
        <Typography
          sx={{
            fontSize: "var(--vtf-font-sm)",
            fontWeight: 850,
            color: "var(--vtf-navy)",
            letterSpacing: "0.02em",
          }}
        >
          {fillPaginationTemplate(rangeTemplate, {
            from,
            to,
            total: totalCount,
          })}
        </Typography>
      </Box>

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: { xs: 0.5, sm: 0.75 },
          flexWrap: "wrap",
          flexShrink: 0,
          px: { xs: 0.5, sm: 1 },
          py: 0.75,
          borderRadius: 999,
          bgcolor: "rgba(var(--vtf-orange-rgb), 0.07)",
          border: "1px solid rgba(var(--vtf-orange-rgb), 0.16)",
          boxShadow: "0 8px 22px rgba(15, 23, 42, 0.06)",
        }}
      >
        <IconButton
          type="button"
          onClick={goPrev}
          disabled={!canPrev}
          aria-label={t("common.pagination.prevAria")}
          size="small"
          sx={roundNavBtnSx}
        >
          <ChevronLeftRoundedIcon sx={{ fontSize: 24 }} />
        </IconButton>

        {pageItems.map((item, idx) =>
          item === "ellipsis" ? (
            <Typography
              key={`ellipsis-${idx}`}
              component="span"
              sx={{
                px: 0.35,
                fontSize: "var(--vtf-font-md)",
                fontWeight: 800,
                color: "var(--vtf-navy)",
                opacity: 0.45,
                userSelect: "none",
              }}
            >
              …
            </Typography>
          ) : item === currentPage ? (
            <Box
              key={`page-${item}`}
              component="span"
              aria-current="page"
              sx={{
                minWidth: 36,
                width: 36,
                height: 36,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: "50%",
                bgcolor: "var(--vtf-orange)",
                color: "#fff",
                fontFamily: "var(--sans)",
                fontSize: "var(--vtf-font-sm)",
                fontWeight: 850,
                lineHeight: 1,
                boxShadow: "0 6px 16px rgba(242, 166, 128, 0.45)",
              }}
            >
              {item}
            </Box>
          ) : (
            <Button
              key={`page-${item}`}
              type="button"
              variant="text"
              onClick={() => goToPage(item)}
              aria-label={fillPaginationTemplate(
                t("common.pagination.pageNumberAria"),
                {
                  page: item,
                  pages: totalPages,
                },
              )}
              disableRipple
              sx={{
                minWidth: 36,
                width: 36,
                maxWidth: 36,
                height: 36,
                minHeight: 36,
                p: 0,
                borderRadius: "50%",
                border: "1px solid rgba(15, 23, 42, 0.1)",
                bgcolor: "rgba(255, 255, 255, 0.88)",
                color: "var(--vtf-navy)",
                fontFamily: "var(--sans)",
                fontSize: "var(--vtf-font-sm)",
                fontWeight: 850,
                lineHeight: 1,
                textTransform: "none",
                boxShadow: "0 2px 8px rgba(15, 23, 42, 0.04)",
                transition:
                  "background-color 0.16s ease, color 0.16s ease, box-shadow 0.16s ease, transform 0.14s ease",
                "&:hover": {
                  bgcolor: "rgba(var(--vtf-orange-rgb), 0.12)",
                  color: "var(--vtf-orange)",
                  borderColor: "rgba(var(--vtf-orange-rgb), 0.35)",
                  transform: "translateY(-1px)",
                },
              }}
            >
              {item}
            </Button>
          ),
        )}

        <IconButton
          type="button"
          onClick={goNext}
          disabled={!canNext}
          aria-label={t("common.pagination.nextAria")}
          size="small"
          sx={roundNavBtnSx}
        >
          <ChevronRightRoundedIcon sx={{ fontSize: 24 }} />
        </IconButton>
      </Box>
    </Box>
  );
}
