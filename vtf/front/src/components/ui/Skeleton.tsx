import * as React from "react";
import MuiSkeleton from "@mui/material/Skeleton";
import type { SkeletonProps } from "@mui/material/Skeleton";

import { mergeSx } from "./_mergeSx";

const baseSx: SkeletonProps["sx"] = {
  borderRadius: "12px",
  bgcolor: "rgba(var(--vtf-navy-rgb), 0.05)",
};

export const Skeleton = React.forwardRef<HTMLElement, SkeletonProps>(
  function Skeleton(props, ref) {
    return (
      <MuiSkeleton
        ref={ref}
        animation="wave"
        {...props}
        sx={mergeSx(baseSx, props.sx)}
      />
    );
  },
);

export type { SkeletonProps };
