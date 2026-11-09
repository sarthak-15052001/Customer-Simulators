import * as React from "react";
import HomeRoundedIcon from "@mui/icons-material/HomeRounded";
import FactCheckRoundedIcon from "@mui/icons-material/FactCheckRounded";
import EditRoundedIcon from "@mui/icons-material/EditRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import CheckRoundedIcon from "@mui/icons-material/CheckRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import { Box, Button, TextField, Typography } from "../../ui";
import { fillQfTemplate } from "../../../utils/familyTab";

export function FamilyQuotientSection(props: {
  tp: (k: string) => string;
  qfSelection: "r1" | "r2" | "plein" | "empty";
  currentValueLabel: string;
  isPeriodValid?: boolean;
  qfVal?: number | null;
  onUpdateQf?: (val: number | null) => void;
}) {
  const {
    tp,
    qfSelection,
    currentValueLabel,
    isPeriodValid = true,
    qfVal,
    onUpdateQf,
  } = props;

  const [isEditing, setIsEditing] = React.useState(false);
  const [prevQfVal, setPrevQfVal] = React.useState(qfVal);
  const [inputVal, setInputVal] = React.useState(
    qfVal != null ? String(qfVal) : "",
  );

  if (qfVal !== prevQfVal) {
    setPrevQfVal(qfVal);
    setInputVal(qfVal != null ? String(qfVal) : "");
  }

  let qfLabel = fillQfTemplate(tp("qfFullLabel"));
  let qfDesc = tp("qfFullDesc");
  let qfTag = tp("qfFullTag");

  if (qfSelection === "r1") {
    qfLabel = fillQfTemplate(tp("qfR1Label"));
    qfDesc = tp("qfR1Desc");
    qfTag = tp("qfR1Tag");
  } else if (qfSelection === "r2") {
    qfLabel = fillQfTemplate(tp("qfR2Label"));
    qfDesc = tp("qfR2Desc");
    qfTag = tp("qfR2Tag");
  } else if (qfSelection === "empty") {
    qfLabel = tp("qfTitle");
    qfDesc = tp("qfCurrentEmpty");
    qfTag = "-";
  }

  if (!isPeriodValid && qfSelection !== "empty") {
    qfDesc = tp("qfNotApplicableDesc");
    qfTag = tp("qfNotApplicableTag");
  }

  const handleSaveEdit = () => {
    if (!inputVal.trim()) {
      onUpdateQf?.(null);
    } else {
      const parsed = parseFloat(inputVal.replace(",", "."));
      if (!isNaN(parsed) && parsed >= 0) {
        onUpdateQf?.(Math.round(parsed));
      }
    }
    setIsEditing(false);
  };

  const handleDelete = () => {
    onUpdateQf?.(null);
    setIsEditing(false);
  };

  return (
    <Box
      className="vtf-glass-strong"
      sx={{
        borderRadius: "24px",
        border: "1px solid rgba(255, 255, 255, 0.7)",
        background:
          "linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.6) 100%)",
        boxShadow: "0 8px 32px rgba(0, 125, 140, 0.08)",
        p: 3,
        display: "flex",
        flexDirection: "column",
        gap: 2,
      }}
    >
      <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start" }}>
        <Box
          sx={{
            width: 30,
            height: 30,
            borderRadius: "14px",
            bgcolor: "var(--vtf-teal)",
            color: "white",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 4px 12px rgba(0, 125, 140, 0.3)",
          }}
        >
          <HomeRoundedIcon sx={{ fontSize: "var(--vtf-font-lg)" }} />
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box
            sx={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: 1,
            }}
          >
            <Typography
              sx={{
                fontSize: "var(--vtf-font-md)",
                fontWeight: 950,
                color: "var(--vtf-navy)",
              }}
            >
              {qfLabel}
            </Typography>
            <Box
              sx={{
                px: 1.5,
                py: 0.5,
                borderRadius: "8px",
                bgcolor: isPeriodValid
                  ? "rgba(var(--vtf-mint-rgb), 0.2)"
                  : "rgba(148, 163, 184, 0.15)",
                color: isPeriodValid ? "var(--vtf-teal)" : "text.secondary",
                fontSize: "var(--vtf-font-sm)",
                fontWeight: 900,
                border: isPeriodValid
                  ? "1px solid rgba(0, 125, 140, 0.15)"
                  : "1px solid rgba(148, 163, 184, 0.35)",
              }}
            >
              {qfTag}
            </Box>
          </Box>
          <Typography
            sx={{
              fontSize: "var(--vtf-font-sm)",
              color: "text.secondary",
              mt: 0.5,
              lineHeight: 1.4,
              fontWeight: 600,
            }}
          >
            {qfDesc}
          </Typography>
        </Box>
      </Box>

      {isEditing ? (
        <Box
          sx={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 1,
            pt: 2,
            borderTop: "1px dashed rgba(0, 68, 90, 0.15)",
          }}
        >
          <TextField
            size="small"
            type="number"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder={tp("qfPlaceholder")}
            sx={{
              width: { xs: "100%", sm: 180 },
              "& .MuiOutlinedInput-root": {
                borderRadius: "12px",
                bgcolor: "#FFFFFF",
              },
            }}
          />
          <Button
            size="small"
            vtfVariant="orangeFillPill"
            startIcon={<CheckRoundedIcon />}
            onClick={handleSaveEdit}
            sx={{ fontWeight: 900 }}
          >
            {tp("qfApply")}
          </Button>
          <Button
            size="small"
            vtfVariant="stepPrevious"
            startIcon={<CloseRoundedIcon />}
            onClick={() => {
              setIsEditing(false);
              setInputVal(qfVal != null ? String(qfVal) : "");
            }}
            sx={{ fontWeight: 800 }}
          >
            {tp("qfCancel")}
          </Button>
        </Box>
      ) : (
        <Box
          sx={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 1,
            pt: 2,
            borderTop: "1px dashed rgba(0, 68, 90, 0.15)",
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <FactCheckRoundedIcon
              sx={{ color: "var(--vtf-orange)", fontSize: "var(--vtf-font-lg)" }}
            />
            <Typography
              sx={{
                fontSize: "var(--vtf-font-sm)",
                fontWeight: 800,
                color: "var(--vtf-navy)",
              }}
            >
              {tp("qfCurrentPrefix")} {currentValueLabel}
            </Typography>
          </Box>

          {onUpdateQf && (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Button
                size="small"
                vtfVariant="stepPrevious"
                startIcon={<EditRoundedIcon sx={{ fontSize: 16 }} />}
                onClick={() => setIsEditing(true)}
                sx={{
                  height: 32,
                  px: 1.25,
                  fontSize: "var(--vtf-font-xs)",
                  fontWeight: 900,
                  borderRadius: "10px",
                }}
              >
                {tp("qfEdit")}
              </Button>
              {qfVal != null && (
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<DeleteOutlineRoundedIcon sx={{ fontSize: 16 }} />}
                  onClick={handleDelete}
                  sx={{
                    height: 32,
                    px: 1.25,
                    fontSize: "var(--vtf-font-xs)",
                    fontWeight: 900,
                    borderRadius: "10px",
                    color: "rgba(185, 28, 28, 0.85)",
                    borderColor: "rgba(185, 28, 28, 0.3)",
                    "&:hover": {
                      borderColor: "rgba(185, 28, 28, 0.8)",
                      bgcolor: "rgba(185, 28, 28, 0.05)",
                    },
                  }}
                >
                  {tp("qfDelete")}
                </Button>
              )}
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}
