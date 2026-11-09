import * as React from 'react'
import type { SxProps, Theme } from '@mui/material/styles'
import { Box, Button } from '../ui'

export type QuantityStepperProps = {
  value: number
  onDec: () => void
  onInc: () => void
  decDisabled?: boolean
  incDisabled?: boolean
  counterSize?: 'sm' | 'md'
  plusTone?: 'navy'
  containerClassName?: string
  containerSx?: SxProps<Theme>
  decAriaLabel?: string
  incAriaLabel?: string
  decButtonSx?: SxProps<Theme>
  incButtonSx?: SxProps<Theme>
  children?: React.ReactNode
}

export function QuantityStepper({
  value,
  onDec,
  onInc,
  decDisabled = false,
  incDisabled = false,
  counterSize = 'sm',
  plusTone,
  containerClassName,
  containerSx,
  decAriaLabel,
  incAriaLabel,
  decButtonSx,
  incButtonSx,
  children,
}: QuantityStepperProps) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, ...containerSx }} className={containerClassName}>
      <Button
        type="button"
        vtfVariant="counterMinus"
        counterSize={counterSize}
        onClick={onDec}
        disabled={decDisabled}
        aria-label={decAriaLabel}
        sx={decButtonSx}
      >
        −
      </Button>

      {children ?? <Box component="span">{value}</Box>}

      <Button
        type="button"
        vtfVariant="counterPlus"
        counterSize={counterSize}
        plusTone={plusTone}
        onClick={onInc}
        disabled={incDisabled}
        aria-label={incAriaLabel}
        sx={incButtonSx}
      >
        +
      </Button>
    </Box>
  )
}

