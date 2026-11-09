import * as React from 'react'
import MuiAppBar from '@mui/material/AppBar'
import type { AppBarProps } from '@mui/material/AppBar'

import { mergeSx } from './_mergeSx'

const baseSx: AppBarProps['sx'] = {
  fontFamily: 'var(--sans)',
}

export const AppBar = React.forwardRef<HTMLDivElement, AppBarProps>(function AppBar(props, ref) {
  return <MuiAppBar ref={ref} {...props} sx={mergeSx(baseSx, props.sx)} />
})

export type { AppBarProps }

