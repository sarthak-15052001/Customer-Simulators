import * as React from 'react'
import { Box, Typography } from '../ui'

/** Space below section heading before card body (matches StaySeasonCard). */
export const VTF_SECTION_HEADING_MB = 3

export type VtfHeadingAccent = 'orange' | 'teal' | 'navy'

const ACCENT_CLASS: Record<VtfHeadingAccent, { box: string; iconColor: string }> = {
  orange: {
    box: 'w-10 h-10 rounded-[14px] bg-[#faf3ef] flex items-center justify-center border border-[#f0ddd4] shadow-[0_8px_20px_rgba(242,166,128,0.12)]',
    iconColor: 'var(--vtf-orange-dark)',
  },
  teal: {
    box: 'w-10 h-10 rounded-[14px] bg-[#f0fafb] flex items-center justify-center border border-[#d4ecef] shadow-[0_8px_20px_rgba(0,168,181,0.1)]',
    iconColor: 'var(--vtf-teal)',
  },
  navy: {
    box: 'w-10 h-10 rounded-[14px] bg-[#f4f7f8] flex items-center justify-center border border-[#e2e8ec] shadow-[0_8px_20px_rgba(0,24,38,0.05)]',
    iconColor: 'var(--vtf-navy)',
  },
}

export type VtfSectionIconProps = {
  icon: React.ReactElement<{ sx?: object }>
  accent?: VtfHeadingAccent
}

/** Light gradient icon badge — same as section headings (ACTIVITÉS, TRANSPORT, etc.). */
export function VtfSectionIcon({ icon, accent = 'orange' }: VtfSectionIconProps) {
  const styles = ACCENT_CLASS[accent]
  const iconNode = React.cloneElement(icon, {
    sx: { color: styles.iconColor, fontSize: 'var(--vtf-font-lg)', ...(icon.props.sx ?? {}) },
  })

  return <Box className={styles.box}>{iconNode}</Box>
}

export type VtfSectionHeadingProps = {
  icon: React.ReactElement<{ sx?: object }>
  title: React.ReactNode
  subtitle?: React.ReactNode
  accent?: VtfHeadingAccent
  rightSlot?: React.ReactNode
  mb?: number | string
  /** When false, `title` is rendered as-is (e.g. hero total layout). Default true. */
  wrapTitle?: boolean
}

export function VtfSectionHeading({
  icon,
  title,
  subtitle,
  accent = 'orange',
  rightSlot,
  mb = VTF_SECTION_HEADING_MB,
  wrapTitle = true,
}: VtfSectionHeadingProps) {
  const accentStyles = ACCENT_CLASS[accent]

  return (
    <Box
      className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
      sx={{
        mb,
        pb: 1.75,
        borderBottom: '1px solid rgba(0, 68, 90, 0.08)',
      }}
    >
      <Box className={`flex min-w-0 gap-2 ${wrapTitle ? 'items-center' : 'items-start'}`}>
        <VtfSectionIcon icon={icon} accent={accent} />
        <Box sx={{ minWidth: 0 }}>
          {wrapTitle ? (
            <Typography
              variant="body2"
              sx={{
                fontWeight: 950,
                color: accentStyles.iconColor,
                fontSize: 'var(--vtf-font-md)',
                lineHeight: 1.2,
              }}
            >
              {title}
            </Typography>
          ) : (
            title
          )}
          {subtitle != null ? (
            <Typography sx={{ fontSize: 'var(--vtf-font-sm)', color: 'text.secondary', mt: 0.5, lineHeight: 1.35 }}>
              {subtitle}
            </Typography>
          ) : null}
        </Box>
      </Box>
      {rightSlot ? (
        <Box className="flex w-full min-w-0 items-center self-stretch sm:w-auto sm:shrink-0 sm:self-auto">
          {rightSlot}
        </Box>
      ) : null}
    </Box>
  )
}
