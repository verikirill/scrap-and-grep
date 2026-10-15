import clsx from 'clsx'
import { motion } from 'motion/react'
import type { ReactNode } from 'react'
import type { IconComponent } from '../../components/icons'
import { cn } from '../../lib/utils'
import { rise } from './motion'

/**
 * The picture of a section: a small piece of its screen drawn with the app's
 * own cards and chips. Decorative: the text beside it says the same in words.
 */
export function PreviewFrame({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      aria-hidden
      className={clsx(
        'pointer-events-none space-y-2.5 rounded-3xl bg-surface-secondary p-3 select-none sm:p-4',
        className,
      )}
    >
      {children}
    </div>
  )
}

/** A white card inside the picture; `index` sets its turn to rise. */
export function Mini({
  index,
  className,
  children,
}: {
  index: number
  className?: string
  children: ReactNode
}) {
  return (
    <motion.div
      {...rise(index)}
      className={cn('rounded-2xl bg-surface p-3 shadow-surface', className)}
    >
      {children}
    </motion.div>
  )
}

/** A line of text drawn as a soft bar, where the words themselves do not matter. */
export function Bar({ className }: { className?: string }) {
  return <span className={clsx('block h-2 rounded-full bg-default', className)} />
}

/** A section's icon in a tinted square, as on empty places of the app. */
export function Tile({
  icon: Icon,
  size = 32,
  className,
}: {
  icon: IconComponent
  size?: number
  className?: string
}) {
  return (
    <span
      className={cn('icon-tile grid shrink-0 place-items-center rounded-[10px]', className)}
      style={{ width: size, height: size }}
    >
      <Icon size={Math.round(size * 0.5)} />
    </span>
  )
}

/** A small label as the app's chips are: soft tone, rounded. */
export function Pill({
  tone = 'neutral',
  className,
  children,
}: {
  tone?: 'neutral' | 'accent' | 'ok' | 'danger' | 'warning'
  className?: string
  children: ReactNode
}) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] leading-5 font-medium whitespace-nowrap',
        tone === 'neutral' && 'bg-default text-muted',
        tone === 'accent' && 'bg-accent-soft text-accent-soft-foreground',
        tone === 'ok' && 'bg-success-soft text-success-soft-foreground',
        tone === 'danger' && 'bg-danger-soft text-danger-soft-foreground',
        tone === 'warning' && 'bg-warning-soft text-warning-soft-foreground',
        className,
      )}
    >
      {children}
    </span>
  )
}
