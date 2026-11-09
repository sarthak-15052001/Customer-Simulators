import * as React from 'react'
import MuiBox from '@mui/material/Box'
import type { BoxProps } from '@mui/material/Box'

import { mergeSx } from './_mergeSx'

const baseSx: BoxProps['sx'] = {
  fontFamily: 'var(--sans)',
}

export const Box = React.forwardRef(function Box(props: BoxProps, ref) {
  return <MuiBox ref={ref} {...props} sx={mergeSx(baseSx, props.sx)} />
}) as typeof MuiBox

export type { BoxProps }

