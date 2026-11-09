import * as React from 'react'
import MuiButton from '@mui/material/Button'
import type { ButtonProps as MuiButtonProps } from '@mui/material/Button'

import { getVtfButtonPreset } from './buttonVtfPresets'
import type { VtfButtonOwnProps } from './buttonVtfPresets'
import { mergeSx } from './_mergeSx'
import { VTF_FONT } from './vtfTypography'

const baseSx: MuiButtonProps['sx'] = {
  fontFamily: 'var(--sans)',
  fontSize: VTF_FONT.sm,
}

export type ButtonProps = MuiButtonProps & VtfButtonOwnProps

export type {
  VtfButtonVariant,
  VtfButtonOwnProps,
  VtfCounterShape,
  VtfCounterSize,
  VtfPlusTone,
  VtfSegmentAccent,
  VtfToggleTone,
} from './buttonVtfPresets'

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(props, ref) {
  const {
    vtfVariant,
    plusTone = 'navy',
    toggleChecked = false,
    toggleTone = 'teal',
    filterActive = false,
    segmentSelected = false,
    segmentAccent = 'teal',
    counterSize = 'md',
    counterShape = 'soft',
    tileSelected = false,
    tileMinHeight,
    villageRowAccent = 'teal',
    villageRowSelected = false,
    className,
    sx,
    ...rest
  } = props

  const preset =
    vtfVariant != null
      ? getVtfButtonPreset({
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
          villageRowAccent,
          villageRowSelected,
          ...(tileMinHeight != null ? { tileMinHeight } : {}),
        })
      : undefined

  const mergedClassName = [preset?.className, className].filter(Boolean).join(' ') || undefined

  return (
    <MuiButton
      ref={ref}
      {...rest}
      className={mergedClassName}
      sx={mergeSx(baseSx, mergeSx(preset?.sx, sx))}
    />
  )
})
