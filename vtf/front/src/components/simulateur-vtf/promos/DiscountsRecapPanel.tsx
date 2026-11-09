import { Box, Typography } from "../../ui";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import type { PromosDiscountSummaryState } from "./promosDiscountState";

export type AppliedLine = { icon: string; label: string; note?: string };

function recapEmptyMessage(
  tp: (k: string) => string,
  state: PromosDiscountSummaryState,
): string {
  if (state === "incomplete") return tp("recapIncomplete");
  if (state === "pending") return tp("recapPending");
  return tp("recapNoDiscounts");
}

export function DiscountsRecapPanel(props: {
  tp: (k: string) => string;
  lines: AppliedLine[];
  discountSummaryState: PromosDiscountSummaryState;
}) {
  const { tp, lines, discountSummaryState } = props;

  return (
    <Box
      className="vtf-glass-strong"
      sx={{
        borderRadius: '24px',
        border: '1px solid rgba(255, 255, 255, 0.6)',
        boxShadow: '0 8px 32px rgba(0, 68, 90, 0.08)',
        p: 2.5,
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        background: 'linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0.5) 100%)',
        backdropFilter: 'blur(20px)',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
        <Box 
         sx={{ 
            width: 30, 
            height: 30, 
            borderRadius: '14px', 
            bgcolor: 'var(--vtf-teal)', 
            color: 'white',
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(0, 125, 140, 0.3)'
          }}
        >
          <CheckCircleRoundedIcon sx={{ fontSize: 'var(--vtf-font-lg)' }} />
        </Box>
        <Typography sx={{ fontSize: 'var(--vtf-font-lg)', fontWeight: 900, color: 'var(--vtf-navy)', letterSpacing: '-0.01em' }}>
          {tp('recapTitle')}
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {lines.length ? (
          lines.map((l, idx) => (
            <Box 
              key={idx} 
              sx={{ 
                display: 'flex', 
                gap: 2, 
                alignItems: 'center',
                p: 1.5,
                borderRadius: '16px',
                bgcolor: 'white',
                border: '1px solid rgba(0, 68, 90, 0.08)',
                boxShadow: '0 2px 8px rgba(0,0,0,0.03)'
              }}
            >
              <Box sx={{ fontSize: 24, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {l.icon}
              </Box>
              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Typography sx={{ fontSize: 'var(--vtf-font-md)', fontWeight: 900, color: 'var(--vtf-teal)', lineHeight: 1.3 }}>
                  {l.label}
                </Typography>
                {l.note ? (
                  <Typography sx={{ fontSize: 'var(--vtf-font-sm)', fontWeight: 600, color: 'rgba(0, 68, 90, 0.65)', mt: 0.25 }}>
                    {l.note}
                  </Typography>
                ) : null}
              </Box>
            </Box>
          ))
        ) : (
          <Box sx={{ p: 2, bgcolor: 'rgba(255,255,255,0.5)', borderRadius: '12px', border: '1px dashed rgba(0, 68, 90, 0.2)' }}>
            <Typography sx={{ fontSize: 'var(--vtf-font-sm)', fontWeight: 700, color: 'text.secondary', textAlign: 'center' }}>
              {recapEmptyMessage(tp, discountSummaryState)}
            </Typography>
          </Box>
        )}
      </Box>

      {lines.length > 0 && (
        <Box sx={{ mt: 2.5, pt: 1.5, borderTop: '1px dashed rgba(0, 68, 90, 0.15)' }}>
          <Typography sx={{ fontSize: 'var(--vtf-font-sm)', fontWeight: 600, color: 'rgba(0, 68, 90, 0.5)', textAlign: 'center' }}>
            {tp('recapRules')}
          </Typography>
        </Box>
      )}
    </Box>
  )
}
