import * as React from 'react'
import MuiIconButton from '@mui/material/IconButton'
import type { IconButtonProps } from '@mui/material/IconButton'

import { mergeSx } from './_mergeSx'

const baseSx: IconButtonProps['sx'] = {
  fontFamily: 'var(--sans)',
}

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(props, ref) {
  return <MuiIconButton ref={ref} {...props} sx={mergeSx(baseSx, props.sx)} />
})

export type { IconButtonProps }

