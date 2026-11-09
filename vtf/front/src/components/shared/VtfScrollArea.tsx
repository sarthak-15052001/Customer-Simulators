import * as React from "react";
import { Box, type BoxProps } from "../ui";

type VtfScrollAreaProps = {
  children: React.ReactNode;
  maxHeight?: number | string | object;
  className?: string;
  sx?: BoxProps["sx"];
};

export function VtfScrollArea({
  children,
  maxHeight = 360,
  className = "",
  sx,
}: VtfScrollAreaProps) {
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const [hasOverflow, setHasOverflow] = React.useState(false);
  const [thumbStyle, setThumbStyle] = React.useState<{ height: number; top: number }>({
    height: 0,
    top: 0,
  });

  const updateThumb = React.useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const { scrollHeight, clientHeight, scrollTop } = el;
    const trackInset = 16; // 8px top + 8px bottom (matches top-2 and bottom-2)
    const trackHeight = clientHeight - trackInset;

    if (scrollHeight <= clientHeight + 1 || trackHeight <= 0) {
      setHasOverflow(false);
      return;
    }

    setHasOverflow(true);
    const thumbPx = Math.max(24, (trackHeight / scrollHeight) * trackHeight);
    const maxScroll = scrollHeight - clientHeight;
    const topPx = maxScroll > 0 ? (scrollTop / maxScroll) * (trackHeight - thumbPx) : 0;
    setThumbStyle({ height: thumbPx, top: topPx });
  }, []);

  React.useLayoutEffect(() => {
    updateThumb();
    const el = scrollRef.current;
    if (!el) return;

    const observer = new ResizeObserver(() => updateThumb());
    observer.observe(el);
    if (el.firstElementChild) {
      observer.observe(el.firstElementChild);
    }

    window.addEventListener("resize", updateThumb);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", updateThumb);
    };
  }, [children, updateThumb]);

  return (
    <Box sx={{ position: "relative", width: "100%", ...sx }}>
      <Box
        ref={scrollRef}
        onScroll={updateThumb}
        className={`no-scrollbar ${className}`}
        sx={{
          width: "100%",
          maxHeight,
          overflowX: "hidden",
          overflowY: "auto",
          WebkitOverflowScrolling: "touch",
        }}
      >
        {children}
      </Box>
      {hasOverflow && (
        <div
          className="pointer-events-none absolute right-1 top-2 bottom-2 w-[6px] rounded-full bg-[rgba(0,68,90,0.08)] z-[10]"
          aria-hidden="true"
        >
          <div
            className="w-full rounded-full bg-[rgba(0,68,90,0.55)] border border-white transition-transform duration-75"
            style={{
              height: `${thumbStyle.height}px`,
              transform: `translateY(${thumbStyle.top}px)`,
            }}
          />
        </div>
      )}
    </Box>
  );
}
