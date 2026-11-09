import * as React from 'react'
import { Box, Typography } from '../../ui'

import { useTranslation } from '../../../contexts/LanguageContext'

export type SimulateurStepKey =
  | 'famille'
  | 'sejour'
  | 'extras'
  | 'resto'
  | 'transport'
  | 'promos'
  | 'planning'
  | 'details'

export type SimulateurStep = {
  key: SimulateurStepKey
  label: string
  icon: React.ReactElement
}

type Props = {
  steps: SimulateurStep[]
  activeIndex: number
  maxEnabledIndex: number
  onChange: (nextIndex: number) => void
  /** Details / recap view: every step shows as completed (checkmarks, no active tab). */
  allStepsComplete?: boolean
}

function stepButtonClassName(active: boolean, done: boolean, disabled: boolean): string {
  const base =
    'm-0 inline-flex flex-col items-center justify-center shrink-0 min-w-[82px] sm:min-w-[102px] md:min-w-[112px] h-14 rounded-2xl border px-2 py-1.5 font-inherit text-inherit text-center transition-all duration-300 relative select-none backdrop-blur-md ' +
    'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:rgba(0,168,181,0.45)]'

  if (disabled) {
    return `${base} cursor-not-allowed opacity-35 bg-white/40 border-slate-200/40 text-vtf-navy/50`
  }

  if (active) {
    return `${base} cursor-pointer text-white border-transparent shadow-xl scale-[1.03]
      bg-[linear-gradient(135deg,var(--vtf-navy)_0%,var(--vtf-navy-light)_38%,var(--vtf-teal)_100%)]`
  }

  if (done) {
    return `${base} cursor-pointer border-[#dce8df] text-vtf-navy
      bg-[var(--vtf-green-soft)]
      hover:shadow-lg hover:scale-[1.02] hover:border-[#c8ddd0]`
  }

  return `${base} cursor-pointer border-slate-200/70 text-vtf-navy/75
    bg-[linear-gradient(135deg,rgba(255,255,255,0.88)_0%,rgba(252,249,246,0.95)_100%)]
    hover:bg-[linear-gradient(135deg,rgba(242,166,128,0.12)_0%,rgba(255,255,255,0.96)_100%)]
    hover:shadow-md hover:scale-[1.015] hover:text-vtf-navy`
}

export function SimulateurTabsList({
  steps,
  activeIndex,
  maxEnabledIndex,
  onChange,
  allStepsComplete = false,
}: Props) {
  const { t } = useTranslation()
  const navLabel = t('simulateur.tabsNavAria')
  const currentStep = steps[activeIndex]
  const mobileStepLabel = t('simulateur.tabsMobileLabel')
    .replace('{{label}}', currentStep?.label ?? '')
    .replace('{{current}}', String(activeIndex + 1))
    .replace('{{total}}', String(steps.length))

  return (
    <Box
      component="nav"
      aria-label={navLabel}
      className="rounded-3xl p-3"
      sx={{
        background: 'var(--vtf-green-soft)',
        border: '1px solid #dce8df',
        boxShadow: '0 14px 38px #00445a14',
        backdropFilter: 'blur(18px)',
      }}
    >
      {/* Mobile Vue (Active step only) */}
      <Box
        sx={{
          display: { xs: 'flex', md: 'none' },
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          py: 0.5,
        }}
      >
        <Box sx={{ color: 'var(--vtf-navy)', transform: 'scale(1.15)', mb: 0.5 }}>
          {currentStep?.icon}
        </Box>
        <Typography
          sx={{
            fontWeight: 900,
            color: 'var(--vtf-navy)',
            fontSize: { xs: 'var(--vtf-font-sm)', sm: 'var(--vtf-font-md)' },
            letterSpacing: '0.02em',
            lineHeight: 1.2,
            px: 1,
            textAlign: 'center',
          }}
        >
          {mobileStepLabel}
        </Typography>
      </Box>

      {/* Desktop Vue (List of tabs) */}
      <Box
        sx={{
          display: { xs: 'none', md: 'flex' },
          gap: 1.5,
          alignItems: 'stretch',
          overflowX: 'auto',
          scrollbarWidth: 'none',
          '&::-webkit-scrollbar': { display: 'none' },
        }}
      >
        {steps.map((s, i) => {
          const disabled = i > maxEnabledIndex
          const done = allStepsComplete || i < activeIndex
          const active = !allStepsComplete && i === activeIndex

          return (
            <button
              key={s.key}
              type="button"
              disabled={disabled}
              aria-current={active ? 'step' : undefined}
              onClick={() => !disabled && onChange(i)}
              className={`${stepButtonClassName(active, done, disabled)} font-(family-name:--sans)`}
            >
              {/* Active glow */}
              {active && (
                <Box
                  sx={{
                    position: 'absolute',
                    inset: 0,
                    borderRadius: 'inherit',
                    background:
                      'linear-gradient(135deg, rgba(255,255,255,0.14), rgba(255,255,255,0.02))',
                    pointerEvents: 'none',
                  }}
                />
              )}

              <Box className="flex flex-col items-center relative z-10">
                <Box
                  className={`transition-all duration-300 ${
                    active ? 'scale-95 text-white' : done ? 'scale-90 text-vtf-green' : 'scale-75'
                  }`}
                >
                  {s.icon}
                </Box>

                <Typography
                  component="span"
                  variant="caption"
                  className="uppercase tracking-[0.08em]"
                  sx={{
                    fontWeight: active ? 900 : 800,
                    fontSize: { xs: 8, sm: 'var(--vtf-font-xs)' },
                    mt: 0.15,
                    lineHeight: 1.15,
                    whiteSpace: 'normal',
                    color: active
                      ? '#FFFFFF'
                      : done
                      ? 'var(--vtf-navy)'
                      : 'rgba(0,68,90,0.75)',
                  }}
                >
                  {s.label}
                </Typography>
              </Box>

              {/* Completed badge */}
              {done && !active && (
                <Box
                  className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full flex items-center justify-center shadow-sm"
                  sx={{
                    background:
                      'linear-gradient(135deg, var(--vtf-green) 0%, #4CAF50 100%)',
                    border: '1px solid rgba(255,255,255,0.72)',
                  }}
                  aria-hidden
                >
                  <Box
                    component="span"
                    sx={{
                      fontSize: 'var(--vtf-font-sm)',
                      color: '#FFFFFF',
                      fontWeight: 900,
                    }}
                  >
                    ✓
                  </Box>
                </Box>
              )}
            </button>
          )
        })}
      </Box>
    </Box>
  )
}
