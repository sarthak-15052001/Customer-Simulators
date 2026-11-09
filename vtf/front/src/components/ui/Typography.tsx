import * as React from 'react'
import MuiTypography from '@mui/material/Typography'
import type { TypographyProps } from '@mui/material/Typography'

import { mergeSx } from './_mergeSx'

const baseSx: TypographyProps['sx'] = {
  fontFamily: 'var(--sans)',
}

export const Typography = React.forwardRef<HTMLSpanElement, TypographyProps>(function Typography(props, ref) {
  return <MuiTypography ref={ref} component={props.component ?? 'div'} {...props} sx={mergeSx(baseSx, props.sx)} />
})

export type { TypographyProps }

