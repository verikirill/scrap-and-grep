import clsx from 'clsx'
import { motion } from 'motion/react'
import { EASE } from '../../components/tokens'
import type { DigestItem } from '../../lib/api'
import { timelineOf } from '../../lib/risk'
import type { TimelineEvent } from '../../lib/risk'

// Years matter here: a flaw can be eight years old by the time it makes the news.
const DAY = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: 'UTC',
})

const DOT_TONES: Record<TimelineEvent['tone'], string> = {
  neutral: 'bg-muted',
  warning: 'bg-warning',
  danger: 'bg-danger',
  accent: 'bg-accent',
}

/**
 * A vulnerability's life in dated steps: published, exploited, in CISA KEV,
 * CISA's deadline, and the news that brought it into the issue. The line
 * draws itself, then the steps light up in order.
 */
export function CveTimeline({ item }: { item: DigestItem }) {
  const events = timelineOf(item)
  if (events.length === 0) return null
  return (
    <div className="mt-2.5 overflow-x-auto rounded-xl bg-surface-secondary px-3 pt-3 pb-2.5">
      <ol className="relative flex min-w-max gap-0">
        <motion.span
          aria-hidden
          className="absolute top-[5px] right-6 left-6 h-0.5 origin-left rounded-full bg-separator"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.6, ease: EASE }}
        />
        {events.map((event, index) => (
          <motion.li
            key={`${event.label}-${event.date}`}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: 0.3 + index * 0.12 }}
            className="relative flex w-32 flex-col items-center text-center"
          >
            <span
              className={clsx(
                'relative size-3 rounded-full ring-4 ring-surface-secondary',
                DOT_TONES[event.tone],
              )}
            />
            <span className="mt-1.5 text-[11px] font-semibold text-foreground tabular-nums">
              {DAY.format(new Date(event.date))}
            </span>
            <span className="text-[11px] leading-tight text-muted">{event.label}</span>
          </motion.li>
        ))}
      </ol>
    </div>
  )
}
