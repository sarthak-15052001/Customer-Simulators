import type { SxProps, Theme } from '@mui/material/styles'

import { selectableTileSx } from './selectableTilePresets'
import { VTF_FONT } from './vtfTypography'

export type VtfPlusTone = 'navy' | 'orange'

export type VtfToggleTone = 'orange' | 'teal'

export type VtfSegmentAccent = 'teal' | 'orange'

/** Kept literal names: counters, remove, row toggle, wizard steps. */
export type VtfButtonVariant =
  | 'counterMinus'
  | 'counterPlus'
  | 'iconRemove'
  | 'toggle'
  | 'stepPrevious'
  | 'stepNext'
  /** Small navy filled pill (e.g. add row). Surfaces: `.vtf-btn-navy-fill-pill` */
  | 'navyFillPill'
  /** Solid orange CTA (header, landing hero — hero scales via `sx`). `.vtf-btn-orange-fill` */
  | 'orangeFill'
  /** Orange pill alias used by detail CTA actions. */
  | 'orangeFillPill'
  /** Compact solid orange (recap bar). `.vtf-btn-orange-fill-compact` */
  | 'orangeFillCompact'
  /** Cream pill, navy when selected (e.g. night shortcuts). `.vtf-btn-navy-filter-pill` */
  | 'navyFilterPill'
  /** Two-tone mode control (teal vs orange selected). `.vtf-btn-mode-pill` */
  | 'modePickerPill'
  /** Stay step: large selectable tile (navy accent). Uses `tileSelected` / `tileMinHeight`. */
  | 'selectableTileNavy'
  | 'selectableTileTeal'
  | 'selectableTileOrange'
  /** Stay results: full-width village row (`villageRowAccent` + `villageRowSelected`). */
  | 'stayVillageRow'

export type VtfCounterSize = 'sm' | 'md' | 'lg'

export type VtfCounterShape = 'soft' | 'circle'

export type VtfButtonOwnProps = {
  vtfVariant?: VtfButtonVariant
  plusTone?: VtfPlusTone
  toggleChecked?: boolean
  toggleTone?: VtfToggleTone
  filterActive?: boolean
  segmentSelected?: boolean
  segmentAccent?: VtfSegmentAccent
  counterSize?: VtfCounterSize
  counterShape?: VtfCounterShape
  /** Selectable tile variants (`selectableTile*`). */
  tileSelected?: boolean
  /** Override default min height (126) for compact grids. */
  tileMinHeight?: number
  /** `stayVillageRow` accent. */
  villageRowAccent?: VtfSegmentAccent
  /** `stayVillageRow` selected state. */
  villageRowSelected?: boolean
}

export type VtfButtonPreset = {
  sx?: SxProps<Theme>
  className?: string
}

const counterDims: Record<VtfCounterSize, SxProps<Theme>> = {
  sm: { minWidth: 28, width: 28, height: 28, fontSize: VTF_FONT.xs },
  md: { minWidth: 32, width: 32, height: 32, fontSize: VTF_FONT.sm },
  lg: { minWidth: 38, width: 38, height: 38, fontSize: VTF_FONT.md },
}

export type VtfButtonPresetInput = Required<
  Pick<
    VtfButtonOwnProps,
    | 'vtfVariant'
    | 'plusTone'
    | 'toggleChecked'
    | 'toggleTone'
    | 'filterActive'
    | 'segmentSelected'
    | 'segmentAccent'
    | 'counterSize'
    | 'counterShape'
    | 'tileSelected'
    | 'villageRowAccent'
    | 'villageRowSelected'
  >
> & { tileMinHeight?: number }

export function getVtfButtonPreset(props: VtfButtonPresetInput): VtfButtonPreset {
  const {
    vtfVariant,
    plusTone,
    toggleChecked,
    toggleTone,
    filterActive,
    segmentSelected,
    segmentAccent,
    counterSize,
    counterShape,
    tileSelected,
    tileMinHeight,
    villageRowAccent,
    villageRowSelected,
  } = props

  const radiusSoft = counterShape === 'circle' ? '999px' : '8px'
  const dim = counterDims[counterSize]

  switch (vtfVariant) {
    case 'navyFillPill':
      return { className: 'vtf-btn-navy-fill-pill' }
    case 'orangeFill':
      return { className: 'vtf-btn-orange-fill' }
    case 'orangeFillPill':
      return { className: 'vtf-btn-orange-fill' }
    case 'orangeFillCompact':
      return { className: 'vtf-btn-orange-fill-compact' }
    case 'navyFilterPill':
      return {
        className: `vtf-btn-navy-filter-pill${filterActive ? ' vtf-btn-navy-filter-pill--on' : ''}`,
      }
    case 'modePickerPill': {
      const modeClass =
        segmentAccent === 'teal' && segmentSelected
          ? 'vtf-btn-mode-pill vtf-btn-mode-pill--teal-on'
          : segmentAccent === 'orange' && segmentSelected
            ? 'vtf-btn-mode-pill vtf-btn-mode-pill--orange-on'
            : 'vtf-btn-mode-pill'
      return { className: modeClass }
    }
    case 'selectableTileNavy':
      return {
        sx: selectableTileSx({
          selected: tileSelected,
          accent: 'navy',
          ...(tileMinHeight != null ? { minHeight: tileMinHeight } : {}),
        }),
      }
    case 'selectableTileTeal':
      return {
        sx: selectableTileSx({
          selected: tileSelected,
          accent: 'teal',
          ...(tileMinHeight != null ? { minHeight: tileMinHeight } : {}),
        }),
      }
    case 'selectableTileOrange':
      return {
        sx: selectableTileSx({
          selected: tileSelected,
          accent: 'orange',
          ...(tileMinHeight != null ? { minHeight: tileMinHeight } : {}),
        }),
      }
    case 'stayVillageRow': {
      const accent = villageRowAccent
      const selected = villageRowSelected
      const borderColor = selected ? (accent === 'teal' ? 'var(--vtf-teal)' : 'var(--vtf-orange)') : 'rgba(15, 23, 42, 0.08)'
      const bgColor = selected
        ? accent === 'teal'
          ? 'rgba(var(--vtf-teal-rgb), 0.06)'
          : 'rgba(var(--vtf-orange-rgb), 0.06)'
        : 'white'
      return {
        sx: {
          width: '100%',
          textAlign: 'left',
          p: 2,
          mb: 1,
          borderRadius: '16px',
          border: '2px solid',
          borderColor,
          bgcolor: bgColor,
          boxShadow: 'none',
          textTransform: 'none',
          alignItems: 'stretch',
          '&:hover': { boxShadow: 'none' },
        },
      }
    }
    case 'counterMinus':
      return {
        sx: {
          ...dim,
          p: 0,
          borderRadius: radiusSoft,
          bgcolor: 'white',
          color: 'var(--vtf-navy)',
          fontWeight: 950,
          boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
          '&:hover': { bgcolor: 'white' },
          '&.Mui-disabled': { 
            opacity: counterSize === 'lg' ? 0.35 : 0.3,
            bgcolor: 'white',
            color: 'var(--vtf-navy)',
            boxShadow: 'none',
          },
        },
      }
    case 'counterPlus': {
      if (plusTone === 'orange') {
        return {
          sx: {
            ...dim,
            p: 0,
            borderRadius: radiusSoft,
            bgcolor: 'rgba(var(--vtf-orange-rgb), 0.08)',
            color: 'var(--vtf-orange)',
            fontWeight: 950,
            boxShadow: 'none',
            border: '2px solid rgba(var(--vtf-orange-rgb), 0.35)',
            '&:hover': { bgcolor: 'rgba(var(--vtf-orange-rgb), 0.12)', boxShadow: 'none' },
            '&.Mui-disabled': { 
              opacity: 0.35,
              bgcolor: 'rgba(var(--vtf-orange-rgb), 0.08)',
              color: 'var(--vtf-orange)',
              border: '2px solid rgba(var(--vtf-orange-rgb), 0.35)',
              boxShadow: 'none',
            },
          },
        }
      }
      return {
        sx: {
          ...dim,
          p: 0,
          borderRadius: radiusSoft,
          bgcolor: 'var(--vtf-navy)',
          color: 'white',
          fontWeight: 950,
          boxShadow: '0 2px 8px rgba(0,68,90,0.15)',
          '&:hover': { bgcolor: 'var(--vtf-navy)' },
          '&.Mui-disabled': { 
            opacity: 0.3,
            bgcolor: 'var(--vtf-navy)',
            color: 'white',
            boxShadow: 'none',
          },
        },
      }
    }
    case 'iconRemove':
      return {
        sx: {
          minWidth: 28,
          width: 28,
          height: 28,
          borderRadius: '10px',
          bgcolor: 'white',
          color: 'rgba(0,68,90,0.55)',
          fontSize: VTF_FONT.sm,
          fontWeight: 900,
          p: 0,
          boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
          border: '1px solid rgba(15, 23, 42, 0.08)',
          '&:hover': {
            color: '#b91c1c',
            borderColor: 'rgba(185, 28, 28, 0.25)',
            bgcolor: 'rgba(185, 28, 28, 0.05)',
          },
        },
      }
    case 'toggle': {
      const checkedBg =
        toggleTone === 'orange'
          ? 'rgba(var(--vtf-orange-rgb), 0.20)'
          : 'rgba(var(--vtf-teal-rgb), 0.15)'
      const uncheckedBg = 'rgba(15,23,42,0.04)'
      const checkedColor = toggleTone === 'orange' ? 'rgba(185, 28, 28, 0.85)' : 'var(--vtf-teal)'
      const hoverChecked =
        toggleTone === 'orange' ? 'rgba(var(--vtf-orange-rgb), 0.26)' : 'rgba(var(--vtf-teal-rgb), 0.18)'
      return {
        sx: {
          ...counterDims.sm,
          borderRadius: '8px',
          bgcolor: toggleChecked ? checkedBg : uncheckedBg,
          color: toggleChecked ? checkedColor : 'rgba(15,23,42,0.55)',
          fontWeight: 950,
          p: 0,
          boxShadow: 'none',
          border: '1px solid rgba(15,23,42,0.08)',
          '&:hover': { bgcolor: toggleChecked ? hoverChecked : 'rgba(15,23,42,0.06)' },
        },
      }
    }
    case 'stepPrevious':
      return {
        sx: {
          minWidth: 140,
          height: 45,
          borderRadius: '16px',
          textTransform: 'none',
          fontSize: VTF_FONT.md,
          fontWeight: 800,
          color: 'var(--vtf-navy)',
          border: '1px solid rgba(15, 23, 42, 0.08)',
          '&:hover': { bgcolor: 'rgba(0, 68, 90, 0.04)' },
          '&:disabled': { opacity: 0.2 },
        },
      }
    case 'stepNext':
      return {
        sx: {
          minWidth: 140,
          height: 45,
          borderRadius: '16px',
          textTransform: 'none',
          fontSize: VTF_FONT.md,
          fontWeight: 900,
          background: 'var(--vtf-navy)',
          color: 'white',
          boxShadow: '0 8px 24px rgba(0, 68, 90, 0.25)',
          border: '1px solid rgba(15, 23, 42, 0.08)',
          '&:hover': {
            background: 'var(--vtf-navy)',
            transform: 'translateY(-2px)',
            boxShadow: '0 12px 32px rgba(0, 68, 90, 0.35)',
          },
          '&:active': { transform: 'translateY(1px)' },
          '&:disabled': { bgcolor: 'rgba(0,68,90,0.08)', color: 'rgba(0,68,90,0.2)', boxShadow: 'none' },
        },
      }
    default:
      return {}
  }
}
