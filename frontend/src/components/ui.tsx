import clsx from 'clsx'
import { ArrowRight, Help, Schedule, TriangleAlert } from './icons'
import { animate, motion, useMotionValue, useTransform } from 'motion/react'
import { useEffect } from 'react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { formatNumber } from '../lib/format'
import { useEntranceDelay } from './entrance'
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
      {/* The call to action points where it leads. */}
      {variant === 'cta' && <ArrowRight size={16} aria-hidden className="cta__arrow" />}
    </button>
  )
}

/**
 * Circular progress, indeterminate, in the current colour. Decorative unless a label is
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

// HeroUI surfaces: a raised card, a filled block, or an outline where it sits on a card.
const CARD_STYLES: Record<CardVariant, string> = {
  elevated: 'bg-surface shadow-surface',
  filled: 'bg-surface-secondary',
  outlined: 'border border-border bg-transparent',
}

/** A card: raised by default, filled or outlined where it sits on another card. */
export function Card({
  className,
  children,
  variant = 'elevated',
}: {
  className?: string
  children: ReactNode
  variant?: CardVariant
}) {
  // On a fresh page cards rise one after another, as the comparison shows its blocks.
  const delay = useEntranceDelay()
  return (
    <motion.div
      initial={delay === null ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: EASE, delay: delay ?? 0 }}
      className={clsx('rounded-3xl', CARD_STYLES[variant], className)}
    >
      {children}
    </motion.div>
  )
}

type ChipTone = 'neutral' | 'accent' | 'spark' | 'ok' | 'danger' | 'alarm'

// HeroUI chips: soft tones, and solid red for what needs acting on first.
const CHIP_STYLES: Record<ChipTone, string> = {
  neutral: 'chip--default chip--soft text-muted',
  accent: 'chip--accent chip--soft',
  spark: 'chip--warning chip--soft',
  ok: 'chip--success chip--soft',
  danger: 'chip--danger chip--soft',
  alarm: 'chip--danger chip--primary font-semibold',
}

/**
 * A chip, not interactive: a label with a tone: a label with a tone. A chip with a hint
 * carries a question mark, so the reader knows hovering it tells more.
 */
export function Chip({
  tone = 'neutral',
  className,
  children,
  title,
  hint,
}: {
  tone?: ChipTone
  className?: string
  children: ReactNode
  title?: string
  /** What the chip means, shown on hover; the chip then carries a «?». */
  hint?: string
}) {
  return (
    <span
      title={hint ?? title}
      className={clsx(
        'chip gap-1 px-2.5 py-1',
        CHIP_STYLES[tone],
        hint && 'cursor-help',
        className,
      )}
    >
      {children}
      {hint && <Help size={14} aria-hidden className="-mr-1 opacity-70" />}
    </span>
  )
}

/** Relevance as a thin bar plus the number: readable at a glance and exact. */
export function ScoreBar({ score, className }: { score: number; className?: string }) {
  return (
    <span className={clsx('inline-flex items-center gap-2', className)} title="Релевантность">
      <span className="relative h-1 w-14 overflow-hidden rounded-full bg-default">
        {/* scaleX, not width: a digest has dozens of these and width would relayout. */}
        <motion.span
          className="absolute inset-0 origin-left rounded-full bg-accent"
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
      <span className="text-[13px] font-medium text-muted">{label}</span>
      {hint && <span className="text-xs text-muted">{hint}</span>}
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

/** A switch in HeroUI's shape: a pill track, the thumb slides to the on side. */
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
        'relative flex h-6 w-10 shrink-0 items-center rounded-full transition-colors duration-200 disabled:opacity-50',
        checked ? 'justify-end bg-accent' : 'justify-start bg-default hover:bg-default-hover',
      )}
    >
      <motion.span
        layout
        transition={{ type: 'spring', stiffness: 700, damping: 38 }}
        className="mx-0.5 size-5 rounded-full bg-white shadow-sm"
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

/**
 * The topic of an empty or failed place: its icon in a soft tinted tile.
 * Decoration: the title next to it says the same in words.
 */
export function IconTile({
  icon,
  tone = 'accent',
  className,
}: {
  icon: ReactNode
  tone?: 'accent' | 'danger'
  className?: string
}) {
  return (
    <motion.div
      aria-hidden
      data-tone={tone}
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: DURATION.long, ease: EASE }}
      className={clsx(
        'icon-tile grid size-16 shrink-0 place-items-center [&>svg]:size-7',
        tone === 'danger' && 'icon-tile--danger',
        className,
      )}
    >
      {icon}
    </motion.div>
  )
}

/** An empty place: its topic, what is missing and the step that fills it. */
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  /** The topic, shown in a tinted tile above the title. */
  icon: ReactNode
  title: string
  children?: ReactNode
  /** The step that fills the empty place, as a button under the text. */
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <IconTile icon={icon} className="mb-4" />
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <div className="mt-1.5 max-w-xl text-sm text-muted">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

/**
 * A part that failed to load: a warning sign, what went wrong in plain words
 * and a way out. The whole block is the alert, so its title is read too.
 */
export function ErrorState({
  title,
  error,
  children,
  action,
  className,
}: {
  title: string
  /** The failure; its message is shown under the title. */
  error?: unknown
  children?: ReactNode
  action?: ReactNode
  className?: string
}) {
  const message = error ? (error instanceof Error ? error.message : 'Неизвестная ошибка') : null
  return (
    <div
      role="alert"
      className={clsx('flex flex-col items-center px-6 py-10 text-center', className)}
    >
      <IconTile icon={<TriangleAlert />} tone="danger" className="mb-4" />
      <h3 className="text-base font-semibold">{title}</h3>
      {message && <p className="mt-1.5 max-w-md text-sm text-muted">{message}</p>}
      {children && <div className="mt-1.5 max-w-md text-sm text-muted">{children}</div>}
      {action && <div className="mt-4 flex flex-wrap justify-center gap-2">{action}</div>}
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
      className="rounded-2xl bg-danger-soft px-4 py-2.5 text-sm text-danger-soft-foreground"
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
        <h1 className="title-pill text-[22px] leading-8 sm:text-[26px] sm:leading-9">{title}</h1>
        {/* Two lines on a phone: the page itself should start on the first screen. */}
        {subtitle && (
          <p className="mt-3 line-clamp-2 max-w-2xl text-sm text-muted sm:line-clamp-none">
            {subtitle}
          </p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}
