import * as React from 'react'
import MuiContainer from '@mui/material/Container'
import type { ContainerProps } from '@mui/material/Container'

import { mergeSx } from './_mergeSx'

const baseSx: ContainerProps['sx'] = {
  fontFamily: 'var(--sans)',
}

export const Container = React.forwardRef<HTMLDivElement, ContainerProps>(function Container(props, ref) {
  return <MuiContainer ref={ref} {...props} sx={mergeSx(baseSx, props.sx)} />
})

export type { ContainerProps }

