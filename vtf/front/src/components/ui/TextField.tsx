import * as React from 'react'
import MuiTextField from '@mui/material/TextField'
import type { TextFieldProps } from '@mui/material/TextField'

import { mergeSx } from './_mergeSx'

const baseSx: TextFieldProps['sx'] = {
  fontFamily: 'var(--sans)',
}

export const TextField = React.forwardRef<HTMLDivElement, TextFieldProps>(function TextField(props, ref) {
  return <MuiTextField ref={ref} {...props} sx={mergeSx(baseSx, props.sx)} />
})

export type { TextFieldProps }

