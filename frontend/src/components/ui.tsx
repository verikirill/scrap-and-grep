import clsx from 'clsx'
import { Schedule } from './icons'
import { animate, motion, useMotionValue, useTransform } from 'motion/react'
import { useEffect } from 'react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { formatNumber } from '../lib/format'
import { ripple } from './ripple'
import { DURATION, EASE, buttonClass } from './tokens'
import type { ButtonVariant } from './tokens'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: 'sm' | 'md'
  isBusy?: boolean
  icon?: ReactNode
}

export function Button({
  variant = 'secondary',
  size = 'md',
  isBusy = false,
  icon,
  className,
  children,
  disabled,
  onPointerDown,
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled || isBusy}
      aria-busy={isBusy || undefined}
      className={clsx(buttonClass(variant, size), icon && children && 'pl-4', className)}
      onPointerDown={(event) => {
        ripple(event)
        onPointerDown?.(event)
      }}
      {...rest}
    >
      {isBusy ? <Spinner /> : icon}
      {children}
    </button>
  )
}

/**
 * Material circular progress, indeterminate. Decorative unless a label is
 * given: a spinner inside a labelled button says nothing new.
 */
export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <span
      role={label ? 'status' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={clsx('inline-block size-4 shrink-0', className)}
    >
      <svg viewBox="0 0 24 24" className="size-full animate-spin [animation-duration:1.1s]">
        <circle
          cx="12"
          cy="12"
          r="9.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="44 60"
        />
      </svg>
    </span>
  )
}

type CardVariant = 'elevated' | 'filled' | 'outlined'

const CARD_STYLES: Record<CardVariant, string> = {
  elevated: 'bg-card shadow-elevation-1',
  filled: 'bg-surface-container-highest',
  outlined: 'border border-outline-variant bg-background',
}

/** Material 3 card: elevated by default, filled or outlined where it sits on a card. */
export function Card({
  className,
  children,
  variant = 'elevated',
}: {
  className?: string
  children: ReactNode
  variant?: CardVariant
}) {
  return (
    <div
      className={clsx(
        'rounded-3xl transition-shadow duration-300',
        CARD_STYLES[variant],
        className,
      )}
    >
      {children}
    </div>
  )
}

type ChipTone = 'neutral' | 'accent' | 'spark' | 'ok' | 'danger'

const CHIP_STYLES: Record<ChipTone, string> = {
  neutral: 'border border-outline-variant text-on-surface-variant',
  accent: 'bg-secondary-container text-on-secondary-container',
  spark: 'bg-spark-container text-on-spark-container',
  ok: 'bg-success-container text-on-success-container',
  danger: 'bg-error-container text-on-error-container',
}

/** Material 3 chip, not interactive: a label with a tone. */
export function Chip({
  tone = 'neutral',
  className,
  children,
  title,
}: {
  tone?: ChipTone
  className?: string
  children: ReactNode
  title?: string
}) {
  return (
    <span
      title={title}
      className={clsx(
        'inline-flex h-7 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium tracking-[0.01em]',
        CHIP_STYLES[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

/** Relevance as a thin bar plus the number: readable at a glance and exact. */
export function ScoreBar({ score, className }: { score: number; className?: string }) {
  return (
    <span className={clsx('inline-flex items-center gap-2', className)} title="Релевантность">
      <span className="relative h-1 w-14 overflow-hidden rounded-full bg-secondary-container">
        {/* scaleX, not width: a digest has dozens of these and width would relayout. */}
        <motion.span
          className="absolute inset-0 origin-left rounded-full bg-primary"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: score }}
          transition={{ duration: 0.6, ease: EASE }}
        />
      </span>
      <span className="tabular text-xs font-semibold text-foreground">{score.toFixed(2)}</span>
    </span>
  )
}

/** Number that counts to its new value instead of jumping. */
export function AnimatedNumber({ value, className }: { value: number; className?: string }) {
  const current = useMotionValue(value)
  const text = useTransform(current, (latest) => formatNumber(Math.round(latest)))
  useEffect(() => {
    const controls = animate(current, value, { duration: 0.7, ease: EASE })
    return () => controls.stop()
  }, [current, value])
  return <motion.span className={clsx('tabular', className)}>{text}</motion.span>
}

type FieldProps = {
  label: string
  hint?: string
  children: ReactNode
  className?: string
  /**
   * Render a group instead of a <label>. Needed when the content holds several
   * controls: a <label> forwards a click on its text to the first one inside,
   * which for a tag input is the "remove" button of the first tag.
   */
  isGroup?: boolean
}

export function Field({ label, hint, children, className, isGroup = false }: FieldProps) {
  const caption = (
    <span className="mb-1.5 flex items-baseline justify-between gap-3 px-1">
      <span className="text-[13px] font-medium text-on-surface-variant">{label}</span>
      {hint && <span className="text-xs text-outline">{hint}</span>}
    </span>
  )
  if (isGroup) {
    return (
      <div role="group" aria-label={label} className={clsx('block', className)}>
        {caption}
        {children}
      </div>
    )
  }
  return (
    <label className={clsx('block', className)}>
      {caption}
      {children}
    </label>
  )
}

/** Material 3 switch: the thumb grows when on, the track takes the primary colour. */
export function Toggle({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean
  onChange: (next: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={clsx(
        'relative flex h-8 w-[52px] shrink-0 items-center rounded-full border-2 transition-colors duration-200 disabled:opacity-40',
        checked
          ? 'justify-end border-primary bg-primary'
          : 'justify-start border-outline bg-surface-container-highest',
      )}
    >
      <motion.span
        layout
        transition={{ type: 'spring', stiffness: 700, damping: 38 }}
        className={clsx(
          'mx-1 rounded-full',
          checked ? 'size-6 bg-primary-foreground' : 'size-4 bg-outline',
        )}
      />
    </button>
  )
}

/** "4 мин чтения": how long the full article takes to read; nothing while it is not known. */
export function ReadingTime({ minutes }: { minutes: number | null | undefined }) {
  if (!minutes) return null
  return (
    <span
      className="inline-flex items-center gap-1 tabular-nums"
      title="Время чтения полной статьи"
    >
      <Schedule size={14} />
      {minutes} мин чтения
    </span>
  )
}

export function EmptyState({
  icon,
  title,
  children,
}: {
  icon: ReactNode
  title: string
  children?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: DURATION.long, ease: EASE }}
        className="mb-4 grid size-14 place-items-center rounded-2xl bg-secondary-container text-on-secondary-container"
      >
        {icon}
      </motion.div>
      <h3 className="text-base font-medium">{title}</h3>
      {children && <div className="mt-1.5 max-w-md text-sm text-muted-foreground">{children}</div>}
    </div>
  )
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null
  const message = error instanceof Error ? error.message : 'Неизвестная ошибка'
  return (
    <motion.p
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      role="alert"
      className="rounded-xl bg-error-container px-4 py-2.5 text-sm text-on-error-container"
    >
      {message}
    </motion.p>
  )
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-4 sm:mb-7">
      <div className="min-w-0">
        <h1 className="text-[28px] leading-9 font-normal tracking-tight text-on-surface">
          {title}
        </h1>
        {/* Two lines on a phone: the page itself should start on the first screen. */}
        {subtitle && (
          <p className="mt-1.5 line-clamp-2 max-w-2xl text-sm text-muted-foreground sm:line-clamp-none">
            {subtitle}
          </p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

/** Placeholder of a block while its data loads, in the shape of what comes. */
export function SkeletonBlock({ className }: { className?: string }) {
  return <div aria-hidden className={clsx('skeleton', className)} />
}
