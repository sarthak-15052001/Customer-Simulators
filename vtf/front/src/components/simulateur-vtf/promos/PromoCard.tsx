import type { ReactNode } from 'react'
import { Box, Button, Pill, Typography } from '../../ui'

export type PromoCardProps = {
  icon: ReactNode | string
  label: string
  description: string
  tag: string
  selected: boolean
  auto?: boolean
  disabled?: boolean
  disabledNote?: string
  onClick: () => void
}

export function PromoCard({ icon, label, description, tag, selected, auto, disabled, disabledNote, onClick }: PromoCardProps) {
  return (
    <Button
      onClick={onClick}
      disabled={disabled}
      sx={{
        width: '100%',
        textAlign: 'left',
        p: 0,
        borderRadius: 3,
        textTransform: 'none',
        justifyContent: 'flex-start',
        bgcolor: selected ? (auto ? 'rgba(16, 185, 129, 0.10)' : 'rgba(var(--vtf-orange-rgb), 0.10)') : 'rgba(255,255,255,0.55)',
        border: selected
          ? auto
            ? '1px solid rgba(16, 185, 129, 0.28)'
            : '1px solid rgba(var(--vtf-orange-rgb), 0.26)'
          : '1px solid rgba(15, 23, 42, 0.10)',
        boxShadow: selected ? '0 16px 30px rgba(2, 8, 23, 0.06)' : 'none',
        '&:hover': {
          bgcolor: selected ? undefined : 'rgba(255,255,255,0.72)',
          borderColor: selected ? undefined : 'rgba(var(--vtf-orange-rgb), 0.28)',
        },
        '&.Mui-disabled': {
          opacity: 0.5,
          cursor: 'not-allowed',
        },
      }}
    >
      <Box sx={{ display: 'flex', gap: 1.5, p: 1.75, width: '100%', alignItems: 'flex-start' }}>
        <Box sx={{ fontSize: 20, lineHeight: 1, mt: 0.15 }}>{icon}</Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 1 }}>
            <Typography sx={{ fontSize: 'var(--vtf-font-sm)', fontWeight: 950, color: 'var(--vtf-navy)' }}>{label}</Typography>
            <Pill
              size="small"
              label={tag}
              vtfTone={auto ? 'softGreen' : 'softOrange'}
              sx={{
                fontSize: 'var(--vtf-font-sm)',
                fontWeight: 950,
                height: 'auto',
                py: 0.2,
                whiteSpace: 'nowrap',
                bgcolor: auto ? 'rgba(16, 185, 129, 0.16)' : 'rgba(var(--vtf-orange-rgb), 0.14)',
                color: auto ? 'rgba(4, 120, 87, 0.95)' : 'rgba(185, 28, 28, 0.9)',
                border: auto ? '1px solid rgba(16, 185, 129, 0.28)' : '1px solid rgba(var(--vtf-orange-rgb), 0.22)',
              }}
            />
          </Box>
          <Typography sx={{ fontSize: 'var(--vtf-font-sm)', color: 'text.secondary', mt: 0.5, lineHeight: 1.4 }}>{description}</Typography>
          {disabled && disabledNote && (
            <Typography sx={{ fontSize: 'var(--vtf-font-sm)', color: 'text.disabled', mt: 0.25, fontStyle: 'italic' }}>
              {disabledNote}
            </Typography>
          )}
        </Box>
        <Box
          sx={{
            width: 20,
            height: 20,
            borderRadius: 2,
            border: selected
              ? auto
                ? '2px solid rgba(16, 185, 129, 0.8)'
                : '2px solid rgba(var(--vtf-orange-rgb), 0.9)'
              : '2px solid rgba(15,23,42,0.18)',
            bgcolor: selected ? (auto ? 'rgba(16, 185, 129, 0.85)' : 'rgba(var(--vtf-orange-rgb), 0.9)') : 'transparent',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 'var(--vtf-font-sm)',
            fontWeight: 900,
            flex: '0 0 auto',
            mt: 0.15,
          }}
        >
          {selected ? '✓' : ''}
        </Box>
      </Box>
    </Button>
  )
}

