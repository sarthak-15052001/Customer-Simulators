/**
 * VTF UI type scale — change CSS vars in index.css to update app-wide.
 * xs: 11px (was 9) · sm: 14px (was 11) · md: 16px (was 14) · lg: 18px
 */
export const VTF_FONT = {
  xs: 'var(--vtf-font-xs)',
  sm: 'var(--vtf-font-sm)',
  md: 'var(--vtf-font-md)',
  lg: 'var(--vtf-font-lg)',
  display: 'var(--vtf-font-display)',
} as const

export const VTF_FONT_PX = {
  xs: 11,
  sm: 14,
  md: 16,
  lg: 18,
  display: 55,
} as const
