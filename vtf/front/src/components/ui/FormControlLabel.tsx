import * as React from 'react'
import MuiFormControlLabel from '@mui/material/FormControlLabel'
import type { FormControlLabelProps } from '@mui/material/FormControlLabel'

import { mergeSx } from './_mergeSx'

const baseSx: FormControlLabelProps['sx'] = {
  fontFamily: 'var(--sans)',
}

export const FormControlLabel = React.forwardRef<HTMLLabelElement, FormControlLabelProps>(
  function FormControlLabel(props, ref) {
    return <MuiFormControlLabel ref={ref} {...props} sx={mergeSx(baseSx, props.sx)} />
  },
)

export type { FormControlLabelProps }

