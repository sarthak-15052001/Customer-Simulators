import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import { Box, Typography } from "../ui";
import {
  headerSearchFieldSx,
  headerSearchIconBtnSx,
  headerSearchInputSx,
  VTF_HEADER,
} from "./headerVtfStyles";

type Props = {
  placeholder: string;
  onActivate: () => void;
  onPrefetch?: () => void;
};

export function HeaderVillageSearchTrigger({
  placeholder,
  onActivate,
  onPrefetch,
}: Props) {
  return (
    <Box
      component="button"
      type="button"
      onMouseEnter={onPrefetch}
      onMouseDown={(e) => {
        e.preventDefault();
        onActivate();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onActivate();
        }
      }}
      sx={{
        ...headerSearchFieldSx,
        display: { xs: "none", sm: "block" },
        p: 0,
        border: "none",
        bgcolor: "transparent",
        cursor: "text",
        textAlign: "left",
      }}
      aria-label={placeholder}
    >
      <Box
        component="span"
        sx={{
          ...headerSearchInputSx,
          display: "flex",
          alignItems: "center",
        }}
      >
        <Typography
          component="span"
          sx={{
            fontFamily: "var(--sans)",
            fontSize: VTF_HEADER.search.fontSize,
            lineHeight: VTF_HEADER.search.lineHeight,
            fontWeight: 400,
            color: VTF_HEADER.search.placeholderColor,
            flex: 1,
            textAlign: "left",
          }}
        >
          {placeholder}
        </Typography>
      </Box>
      <Box
        component="span"
        sx={{
          ...headerSearchIconBtnSx,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          pointerEvents: "none",
        }}
      >
        <SearchRoundedIcon sx={{ fontSize: VTF_HEADER.search.iconFontSize }} />
      </Box>
    </Box>
  );
}
