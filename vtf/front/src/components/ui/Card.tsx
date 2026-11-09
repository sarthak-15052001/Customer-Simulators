import * as React from 'react'
import MuiCard from '@mui/material/Card'
import type { CardProps } from '@mui/material/Card'

import { mergeSx } from './_mergeSx'

const baseSx: CardProps['sx'] = {
  fontFamily: 'var(--sans)',
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(function Card(props, ref) {
  return <MuiCard ref={ref} {...props} sx={mergeSx(baseSx, props.sx)} />
})

export type { CardProps }

