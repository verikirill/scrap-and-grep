import { motion } from 'motion/react'
import type { CSSProperties, ReactNode } from 'react'
import { cn } from '../lib/utils'
import { Mascot } from './Mascot'

/** One shimmering block in the shape of what comes; decoration, the region speaks. */
export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <div
      aria-hidden
      className={cn('skeleton skeleton--shimmer rounded-xl', className)}
      style={style}
    />
  )
}

/**
 * A place that is loading: announced once as a busy status with its label,
 * the skeletons inside are only the picture of what comes.
 */
export function Loading({
  label,
  className,
  children,
}: {
  label: string
  className?: string
  children: ReactNode
}) {
  return (
    <div role="status" aria-busy="true" aria-label={label} className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  )
}

/** Lines of text: the last one shorter, as a paragraph ends. */
export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div aria-hidden className={cn('space-y-2', className)}>
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton
          key={index}
          className={cn('h-3.5', index === lines - 1 && lines > 1 ? 'w-2/3' : 'w-full')}
        />
      ))}
    </div>
  )
}

/**
 * A card of a list: a mark, a title, two lines and a row of chips. Used for
 * digest entries, feed cards, posts and the history.
 */
export function SkeletonCard({
  className,
  hasMark = true,
}: {
  className?: string
  hasMark?: boolean
}) {
  return (
    <div aria-hidden className={cn('rounded-3xl bg-surface p-5 shadow-surface', className)}>
      <div className="flex items-start gap-3">
        {hasMark && <Skeleton className="size-10 shrink-0 rounded-full" />}
        <div className="min-w-0 flex-1 space-y-2.5">
          <Skeleton className="h-4 w-3/4" />
          <SkeletonText lines={2} />
          <div className="flex gap-2 pt-1">
            <Skeleton className="h-6 w-20 rounded-full" />
            <Skeleton className="h-6 w-14 rounded-full" />
            <Skeleton className="h-6 w-24 rounded-full" />
          </div>
        </div>
      </div>
    </div>
  )
}

/** Cards one under another, as a list arrives. */
export function SkeletonList({
  count = 3,
  className,
  hasMark,
}: {
  count?: number
  className?: string
  hasMark?: boolean
}) {
  return (
    <div aria-hidden className={cn('space-y-3', className)}>
      {Array.from({ length: count }, (_, index) => (
        <SkeletonCard key={index} hasMark={hasMark} />
      ))}
    </div>
  )
}

/** Rows of a table: a header line and rows of cells. */
export function SkeletonTable({ rows = 6, className }: { rows?: number; className?: string }) {
  return (
    <div aria-hidden className={cn('rounded-3xl bg-surface p-4 shadow-surface', className)}>
      <Skeleton className="mb-4 h-4 w-40" />
      <div className="space-y-3">
        {Array.from({ length: rows }, (_, index) => (
          <div key={index} className="flex items-center gap-3">
            <Skeleton className="size-8 shrink-0 rounded-full" />
            <Skeleton className="h-3.5 flex-1" />
            <Skeleton className="hidden h-3.5 w-24 sm:block" />
            <Skeleton className="h-6 w-16 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  )
}

/** A chart: its title and bars of different heights rising from the axis. */
export function SkeletonChart({ className }: { className?: string }) {
  const bars = [40, 65, 50, 80, 58, 92, 70, 48, 76, 60]
  return (
    <div aria-hidden className={cn('rounded-3xl bg-surface p-5 shadow-surface', className)}>
      <Skeleton className="h-4 w-44" />
      <div className="mt-6 flex h-40 items-end gap-2">
        {bars.map((height, index) => (
          <Skeleton key={index} className="flex-1 rounded-md" style={{ height: `${height}%` }} />
        ))}
      </div>
    </div>
  )
}

/** The first frame of any page: its title pill, a line under it and two cards. */
export function PageSkeleton({ label = 'Открываем раздел' }: { label?: string }) {
  return (
    <Loading label={label} className="space-y-5">
      <Skeleton className="h-11 w-60 rounded-[1.25rem]" />
      <Skeleton className="h-4 w-full max-w-xl" />
      <SkeletonCard className="h-44" />
      <SkeletonList count={2} />
    </Loading>
  )
}

/**
 * Where nothing has a shape yet (a check of the session, an answer being
 * written): the cat looks through its magnifier, with what it is doing.
 */
export function MascotLoader({
  label,
  hint,
  size,
  isInline = false,
  className,
}: {
  label: string
  hint?: ReactNode
  size?: number
  /** In a line, as an answer being written in a chat; stacked and centred otherwise. */
  isInline?: boolean
  className?: string
}) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label={label}
      className={cn(
        isInline ? 'flex items-center gap-2' : 'flex flex-col items-center gap-2 py-6 text-center',
        className,
      )}
    >
      <Mascot pose="searching" size={size ?? (isInline ? 44 : 96)} />
      <p className={cn('text-sm', isInline ? 'text-muted' : 'font-semibold text-foreground')}>
        {label}
        <Dots />
      </p>
      {hint && <div className="max-w-sm text-xs text-muted">{hint}</div>}
    </div>
  )
}

/** Three dots that fill one after another: the wait is going on. */
function Dots() {
  return (
    <span aria-hidden className="ml-0.5 inline-flex gap-0.5">
      {[0, 1, 2].map((index) => (
        <motion.span
          key={index}
          className="inline-block size-1 rounded-full bg-current"
          animate={{ opacity: [0.2, 1, 0.2] }}
          transition={{ duration: 1.2, delay: index * 0.2, repeat: Infinity }}
        />
      ))}
    </span>
  )
}
