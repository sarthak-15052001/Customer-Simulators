import * as React from 'react'
import type { SxProps, Theme } from '@mui/material/styles'
import { Box, Card, CardContent, Typography } from '../ui'
import { vtfTransparentCardContentSx, vtfTransparentCardSx } from '../ui/vtfCardPresets'
import { mergeSx } from '../ui/_mergeSx'
import { VtfSectionHeading, VTF_SECTION_HEADING_MB, type VtfHeadingAccent } from './VtfSectionHeading'

export type VtfGlassCardProps = {
  title?: React.ReactNode
  subtitle?: React.ReactNode
  headingIcon?: React.ReactElement<{ sx?: object }>
  headingAccent?: VtfHeadingAccent
  rightSlot?: React.ReactNode
  children: React.ReactNode
  glassClassName?: string
  glassSx?: SxProps<Theme>
  cardSx?: SxProps<Theme>
  contentSx?: SxProps<Theme>
}

export function VtfGlassCard({
  title,
  subtitle,
  headingIcon,
  headingAccent = 'orange',
  rightSlot,
  children,
  glassClassName = 'vtf-glass-strong rounded-2xl p-4',
  glassSx,
  cardSx,
  contentSx,
}: VtfGlassCardProps) {
  const hasHeader = title != null || subtitle != null || rightSlot != null || headingIcon != null

  return (
    <Card sx={mergeSx(vtfTransparentCardSx, cardSx)}>
      <CardContent sx={mergeSx(vtfTransparentCardContentSx, contentSx)}>
        <Box className={glassClassName} sx={glassSx}>
          {hasHeader && headingIcon != null && title != null ? (
            <VtfSectionHeading
              icon={headingIcon}
              title={title}
              subtitle={subtitle}
              accent={headingAccent}
              rightSlot={rightSlot}
            />
          ) : hasHeader ? (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: 2,
                mb: VTF_SECTION_HEADING_MB,
                pb: 1.5,
                borderBottom: '1px solid rgba(0, 68, 90, 0.10)',
              }}
            >
              <Box sx={{ minWidth: 0 }}>
                {title != null && (
                  <Typography sx={{ fontWeight: 950, color: 'var(--vtf-navy)', fontSize: 'var(--vtf-font-md)' }}>{title}</Typography>
                )}
                {subtitle != null && (
                  <Typography sx={{ fontSize: 'var(--vtf-font-sm)', color: 'text.secondary', mt: 0.5 }}>{subtitle}</Typography>
                )}
              </Box>
              {rightSlot}
            </Box>
          ) : null}

          {children}
        </Box>
      </CardContent>
    </Card>
  )
}
