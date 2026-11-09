import type { SxProps, Theme } from '@mui/material/styles'

export function mergeSx(
  baseSx: SxProps<Theme> | undefined,
  sx: SxProps<Theme> | undefined,
): SxProps<Theme> | undefined {
  if (baseSx == null) return sx
  if (sx == null) return baseSx

  // Ensure we always return a valid SxProps array when combining
  const combined = Array.isArray(sx) ? [baseSx, ...sx] : [baseSx, sx]
  return combined as SxProps<Theme>
}

