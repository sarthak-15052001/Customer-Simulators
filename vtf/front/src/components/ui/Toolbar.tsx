import * as React from 'react'
import MuiToolbar from '@mui/material/Toolbar'
import type { ToolbarProps } from '@mui/material/Toolbar'

import { mergeSx } from './_mergeSx'

const baseSx: ToolbarProps['sx'] = {
  fontFamily: 'var(--sans)',
}

export const Toolbar = React.forwardRef<HTMLDivElement, ToolbarProps>(function Toolbar(props, ref) {
  return <MuiToolbar ref={ref} {...props} sx={mergeSx(baseSx, props.sx)} />
})

export type { ToolbarProps }

