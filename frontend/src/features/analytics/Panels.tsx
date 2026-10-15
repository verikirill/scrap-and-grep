import clsx from 'clsx'
import { useId } from 'react'
import type { ReactNode } from 'react'
import {
  ArrowDown,
  ArrowUp,
  ExternalLink,
  Eye,
  Info,
  Minus,
  ThumbsUp,
  Users,
} from '../../components/icons'
import { Card, Chip } from '../../components/ui'
import type { Analytics, AnalyticsTotals, Rates } from '../../lib/api'
import { formatNumber } from '../../lib/format'
import { formatPercent, formatPoints } from '../../lib/analyticsFormat'
import { DayBars, RateBar, RateLines } from './charts'
import type { BarTone } from './charts'

/** The topic of a block: its icon in a soft tinted square, as the other pages head their cards. */
function TopicTile({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      aria-hidden
      className={clsx(
        'grid shrink-0 place-items-center bg-accent-soft text-accent-soft-foreground',
        className,
      )}
    >
      {children}
    </span>
  )
}

/** A remark at the foot of a card: how a number is counted or how to read it. */
function Note({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-1.5 text-xs text-muted">
      <Info size={14} aria-hidden className="mt-px shrink-0" />
      <span>{children}</span>
    </p>
  )
}

/**
 * A section of the page: an icon tile, the title and one line of what the
 * section shows, then its body; a remark, if any, sits at the foot.
 */
export function Panel({
  icon,
  title,
  subtitle,
  note,
  children,
  className,
}: {
  icon: ReactNode
  title: string
  subtitle?: ReactNode
  note?: ReactNode
  children: ReactNode
  className?: string
}) {
  const id = useId()
  return (
    <Card className={clsx('flex min-w-0 flex-col p-5 sm:p-6', className)}>
      <section aria-labelledby={id} className="flex flex-1 flex-col">
        <div className="flex items-start gap-3">
          <TopicTile className="size-10 rounded-2xl">{icon}</TopicTile>
          <div className="min-w-0">
            <h2 id={id} className="font-semibold">
              {title}
            </h2>
            {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
          </div>
        </div>
        <div className="mt-5 flex-1">{children}</div>
        {note && (
          <div className="mt-5">
            <Note>{note}</Note>
          </div>
        )}
      </section>
    </Card>
  )
}

/** How far a figure moved since the previous period of the same length, as a soft chip. */
function Delta({ now, before, isRate }: { now: number; before: number; isRate: boolean }) {
  // The arrow follows what is printed: a change that rounds to zero is level.
  const change = isRate ? Math.round((now - before) * 1000) / 1000 : now - before
  const Icon = change > 0 ? ArrowUp : change < 0 ? ArrowDown : Minus
  const text = isRate
    ? formatPoints(change)
    : before
      ? `${change > 0 ? '+' : change < 0 ? '−' : ''}${formatPercent(Math.abs(change) / before)}`
      : 'было 0'
  // Every figure here is better higher: growth is good news, a fall is not.
  const tone = change > 0 ? 'ok' : change < 0 ? 'danger' : 'neutral'
  return (
    <Chip tone={tone} className="text-xs tabular-nums">
      <Icon size={12} aria-hidden />
      {text}
    </Chip>
  )
}

function Figure({
  icon,
  label,
  value,
  now,
  before,
  days,
  isRate = false,
}: {
  icon: ReactNode
  label: string
  value: string
  now: number
  before: number | undefined
  days: number
  isRate?: boolean
}) {
  const id = useId()
  return (
    <Card className="flex min-w-0 flex-col p-4 sm:p-5">
      <div role="group" aria-labelledby={id} className="flex flex-1 flex-col">
        <div className="flex items-start gap-2.5">
          <TopicTile className="size-8 rounded-xl">{icon}</TopicTile>
          <p id={id} className="min-w-0 self-center text-xs leading-snug text-muted">
            {label}
          </p>
        </div>
        <p className="mt-3 text-2xl font-semibold tabular-nums sm:text-[28px] sm:leading-9">
          {value}
        </p>
        {before !== undefined && (
          <p className="mt-auto flex flex-wrap items-center gap-x-1.5 gap-y-1 pt-2">
            <Delta now={now} before={before} isRate={isRate} />
            <span className="text-[11px] text-muted">к предыдущим {days} дням</span>
          </p>
        )}
      </div>
    </Card>
  )
}

export function Figures({
  totals,
  previous,
  days,
}: {
  totals: AnalyticsTotals
  previous: AnalyticsTotals | null
  /** The length of the period, the previous one being as long. */
  days: number
}) {
  // A rate of a period when nothing was seen is no rate at all, not 0 %.
  const rateBefore = (value: number | undefined) => (previous?.seen ? value : undefined)
  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
      <Figure
        icon={<Users size={16} />}
        label="Читатели"
        value={formatNumber(totals.readers)}
        now={totals.readers}
        before={previous?.readers}
        days={days}
      />
      <Figure
        icon={<Eye size={16} />}
        label="Показано статей"
        value={formatNumber(totals.seen)}
        now={totals.seen}
        before={previous?.seen}
        days={days}
      />
      <Figure
        icon={<ExternalLink size={16} />}
        label="Доля открытий"
        value={formatPercent(totals.ctr)}
        now={totals.ctr}
        before={rateBefore(previous?.ctr)}
        days={days}
        isRate
      />
      <Figure
        icon={<ThumbsUp size={16} />}
        label="Реакции «больше» и сохранения"
        value={formatPercent(totals.like_rate)}
        now={totals.like_rate}
        before={rateBefore(previous?.like_rate)}
        days={days}
        isRate
      />
    </div>
  )
}

export function Activity({ totals }: { totals: AnalyticsTotals }) {
  const decided = totals.suggestions_accepted + totals.suggestions_dismissed
  const items = [
    ['Показано в ленте', formatNumber(totals.served), 'статей'],
    ['Собрано выпусков', formatNumber(totals.digests_built), ''],
    ['Открыто выпусков', formatNumber(totals.digests_opened), ''],
    ['Запросов через MCP', formatNumber(totals.mcp_calls), ''],
    [
      'Предложений подстройки',
      decided ? `${totals.suggestions_accepted} из ${decided}` : '0',
      'принято',
    ],
  ] as const
  return (
    <dl className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-5">
      {items.map(([label, value, unit], index) => (
        <div
          key={label}
          className={clsx(
            'min-w-0 rounded-2xl bg-surface-secondary px-4 py-3',
            // Five on a phone: the last one takes the whole line, not half of it.
            index === items.length - 1 && 'col-span-2 sm:col-span-1',
          )}
        >
          <dt className="text-xs leading-snug text-muted">{label}</dt>
          <dd className="mt-1 text-lg font-semibold tabular-nums">
            {value} {unit && <span className="text-xs font-normal text-muted">{unit}</span>}
          </dd>
        </div>
      ))}
    </dl>
  )
}

/** Seen, then opened, then marked: each step as a share of the first. */
export function Funnel({ totals }: { totals: Rates }) {
  const steps: { label: string; value: number; share: number; tone: BarTone }[] = [
    { label: 'Показано', value: totals.seen, share: 1, tone: 'accent' },
    { label: 'Открыто', value: totals.opened, share: totals.ctr, tone: 'accent' },
    {
      label: '«Больше такого» и сохранения',
      value: totals.liked,
      share: totals.like_rate,
      tone: 'warning',
    },
    {
      label: '«Меньше такого» и скрытия',
      value: totals.rejected,
      share: totals.reject_rate,
      tone: 'danger',
    },
  ]
  return (
    <div className="@container">
      {/* A narrow card puts each bar under its step; a wide one gives the bars a column. */}
      <ul className="divide-y divide-separator">
        {steps.map((step) => (
          <li
            key={step.label}
            className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 py-3 first:pt-0 last:pb-0 @md:grid-cols-[minmax(0,10rem)_minmax(0,1fr)_7rem]"
          >
            <span className="col-start-1 row-start-1 text-sm leading-snug">{step.label}</span>
            <div aria-hidden className="col-[1/-1] row-start-2 @md:col-[2/3] @md:row-start-1">
              <RateBar rate={step.share} scale={1} tone={step.tone} />
            </div>
            <span className="col-start-2 row-start-1 text-right text-sm font-semibold tabular-nums @md:col-start-3">
              {formatNumber(step.value)}
              <span className="ml-1.5 text-xs font-normal text-muted">
                {formatPercent(step.share)}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Days({ daily }: { daily: Analytics['daily'] }) {
  const days = daily.map((day) => day.day)
  return (
    <div className="grid gap-8 lg:grid-cols-2 lg:gap-6">
      <DayBars days={days} values={daily.map((day) => day.seen)} label="Показы статей по дням" />
      <RateLines
        days={days}
        label="Доля открытий и отметок"
        note="Дни, где меньше 30 показов, пропущены."
        series={[
          {
            label: 'открывают',
            tone: 'text-accent',
            values: daily.map((day) => (day.enough ? day.ctr : null)),
          },
          {
            label: '«больше такого» или сохранили',
            tone: 'text-warning',
            values: daily.map((day) => (day.enough ? day.like_rate : null)),
          },
        ]}
      />
    </div>
  )
}
