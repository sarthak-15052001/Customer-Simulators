import * as React from "react";
import { createPortal } from "react-dom";

export interface Option {
  value: string;
  label: string;
  disabled?: boolean;
  icon?: React.ReactNode;
  isHeader?: boolean;
  badge?: string | number;
}
export interface SelectProps {
  options: Option[];
  value?: string;
  defaultValue?: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
  style?: React.CSSProperties;
  portal?: boolean;
  showIcons?: boolean;
  variant?: "dark" | "light" | "topbar";
  hideScrollbar?: boolean;
  menuWidth?: number;
  size?: "default" | "compact";
  /** Align dropdown menu to the left or right edge of the trigger. */
  menuAlign?: "left" | "right";
  /** Accessible name when no visible label is associated. */
  ariaLabel?: string;
}

const UI = {
  chk: "M16.704 5.29a1 1 0 010 1.42l-7.2 7.2a1 1 0 01-1.42 0l-3.2-3.2a1 1 0 011.42-1.42l2.49 2.49 6.49-6.49a1 1 0 011.42 0z",
  icn: "M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z",
  btn: {
    l_d: "inline-flex w-full items-center gap-x-2 rounded-[999px] bg-white px-3.5 py-2.5 text-[var(--vtf-font-sm)] font-semibold text-[color:var(--vtf-navy)] shadow-[0_2px_14px_rgba(15,23,42,0.07)] border border-slate-200/95 hover:border-slate-300/90 hover:bg-[linear-gradient(180deg,#fff_0%,#fafbfc_100%)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(0,168,181,0.35)]",
    l_c: "inline-flex w-full items-center gap-x-1.5 rounded-[999px] bg-white px-2.5 py-1.5 text-[var(--vtf-font-sm)] font-semibold text-[color:var(--vtf-navy)] shadow-[0_1px_10px_rgba(15,23,42,0.06)] border border-slate-200/90 hover:border-slate-300/85 hover:bg-[linear-gradient(180deg,#fff_0%,#fafbfc_100%)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(0,168,181,0.32)]",
    d_d: "inline-flex w-full items-center gap-x-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-white/20 border border-white/20 transition-all",
    d_c: "inline-flex w-full items-center gap-x-1.5 rounded-full bg-white/10 px-2.5 py-1 text-[var(--vtf-font-sm)] font-bold text-white shadow-sm hover:bg-white/20 border border-white/20 transition-all",
    t_c: "inline-flex w-auto items-center gap-x-1 bg-transparent border-0 p-0 pr-5 text-[var(--vtf-font-sm)] font-light text-white shadow-none hover:bg-transparent focus:outline-none focus-visible:ring-0",
  },
  chev: {
    l_d: "-mr-0.5 h-5 w-5 shrink-0 text-slate-400 transition-transform duration-200",
    l_c: "-mr-0.5 h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200",
    d_d: "-mr-1 h-4 w-4 text-white/60",
    d_c: "-mr-0.5 h-3.5 w-3.5 shrink-0 text-white/60",
    t_c: "absolute right-0 top-1/2 h-2 w-2 -translate-y-1/2 shrink-0 text-white",
  },
};

const Svg = ({ d, cls }: { d: string; cls?: string }) => (
  <svg
    className={cls}
    viewBox="0 0 20 20"
    fill="currentColor"
    aria-hidden="true"
  >
    <path fillRule="evenodd" clipRule="evenodd" d={d} />
  </svg>
);

export function Select({
  options = [],
  value,
  defaultValue = "",
  onChange,
  placeholder = "Select",
  className = "",
  style,
  portal = true,
  showIcons = true,
  variant = "dark",
  hideScrollbar,
  menuWidth = 150,
  size = "default",
  menuAlign = "left",
  ariaLabel,
}: SelectProps) {
  const [open, setOpen] = React.useState(false);
  const [u, setU] = React.useState(defaultValue);
  const [pos, setPos] = React.useState<{
    top: number;
    left: number;
    width: number;
    fixed?: boolean;
  } | null>(null);
  const [hasOverflow, setHasOverflow] = React.useState(false);
  const [thumbStyle, setThumbStyle] = React.useState<{ height: number; top: number }>({ height: 0, top: 0 });

  const v = value ?? u;
  const sel = options.find((o) => o.value === v);
  const cmp = size === "compact";
  const ref = React.useRef<HTMLDivElement>(null);
  const btn = React.useRef<HTMLButtonElement>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  const updateThumb = React.useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const { scrollHeight, clientHeight, scrollTop } = el;
    const trackInset = 16; // 8px top + 8px bottom
    const trackHeight = clientHeight - trackInset;
    if (scrollHeight <= clientHeight + 1 || trackHeight <= 0) {
      setHasOverflow(false);
      return;
    }
    setHasOverflow(true);
    const thumbPx = Math.max(20, (trackHeight / scrollHeight) * trackHeight);
    const maxScroll = scrollHeight - clientHeight;
    const topPx = maxScroll > 0 ? (scrollTop / maxScroll) * (trackHeight - thumbPx) : 0;
    setThumbStyle({ height: thumbPx, top: topPx });
  }, []);

  const theme = (
    variant === "topbar" ? "t_c" : `${variant.charAt(0)}_${cmp ? "c" : "d"}`
  ) as keyof typeof UI.btn;

  const repos = React.useCallback(() => {
    if (!btn.current) return;
    const r = btn.current.getBoundingClientRect(),
      w = Math.max(menuWidth, Math.min(window.innerWidth - 24, r.width)),
      h = btn.current.closest(".MuiAppBar-root, header");
    const fx =
      h && ["sticky", "fixed"].includes(window.getComputedStyle(h).position);
    const top =
      window.innerHeight - r.bottom < (cmp ? 232 : 312) &&
      r.top > window.innerHeight - r.bottom
        ? Math.max(12, r.top - 8 - (cmp ? 220 : 300))
        : Math.min(window.innerHeight - 12, r.bottom + 8);
    const rawLeft = menuAlign === "right" ? r.right - w : r.left;
    const scrollX = fx ? 0 : window.scrollX;
    setPos({
      top: fx ? top : top + window.scrollY,
      left:
        scrollX + Math.max(12, Math.min(window.innerWidth - w - 12, rawLeft)),
      width: w,
      fixed: !!fx,
    });
  }, [menuWidth, cmp, menuAlign]);

  React.useEffect(() => {
    const fn = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", fn);
    return () => document.removeEventListener("mousedown", fn);
  }, []);

  React.useEffect(() => {
    if (!open || !portal) return;
    repos();
    window.addEventListener("resize", repos);
    window.addEventListener("scroll", repos, true);
    return () => {
      window.removeEventListener("resize", repos);
      window.removeEventListener("scroll", repos, true);
    };
  }, [open, portal, repos]);

  React.useLayoutEffect(() => {
    if (open) {
      // Delay slightly to ensure rendered dimensions are measured correctly
      const t = setTimeout(() => updateThumb(), 10);
      return () => clearTimeout(t);
    }
  }, [open, options, updateThumb]);

  const isTopbar = variant === "topbar";

  const menuContainer = `relative ${portal ? "" : "z-[100] absolute mt-1.5"} w-full border border-slate-200/80 bg-white shadow-[0_18px_44px_-16px_rgba(2,8,23,0.24)] ring-1 ring-slate-900/[0.035] outline-none overflow-hidden ${cmp ? "rounded-[14px]" : "rounded-[20px]"}${isTopbar ? " vtf-topbar-lang-menu" : ""}`;
  const menuScroll = `no-scrollbar w-full overflow-x-hidden overflow-y-auto ${cmp ? "max-h-[min(11rem,38vh)] p-1 pr-2.5" : "max-h-[min(18rem,calc(100vh-7rem))] p-1.5 pr-3"}`;

  const menuItemTextClass = (o: Option) => {
    if (isTopbar) {
      return "text-[length:var(--vtf-font-sm)] font-light tracking-normal text-[color:var(--vtf-navy)]";
    }
    if (o.isHeader) {
      return "text-[length:var(--vtf-font-xs)] font-black uppercase tracking-[0.08em] text-slate-400";
    }
    return "text-[length:var(--vtf-font-sm)] font-semibold tracking-tight text-[color:var(--vtf-navy)]";
  };

  const menu = (
    <div
      className={menuContainer}
      style={
        portal
          ? {
              position: pos?.fixed ? "fixed" : "absolute",
              top: pos?.top || 0,
              left: pos?.left || 0,
              width: pos?.width,
              zIndex: 2000,
            }
          : undefined
      }
    >
      <div ref={scrollRef} className={menuScroll} onScroll={updateThumb}>
        {!options.length ? (
          <div
            className={`text-slate-400 ${isTopbar || cmp ? "px-3 py-2 text-[length:var(--vtf-font-sm)]" : "px-4 py-2.5 text-sm"}`}
          >
            Aucune option
          </div>
        ) : (
          options.map((o, i) => {
            const isSelected = v === o.value;
            const bg = o.isHeader
              ? "mt-1.5 cursor-default opacity-100 first:mt-0"
              : o.disabled
                ? "cursor-not-allowed opacity-40 text-slate-400"
                : isSelected
                  ? "bg-[linear-gradient(90deg,rgba(242,166,128,0.22)_0%,rgba(242,166,128,0.06)_55%,transparent_100%)] text-[color:var(--vtf-navy)] shadow-[inset_2px_0_0_0_var(--vtf-orange)]"
                  : "text-[color:var(--vtf-navy)] hover:bg-slate-50 active:scale-[0.995]";
            return (
              <button
                key={o.value || `h-${i}`}
                type="button"
                disabled={o.disabled}
                onMouseDown={(e) => e.stopPropagation()}
                onClick={() => {
                  if (!o.disabled && !o.isHeader) {
                    if (value === undefined) setU(o.value);
                    onChange(o.value);
                    setOpen(false);
                  }
                }}
                className={`group relative flex w-full items-center text-left transition-all duration-150 ease-out ${cmp ? "gap-1.5 rounded-lg px-2 py-1.5" : "gap-2.5 rounded-xl px-3 py-2.5"} ${bg}`}
              >
                {showIcons && o.icon && (
                  <span
                    className={`shrink-0 text-xs transition-transform ${o.isHeader ? "scale-90 text-slate-400" : "group-hover:scale-110"} ${cmp ? "mr-0.5" : "mr-2"}`}
                  >
                    {o.icon}
                  </span>
                )}
                <span
                  className={`min-w-0 flex-1 leading-snug ${menuItemTextClass(o)}`}
                >
                  <span className={o.isHeader ? "" : "line-clamp-2"}>
                    {o.label}
                  </span>
                </span>
                {!o.isHeader && o.badge && (
                  <span
                    className={`flex shrink-0 items-center justify-center rounded-full border border-vtf-orange/30 bg-white tabular-nums text-vtf-orange ${cmp ? "h-5 min-w-5 text-[var(--vtf-font-xs)] shadow-[0_1px_3px_rgba(242,166,128,0.3)]" : "h-7 min-w-7 text-[var(--vtf-font-sm)] shadow-[0_1px_4px_rgba(242,166,128,0.35)]"}`}
                  >
                    {o.badge}
                  </span>
                )}
                {!o.isHeader && isSelected && (
                  <div
                    className={`flex shrink-0 items-center justify-center rounded-full bg-vtf-orange/15 ring-1 ring-vtf-orange/25 ${cmp ? "h-5 w-5" : "h-7 w-7"}`}
                  >
                    <Svg
                      cls={`text-vtf-orange ${cmp ? "h-2.5 w-2.5" : "h-3 w-3"}`}
                      d={UI.chk}
                    />
                  </div>
                )}
              </button>
            );
          })
        )}
      </div>
      {hasOverflow && !hideScrollbar && (
        <div
          className="pointer-events-none absolute right-1.5 top-2 bottom-2 w-[6px] rounded-full bg-[rgba(0,68,90,0.08)] z-[2001]"
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
    </div>
  );

  return (
    <div ref={ref} className={`relative ${className}`} style={style}>
      <button
        ref={btn}
        type="button"
        role="combobox"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className={`group relative ${UI.btn[theme]}`}
      >
        <span
          className={`flex min-w-0 items-center ${isTopbar ? "gap-1" : `flex-1 ${cmp ? "gap-1.5" : "gap-2"}`}`}
        >
          {showIcons && sel?.icon && (
            <span className="shrink-0">{sel.icon}</span>
          )}
          <span
            className={`min-w-0 truncate text-left ${isTopbar ? "text-[length:var(--vtf-font-sm)] leading-[17px]" : "flex-1 leading-tight"} ${sel ? "vtf-select-value" : "vtf-select-placeholder"}`}
          >
            {sel ? sel.label : placeholder}
          </span>
          {sel?.badge && (
            <span
              className={`flex shrink-0 items-center justify-center rounded-full border border-vtf-orange/35 bg-[linear-gradient(180deg,#fff_0%,rgba(242,166,128,0.1)_100%)] tabular-nums text-vtf-orange ${cmp ? "h-5 min-w-5 text-[var(--vtf-font-xs)] shadow-[0_1px_4px_rgba(242,166,128,0.32)]" : "h-7 min-w-7 text-[var(--vtf-font-sm)] shadow-[0_1px_5px_rgba(242,166,128,0.35)]"}`}
            >
              {sel.badge}
            </span>
          )}
        </span>
        {isTopbar ? (
          <svg
            className={UI.chev[theme]}
            aria-hidden="true"
            xmlns="http://www.w3.org/2000/svg"
            width="7"
            height="4"
            viewBox="0 0 7 4"
          >
            <path fill="currentColor" fillRule="evenodd" d="M0 0l3.5 4L7 0z" />
          </svg>
        ) : (
          <Svg
            cls={`${UI.chev[theme]} ${variant === "light" && open ? "rotate-180" : ""}`}
            d={UI.icn}
          />
        )}
      </button>
      {open && (portal ? pos && createPortal(menu, document.body) : menu)}
    </div>
  );
}

export const VtfSelect = ({
  width,
  placeholder = "Select",
  className = "",
  ...rest
}: SelectProps & { width?: number | string }) => (
  <Select
    {...rest}
    placeholder={placeholder}
    className={`font-montserrat ${className}`.trim()}
    defaultValue=""
    style={
      width != null
        ? { width: typeof width === "number" ? `${width}px` : width }
        : undefined
    }
    portal
  />
);
