import type { SxProps, Theme } from '@mui/material/styles'

export type SelectableAccent = 'teal' | 'orange' | 'navy' | 'green'

function accentRgbVar(accent: SelectableAccent): string {
  if (accent === 'teal') return 'var(--vtf-teal-rgb)'
  if (accent === 'orange') return 'var(--vtf-orange-rgb)'
  if (accent === 'green') return '46, 125, 90'
  return 'var(--vtf-navy-rgb)'
}

function accentVar(accent: SelectableAccent): string {
  if (accent === 'teal') return 'var(--vtf-teal)'
  if (accent === 'orange') return 'var(--vtf-orange)'
  if (accent === 'green') return 'var(--vtf-green)'
  return 'var(--vtf-navy)'
}

export function selectableTileSx({
  selected,
  accent,
  minHeight = 126,
}: {
  selected: boolean
  accent: SelectableAccent
  minHeight?: number
}): SxProps<Theme> {
  const rgb = accentRgbVar(accent)
  const borderColor = selected ? accentVar(accent) : 'rgba(148, 163, 184, 0.35)'
  const bg = selected ? `rgba(${rgb}, 0.07)` : 'rgba(15, 23, 42, 0.025)'
  const shadow = selected
    ? accent === 'teal'
      ? '0 16px 34px rgba(0,168,181,0.16)'
      : accent === 'orange'
        ? '0 16px 40px rgba(242,166,128,0.18)'
        : accent === 'green'
          ? '0 16px 40px rgba(46, 125, 90, 0.18)'
        : '0 16px 40px rgba(0, 68, 90, 0.16)'
    : '0 12px 30px rgba(2,8,23,0.06)'
  const hoverShadow = selected
    ? accent === 'teal'
      ? '0 18px 40px rgba(0,168,181,0.22)'
      : accent === 'orange'
        ? '0 20px 46px rgba(242,166,128,0.24)'
        : accent === 'green'
          ? '0 20px 46px rgba(46, 125, 90, 0.24)'
        : '0 20px 46px rgba(0, 68, 90, 0.20)'
    : '0 16px 36px rgba(2,8,23,0.10)'

  return {
    position: 'relative',
    p: 2.25,
    minHeight,
    borderRadius: '22px',
    border: '2px solid',
    borderColor,
    bgcolor: bg,
    textTransform: 'none',
    boxShadow: shadow,
    transform: selected ? 'translateY(-1px)' : 'none',
    transition: 'transform 160ms ease, box-shadow 160ms ease, background 160ms ease, border-color 160ms ease',
    '&:hover': {
      boxShadow: hoverShadow,
      transform: 'translateY(-2px)',
      bgcolor: selected ? `rgba(${rgb}, 0.085)` : 'rgba(15, 23, 42, 0.03)',
    },
    '&:active': { transform: 'translateY(1px)' },
  }
}
