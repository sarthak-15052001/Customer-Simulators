import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import InputAdornment from "@mui/material/InputAdornment";

import { TextField } from "../ui/TextField";
import type { TextFieldProps } from "../ui/TextField";
import { mergeSx } from "../ui/_mergeSx";

export type VtfSearchFieldProps = {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  "aria-label"?: string;
  name?: string;
  disabled?: boolean;
  fullWidth?: boolean;
  size?: "small" | "medium";
  className?: string;
  sx?: TextFieldProps["sx"];
};

const searchFieldSx: TextFieldProps["sx"] = {
  "& .MuiOutlinedInput-root": {
    borderRadius: "14px",
    bgcolor: "var(--vtf-white)",
    fontFamily: "var(--sans)",
    fontWeight: 600,
    fontSize: "var(--vtf-font-sm)",
    color: "var(--vtf-navy)",
    minHeight: 36,
    boxShadow: "none",
    border: "1px solid #dadfe6",
    transition: "border-color 0.2s ease",
    "& fieldset": { border: "none" },
    "&:hover": {
      borderColor: "#c8ddd0",
    },
    "&.Mui-focused": {
      borderColor: "#a6e1e5",
      boxShadow: "none",
    },
  },
  "& .MuiOutlinedInput-notchedOutline": { border: "none" },
  "& .MuiOutlinedInput-input": {
    py: 0.75,
    "&::placeholder": {
      color: "#94a3b8",
      opacity: 1,
    },
  },
};

/**
 * Reusable search input — border/radius aligned with `vtf-select-age` compact selects.
 */
export function VtfSearchField({
  value,
  onChange,
  placeholder,
  "aria-label": ariaLabel,
  name = "search",
  disabled,
  fullWidth = true,
  size = "small",
  className = "vtf-search-field",
  sx,
}: VtfSearchFieldProps) {
  return (
    <TextField
      className={className}
      name={name}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      aria-label={ariaLabel ?? placeholder}
      disabled={disabled}
      fullWidth={fullWidth}
      size={size}
      variant="outlined"
      slotProps={{
        input: {
          startAdornment: (
            <InputAdornment position="start">
              <SearchRoundedIcon
                sx={{
                  fontSize: 20,
                  color: "#94a3b8",
                }}
              />
            </InputAdornment>
          ),
        },
      }}
      sx={mergeSx(searchFieldSx, sx)}
    />
  );
}
