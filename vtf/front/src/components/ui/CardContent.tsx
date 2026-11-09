import * as React from 'react'
import MuiCardContent from '@mui/material/CardContent'
import type { CardContentProps } from '@mui/material/CardContent'

import { mergeSx } from './_mergeSx'

const baseSx: CardContentProps['sx'] = {
  fontFamily: 'var(--sans)',
}

export const CardContent = React.forwardRef<HTMLDivElement, CardContentProps>(function CardContent(props, ref) {
  return <MuiCardContent ref={ref} {...props} sx={mergeSx(baseSx, props.sx)} />
})

export type { CardContentProps }

