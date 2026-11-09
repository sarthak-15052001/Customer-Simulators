import * as React from 'react'
import MuiLink from '@mui/material/Link'
import type { LinkProps } from '@mui/material/Link'

import { mergeSx } from './_mergeSx'

const baseSx: LinkProps['sx'] = {
  fontFamily: 'var(--sans)',
}

export const Link = React.forwardRef<HTMLAnchorElement, LinkProps>(function Link(props, ref) {
  return <MuiLink ref={ref} {...props} sx={mergeSx(baseSx, props.sx)} />
})

export type { LinkProps }

