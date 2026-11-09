import { styled } from "@mui/material/styles";
import MuiTooltip, {
  tooltipClasses,
  type TooltipProps,
} from "@mui/material/Tooltip";

const StyledTooltip = styled(({ className, ...props }: TooltipProps) => (
  <MuiTooltip {...props} classes={{ popper: className }} />
))(() => ({
  [`& .${tooltipClasses.tooltip}`]: {
    backgroundColor: "var(--vtf-navy)",
    color: "#fff",
    boxShadow: "0 8px 24px rgba(0, 68, 90, 0.25)",
    fontSize: 'var(--vtf-font-sm)',
    fontWeight: 900,
    borderRadius: 8,
    padding: "6px 12px",
    letterSpacing: "0.02em",
    border: "1px solid rgba(255, 255, 255, 0.1)",
  },
  [`& .${tooltipClasses.arrow}`]: {
    color: "var(--vtf-navy)",
  },
}));

export const Tooltip = (props: TooltipProps) => {
  return (
    <StyledTooltip
      arrow
      enterDelay={400}
      leaveDelay={0}
      placement="top"
      {...props}
    />
  );
};
