import clsx from 'clsx'
import { animate, motion, useMotionValue, useTransform } from 'motion/react'
import { useEffect } from 'react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { formatNumber } from '../lib/format'
import { EASE, buttonClass } from './tokens'
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
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled || isBusy}
      aria-busy={isBusy || undefined}
      className={clsx(buttonClass(variant, size), className)}
      {...rest}
    >
      {isBusy ? <Spinner /> : icon}
      {children}
    </button>
  )
}

/** Decorative unless a label is given: a spinner inside a labelled button says nothing new. */
export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <span
      role={label ? 'status' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={clsx(
        'inline-block size-4 animate-spin rounded-full border-2 border-current border-r-transparent',
        className,
      )}
    />
  )
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={clsx('rounded-2xl border border-line bg-surface shadow-card', className)}>
      {children}
    </div>
  )
}

type ChipTone = 'neutral' | 'accent' | 'spark' | 'ok' | 'danger'

const CHIP_STYLES: Record<ChipTone, string> = {
  neutral: 'bg-sunken text-muted',
  accent: 'bg-accent-soft text-accent-text',
  spark: 'bg-spark-soft text-spark',
  ok: 'bg-ok-soft text-ok',
  danger: 'bg-danger-soft text-danger',
}

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
        'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium',
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
      <span className="relative h-1.5 w-14 overflow-hidden rounded-full bg-line">
        {/* scaleX, not width: a digest has dozens of these and width would relayout. */}
        <motion.span
          className="absolute inset-0 origin-left rounded-full bg-spark"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: score }}
          transition={{ duration: 0.6, ease: EASE }}
        />
      </span>
      <span className="tabular text-xs font-semibold text-text">{score.toFixed(2)}</span>
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
    <span className="mb-1.5 flex items-baseline justify-between gap-3">
      <span className="text-[13px] font-medium text-text">{label}</span>
      {hint && <span className="text-xs text-faint">{hint}</span>}
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
        'relative h-5 w-9 shrink-0 rounded-full transition-colors duration-200 disabled:opacity-50',
        checked ? 'bg-accent' : 'bg-line',
      )}
    >
      <motion.span
        layout
        transition={{ type: 'spring', stiffness: 600, damping: 34 }}
        className={clsx(
          'absolute top-0.5 size-4 rounded-full bg-white shadow',
          checked ? 'right-0.5' : 'left-0.5',
        )}
      />
    </button>
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
      <div className="mb-4 grid size-12 place-items-center rounded-2xl bg-sunken text-muted">
        {icon}
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <div className="mt-1.5 max-w-md text-sm text-muted">{children}</div>}
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
      className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger"
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
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}
