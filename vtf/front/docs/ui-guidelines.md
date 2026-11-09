# UI guidelines (Tailwind + MUI) — simulateur_vtf

This repo intentionally mixes:

- **MUI** for component behavior & accessibility (Button, TextField, Menu-like UI, etc.)
- **Tailwind** for layout + “surface” styling (glass cards, spacing, grid, typography utilities)
- **Small reusable presets** to avoid repeated `sx` blocks (`vtfVariant` in `Button`, `vtf-glass-*` classes, etc.)

## When to use what

- **Use Tailwind classes** for:
  - Layout: `flex`, `grid`, `gap-*`, responsive breakpoints
  - Surface helpers: `vtf-glass-strong`, `vtf-glass-soft`, `vtf-tab-stack`
  - Simple typography/spacing that doesn’t need theme values

- **Use MUI `sx`** for:
  - Styling *inside* MUI components where Tailwind is awkward (e.g. `TextField` slots)
  - Token-based colors (CSS vars like `var(--vtf-navy)`) and component-specific tweaks
  - One-off styling that is truly unique to a single component

- **Prefer reusable presets** when you see repetition:
  - **Buttons**: add/extend `vtfVariant` presets in `src/components/ui/buttonVtfPresets.ts`
  - **Selectable tiles**: use `vtfVariant="selectableTile*"` + `tileSelected` (+ `tileMinHeight` if needed)
  - **Card wrappers**: use `vtfTransparentCardSx` + `vtfTransparentCardContentSx` from `src/components/ui/vtfCardPresets.ts`

## Rules of thumb (keeps code clean)

- **No repeated `sx` blocks** across multiple files. If copied twice, extract a preset.
- **No new hardcoded user text** inside components. Use locale keys (`useTranslation`) even for pills/empty states.
- **One primary button system**: use the shared `Button` wrapper and `vtfVariant` for consistent look & behavior.
- **Keep generic UI in `src/components/ui/`**. Keep simulateur-only UI in `src/components/simulateur-vtf/`.

