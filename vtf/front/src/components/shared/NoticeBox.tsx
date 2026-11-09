import * as React from 'react'
import type { BoxProps } from '@mui/material/Box'

import { mergeSx } from '../ui/_mergeSx'
import { Box } from '../ui/Box'

export type NoticeTone = 'navy' | 'orange' | 'teal' | 'green'

type Props = Omit<BoxProps, 'color'> & {
  tone?: NoticeTone
  dense?: boolean
}

const toneTokens: Record<NoticeTone, { fg: string; bg: string; border: string; radius: number | string; fontWeight?: number }> = {
  navy: {
    fg: 'text.secondary',
    bg: 'rgba(0, 68, 90, 0.06)',
    border: '1px solid rgba(0, 68, 90, 0.10)',
    radius: 2,
  },
  orange: {
    fg: 'text.secondary',
    bg: 'rgba(var(--vtf-orange-rgb), 0.10)',
    border: '1px solid rgba(var(--vtf-orange-rgb), 0.18)',
    radius: 2,
  },
  teal: {
    fg: 'var(--vtf-teal)',
    bg: 'rgba(var(--vtf-teal-rgb), 0.08)',
    border: '1px solid rgba(var(--vtf-teal-rgb), 0.14)',
    radius: 2,
  },
  green: {
    fg: 'rgba(4, 120, 87, 0.95)',
    bg: 'rgba(16, 185, 129, 0.12)',
    border: '1px solid rgba(16, 185, 129, 0.22)',
    radius: '16px',
    fontWeight: 850,
  },
}

export const NoticeBox = React.forwardRef<HTMLElement, Props>(function NoticeBox(
  { tone = 'navy', dense = false, sx, ...rest },
  ref,
) {
  const t = toneTokens[tone]
  const baseSx: BoxProps['sx'] = {
    mt: 2,
    fontSize: 'var(--vtf-font-sm)',
    color: t.fg,
    background: t.bg,
    borderRadius: t.radius,
    padding: dense ? '10px 12px' : '12px 14px',
    border: t.border,
    lineHeight: dense ? 1.35 : 1.45,
    ...(t.fontWeight != null ? { fontWeight: t.fontWeight } : undefined),
  }

  return <Box ref={ref} {...rest} sx={mergeSx(baseSx, sx)} />
})

