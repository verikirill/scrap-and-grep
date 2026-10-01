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

type Props = {
  digest: DigestSummary
  event: ProgressEvent | null
}

export function ProgressCard({ digest, event }: Props) {
  const stage = event?.stage ?? digest.stage
  const progress = Math.max(event?.progress ?? 0, digest.progress, 0.02)
  const current = stepIndex(stage)
  const isQueued = (event?.status ?? digest.status) === 'queued'
  const stageLabel = isQueued ? 'В очереди' : (STAGE_LABELS[stage ?? 'prepare'] ?? 'Работаем')
  const counter =
    event?.total && event.done !== null && event.done !== undefined
      ? `${event.done} из ${event.total}`
      : null
  const percent = Math.round(progress * 100)

  return (
    <Card className="overflow-hidden p-6">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <p className="text-xs font-medium tracking-wide text-on-primary-container uppercase">
            Собираем выпуск
          </p>
          {/* Announce stage changes, not every counter tick. */}
          <h2 className="mt-1 text-lg font-semibold">
            <span aria-live="polite">{stageLabel}</span>
            {counter && (
              <span className="tabular ml-2 text-sm font-normal text-muted-foreground">
                {counter}
              </span>
            )}
          </h2>
        </div>
        <span className="tabular text-2xl font-semibold text-muted-foreground" aria-hidden>
          {percent}%
        </span>
      </div>

      <div
        role="progressbar"
        aria-label="Готовность выпуска"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="mt-5 h-1.5 overflow-hidden rounded-full bg-surface-container"
      >
        <motion.div
          className="h-full origin-left rounded-full bg-primary"
          initial={false}
          animate={{ scaleX: progress }}
          transition={{ type: 'spring', stiffness: 70, damping: 20 }}
        />
      </div>

      <ol className="mt-6 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-6">
        {STEPS.map((step, index) => {
          const isDone = index < current
          const isActive = index === current && !isQueued
          return (
            <li
              key={step}
              aria-current={isActive ? 'step' : undefined}
              className="flex items-center gap-2.5"
            >
              <span
                className={clsx(
                  'relative grid size-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold transition-colors duration-300',
                  isDone && 'bg-primary text-white dark:text-[#0b0f17]',
                  isActive && 'bg-primary-container text-on-primary-container',
                  !isDone && !isActive && 'bg-surface-container text-outline',
                )}
              >
                {isActive && (
                  <motion.span
                    className="absolute inset-0 rounded-full border border-primary"
                    animate={{ scale: [1, 1.5], opacity: [0.7, 0] }}
                    transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }}
                  />
                )}
                {isDone ? <Check size={13} strokeWidth={3} aria-label="готово" /> : index + 1}
              </span>
              <span
                className={clsx(
                  'text-xs leading-tight transition-colors duration-300',
                  isDone || isActive ? 'text-foreground' : 'text-outline',
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
