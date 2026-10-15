import clsx from 'clsx'
import { Check } from '../../components/icons'
import { motion } from 'motion/react'
import { Card } from '../../components/ui'
import type { DigestSummary, ProgressEvent } from '../../lib/api'
import { STAGE_LABELS } from '../../lib/format'

// Pipeline stages as the reader sees them; "cluster" and "persist" are folded
// into their neighbours because they take a fraction of a second.
const STEPS = ['prepare', 'retrieve', 'grade', 'select', 'summarize', 'compose'] as const

// One word per step: six of them share a row, and the heading above already
// says in full what is going on.
const STEP_NAMES: Record<(typeof STEPS)[number], string> = {
  prepare: 'Подготовка',
  retrieve: 'Поиск',
  grade: 'Оценка',
  select: 'Отбор',
  summarize: 'Выжимки',
  compose: 'Сборка',
}

function stepIndex(stage: string | null | undefined): number {
  if (stage === 'persist' || stage === 'done') return STEPS.length
  const index = STEPS.indexOf(stage as (typeof STEPS)[number])
  return index === -1 ? 0 : index
}

type TrackState = 'queued' | 'running' | 'saving'

/** The marker rests in the queue, glows while the steps run and settles once they are all done. */
function trackStateOf(isQueued: boolean, current: number): TrackState {
  if (isQueued) return 'queued'
  return current >= STEPS.length ? 'saving' : 'running'
}

type Props = {
  digest: DigestSummary
  event: ProgressEvent | null
}

export function ProgressCard({ digest, event }: Props) {
  const stage = event?.stage ?? digest.stage
  const progress = Math.max(event?.progress ?? 0, digest.progress, 0.02)
  const current = stepIndex(stage)
  const isQueued = (event?.status ?? digest.status) === 'queued'
  const stageLabel = isQueued ? 'В очереди' : (STAGE_LABELS[stage ?? 'prepare'] ?? 'Обработка')
  const counter =
    event?.total && event.done !== null && event.done !== undefined
      ? `${event.done} из ${event.total}`
      : null
  const percent = Math.round(progress * 100)
  const trackState = trackStateOf(isQueued, current)

  return (
    <Card className="overflow-hidden p-6">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <p className="text-xs font-medium tracking-wide text-accent-soft-foreground uppercase">
            Собираем выпуск
          </p>
          {/* Announce stage changes, not every counter tick. */}
          <h2 className="mt-1 text-lg font-semibold">
            <span aria-live="polite">{stageLabel}</span>
            {counter && (
              <span className="tabular ml-2 text-sm font-normal text-muted">{counter}</span>
            )}
          </h2>
        </div>
        <span className="tabular text-2xl font-semibold text-muted" aria-hidden>
          {percent}%
        </span>
      </div>

      {/* The track: a glowing marker rides the front of the bar as the issue gets ready. */}
      <div className="relative mt-5">
        <div
          role="progressbar"
          aria-label="Готовность выпуска"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          className="h-2.5 overflow-hidden rounded-full bg-surface-secondary"
        >
          <motion.div
            className="progress-fill h-full origin-left rounded-full"
            initial={false}
            animate={{ scaleX: progress }}
            transition={{ type: 'spring', stiffness: 60, damping: 18 }}
          />
        </div>
        {/* A full-width layer moved by a share of its own width: the marker
            travels with the fill on the compositor, without layout. */}
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-1/2 h-0"
          initial={false}
          animate={{ x: `${progress * 100}%` }}
          transition={{ type: 'spring', stiffness: 60, damping: 18 }}
        >
          <span
            data-state={trackState}
            className="progress-marker absolute top-0 left-0 grid size-4 -translate-x-1/2 -translate-y-1/2 place-items-center"
          >
            {trackState === 'running' && (
              <motion.span
                className="absolute inset-0 rounded-full bg-accent"
                animate={{ scale: [1, 2.4], opacity: [0.45, 0] }}
                transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut' }}
              />
            )}
            <span className="progress-marker__dot size-full rounded-full" />
          </span>
        </motion.div>
      </div>

      <ol className="mt-4 grid grid-cols-6 gap-x-1 sm:mx-2">
        {STEPS.map((step, index) => {
          const isDone = index < current
          const isActive = index === current && !isQueued
          return (
            <li
              key={step}
              aria-current={isActive ? 'step' : undefined}
              className="flex flex-col items-center gap-1.5 text-center"
            >
              <span
                className={clsx(
                  'relative grid size-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold transition-colors duration-300',
                  isDone && 'bg-accent text-white dark:text-[#0b0f17]',
                  isActive && 'bg-accent-soft text-accent-soft-foreground',
                  !isDone && !isActive && 'bg-surface-secondary text-muted',
                )}
              >
                {isActive && (
                  <motion.span
                    className="absolute inset-0 rounded-full border border-accent"
                    animate={{ scale: [1, 1.5], opacity: [0.7, 0] }}
                    transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }}
                  />
                )}
                {isDone ? <Check size={13} strokeWidth={3} aria-label="готово" /> : index + 1}
              </span>
              <span
                className={clsx(
                  'text-xs leading-tight transition-colors duration-300',
                  isDone || isActive ? 'text-foreground' : 'text-muted',
                  isActive ? 'font-semibold whitespace-nowrap' : 'max-sm:sr-only',
                )}
              >
                {STEP_NAMES[step]}
              </span>
            </li>
          )
        })}
      </ol>
    </Card>
  )
}
