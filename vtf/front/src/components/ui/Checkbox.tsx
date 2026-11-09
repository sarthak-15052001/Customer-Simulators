import * as React from 'react'
import MuiCheckbox from '@mui/material/Checkbox'
import type { CheckboxProps } from '@mui/material/Checkbox'

import { mergeSx } from './_mergeSx'

const baseSx: CheckboxProps['sx'] = {
  fontFamily: 'var(--sans)',
}

export const Checkbox = React.forwardRef<HTMLButtonElement, CheckboxProps>(function Checkbox(props, ref) {
  return <MuiCheckbox ref={ref} {...props} sx={mergeSx(baseSx, props.sx)} />
})

export type { CheckboxProps }

