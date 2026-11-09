/* eslint-disable @typescript-eslint/no-explicit-any */
import * as React from "react";
import {
  Autocomplete,
  CircularProgress,
  IconButton,
  TextField,
} from "@mui/material";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import { useNavigate } from "react-router-dom";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useVillages } from "../../hooks/village.hooks";
import { useTranslation } from "../../contexts/LanguageContext";
import { Box, Typography } from "../ui";
import {
  headerSearchFieldSx,
  headerSearchIconBtnSx,
  VTF_HEADER,
} from "./headerVtfStyles";
import { VTF_FONT } from "../ui/vtfTypography";

type Props = {
  autoFocus?: boolean;
};

export default function HeaderVillageSearch({ autoFocus }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const inputRef = React.useRef<HTMLInputElement>(null);

  const [searchInput, setSearchInput] = React.useState("");

  React.useEffect(() => {
    if (!autoFocus) return;
    const id = window.requestAnimationFrame(() => {
      inputRef.current?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(id);
  }, [autoFocus]);
  const debouncedSearch = useDebouncedValue(searchInput, 400);

  const { data: searchVillages, isFetching: isSearching } = useVillages(
    { search: debouncedSearch.trim() || undefined, limit: 10 },
    { enabled: debouncedSearch.trim().length > 1 },
  );

  const placeholder = t("header.mainBar.searchDestination");
  const noOptionsText = t("header.mainBar.searchNoResults");
  const loadingText = t("header.mainBar.searchLoading");

  return (
    <Box sx={{ ...headerSearchFieldSx, display: { xs: "none", sm: "block" } }}>
      <Autocomplete
        openOnFocus
        value={null}
        inputValue={searchInput}
        options={
          debouncedSearch.trim().length > 1
            ? (searchVillages?.results ?? [])
            : []
        }
        forcePopupIcon={false}
        getOptionLabel={(option) =>
          typeof option === "string" ? option : option.nom
        }
        filterOptions={(x) => x}
        loading={isSearching}
        noOptionsText={
          <Box
            sx={{
              py: 1.5,
              textAlign: "center",
              color: "text.secondary",
              fontSize: VTF_FONT.sm,
              fontWeight: 600,
            }}
          >
            {noOptionsText}
          </Box>
        }
        loadingText={
          <Box
            sx={{
              py: 1.5,
              textAlign: "center",
              color: "text.secondary",
              fontSize: VTF_FONT.sm,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 1,
            }}
          >
            <CircularProgress size={14} color="inherit" />
            {loadingText}
          </Box>
        }
        slotProps={{
          clearIndicator: { sx: { display: "none" } },
          paper: {
            sx: {
              borderRadius: "16px",
              mt: 1,
              border: "1px solid rgba(0, 71, 81, 0.08)",
              boxShadow: "0 12px 32px rgba(0, 71, 81, 0.12)",
              "& .MuiAutocomplete-listbox": { p: 1 },
            },
          },
        }}
        onChange={(_, newValue) => {
          if (typeof newValue === "object" && newValue !== null) {
            setSearchInput("");
            navigate("/simulateur-vtf/sejour", {
              state: { autoSelectVillage: newValue },
            });
          }
        }}
        onInputChange={(_, newInputValue, reason) => {
          if (reason === "reset") return;
          setSearchInput(newInputValue);
        }}
        sx={{ width: "100%" }}
         renderInput={(params: any) => (
           <TextField
            {...params}
            inputRef={inputRef}
            placeholder={placeholder}
            variant="outlined"
            InputProps={{
              ...params.InputProps,
              endAdornment: params.InputProps?.endAdornment,
            }}
            sx={{
              width: "100%",
              m: 0,
              "& .MuiOutlinedInput-root": {
                height: VTF_HEADER.search.height,
                borderRadius: VTF_HEADER.search.borderRadius,
                border: VTF_HEADER.search.border,
                bgcolor: "#ffffff",
                pl: VTF_HEADER.search.pl,
                pr: VTF_HEADER.search.pr,
                py: 0,
                transition: "none",
                "& fieldset": { border: "none" },
                "&:hover fieldset": { border: "none" },
                "&.Mui-focused fieldset": { border: "none" },
              },
              "& .MuiOutlinedInput-input": {
                p: 0,
                height: "100%",
                fontFamily: "var(--sans)",
                fontSize: VTF_HEADER.search.fontSize,
                lineHeight: VTF_HEADER.search.lineHeight,
                fontWeight: 400,
                color: VTF_HEADER.search.color,
              },
              "& input::placeholder": {
                color: VTF_HEADER.search.placeholderColor,
                opacity: 1,
              },
            }}
          />
     )}
        renderOption={(props, option) => (
          <li
            {...props}
            key={option.id}
            style={{
              borderRadius: "10px",
              marginBottom: "2px",
              padding: "8px 12px",
              transition: "background 0.2s ease",
            }}
          >
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1.5,
                width: "100%",
              }}
            >
              <Box
                sx={{
                  width: 32,
                  height: 32,
                  borderRadius: "8px",
                  bgcolor: "rgba(0,168,181,0.08)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  border: "1px solid rgba(0,168,181,0.1)",
                }}
              >
                <span style={{ fontSize: VTF_FONT.sm }}>{option.env || "📍"}</span>
              </Box>
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  minWidth: 0,
                  flex: 1,
                }}
              >
                <Typography
                  noWrap
                  sx={{
                    fontWeight: 800,
                    fontSize: VTF_FONT.sm,
                    color: "var(--vtf-navy)",
                    lineHeight: 1.2,
                  }}
                >
                  {option.nom}
                </Typography>
                {option.region ? (
                  <Typography
                    noWrap
                    sx={{
                      fontSize: VTF_FONT.sm,
                      color: "text.secondary",
                      fontWeight: 600,
                      mt: 0.25,
                    }}
                  >
                    {option.region}
                  </Typography>
                ) : null}
              </Box>
            </Box>
          </li>
        )}
      />
      <IconButton
        size="small"
        tabIndex={-1}
        aria-label={placeholder}
        sx={headerSearchIconBtnSx}
        onClick={() => inputRef.current?.focus()}
      >
        {isSearching ? (
          <CircularProgress size={16} sx={{ color: "#000" }} />
        ) : (
          <SearchRoundedIcon sx={{ fontSize: VTF_HEADER.search.iconFontSize }} />
        )}
      </IconButton>
    </Box>
  );
}
