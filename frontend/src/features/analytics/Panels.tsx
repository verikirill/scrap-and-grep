import clsx from 'clsx'
import type { ReactNode } from 'react'
import { ArrowDown, ArrowUp, Minus } from '../../components/icons'
import { Card, Chip } from '../../components/ui'
import type { Analytics, AnalyticsTotals, RankerRun, Rates } from '../../lib/api'
import { CATEGORY_LABELS, formatDateTime, formatNumber, plural } from '../../lib/format'
import { DayBars, RateBar, RateLines, formatPercent, formatPoints } from './charts'

export function Panel({
  title,
  hint,
  children,
  className,
}: {
  title: string
  hint?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <Card className={clsx('min-w-0 p-5 sm:p-6', className)}>
      <h2 className="text-base font-medium">{title}</h2>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      <div className="mt-4">{children}</div>
    </Card>
  )
}

/** A rate and how far it moved since the previous period of the same length. */
function Delta({ now, before, isRate }: { now: number; before: number; isRate: boolean }) {
  // The arrow follows what is printed: a change that rounds to zero is level.
  const change = isRate ? Math.round((now - before) * 1000) / 1000 : now - before
  const Icon = change > 0 ? ArrowUp : change < 0 ? ArrowDown : Minus
  const text = isRate
    ? formatPoints(change)
    : before
      ? `${change > 0 ? '+' : change < 0 ? '−' : ''}${formatPercent(Math.abs(change) / before)}`
      : 'было 0'
  return (
    <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground tabular-nums">
      <Icon size={13} />
      {text}
    </span>
  )
}

function Figure({
  label,
  value,
  now,
  before,
  isRate = false,
}: {
  label: string
  value: string
  now: number
  before: number | undefined
  isRate?: boolean
}) {
  return (
    <Card className="p-4 sm:p-5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {before !== undefined && <Delta now={now} before={before} isRate={isRate} />}
    </Card>
  )
}

export function Figures({
  totals,
  previous,
}: {
  totals: AnalyticsTotals
  previous: AnalyticsTotals | null
}) {
  // A rate of a period when nothing was seen is no rate at all, not 0 %.
  const rateBefore = (value: number | undefined) => (previous?.seen ? value : undefined)
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Figure
        label="Читатели"
        value={formatNumber(totals.readers)}
        now={totals.readers}
        before={previous?.readers}
      />
      <Figure
        label="Показано статей"
        value={formatNumber(totals.seen)}
        now={totals.seen}
        before={previous?.seen}
      />
      <Figure
        label="Доля открытий"
        value={formatPercent(totals.ctr)}
        now={totals.ctr}
        before={rateBefore(previous?.ctr)}
        isRate
      />
      <Figure
        label="Реакции «больше» и сохранения"
        value={formatPercent(totals.like_rate)}
        now={totals.like_rate}
        before={rateBefore(previous?.like_rate)}
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
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 xl:grid-cols-5">
      {items.map(([label, value, unit]) => (
        <div key={label}>
          <dt className="text-xs text-muted-foreground">{label}</dt>
          <dd className="text-base font-medium tabular-nums">
            {value} {unit && <span className="text-xs font-normal text-outline">{unit}</span>}
          </dd>
        </div>
      ))}
    </dl>
  )
}

/** Seen, then opened, then marked: each step as a share of the first. */
export function Funnel({ totals }: { totals: Rates }) {
  const steps = [
    { label: 'Показано', value: totals.seen, share: 1, tone: 'text-primary' },
    { label: 'Открыто', value: totals.opened, share: totals.ctr, tone: 'text-primary' },
    {
      label: '«Больше такого» и сохранения',
      value: totals.liked,
      share: totals.like_rate,
      tone: 'text-spark',
    },
    {
      label: '«Меньше такого» и скрытия',
      value: totals.rejected,
      share: totals.reject_rate,
      tone: 'text-destructive',
    },
  ]
  return (
    <ul className="space-y-3">
      {steps.map((step) => (
        <li
          key={step.label}
          className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_6.5rem] items-center gap-3"
        >
          {/* Two lines rather than "«Больше такого» ил…": the column is narrow. */}
          <span className="text-sm leading-snug">{step.label}</span>
          <RateBar rate={step.share} scale={1} tone={step.tone} />
          <span className="text-right text-sm tabular-nums">
            {formatNumber(step.value)}
            <span className="ml-1.5 text-xs text-outline">{formatPercent(step.share)}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}

export function Days({ daily }: { daily: Analytics['daily'] }) {
  const days = daily.map((day) => day.day)
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <DayBars days={days} values={daily.map((day) => day.seen)} label="Показы статей по дням" />
      <RateLines
        days={days}
        label="Доля открытий и отметок (дни менее чем с 30 показами пропущены)"
        series={[
          {
            label: 'открывают',
            tone: 'text-primary',
            values: daily.map((day) => (day.enough ? day.ctr : null)),
          },
          {
            label: '«больше такого» или сохранили',
            tone: 'text-spark',
            values: daily.map((day) => (day.enough ? day.like_rate : null)),
          },
        ]}
      />
    </div>
  )
}

/** Rows of one breakdown: a name, how many were seen, the CTR with its interval and the like rate. */
export function RateRows({
  rows,
  empty,
}: {
  rows: { key: string; label: ReactNode; detail?: string; rates: Rates }[]
  empty: string
}) {
  if (!rows.length) return <p className="text-sm text-muted-foreground">{empty}</p>
  const scale = Math.max(0.05, ...rows.map((row) => row.rates.ctr_high))
  return (
    <div className="space-y-3.5">
      <div className="hidden grid-cols-[minmax(0,15rem)_5rem_minmax(0,1fr)_5rem_4.5rem] gap-3 text-[11px] text-outline sm:grid">
        <span />
        <span className="text-right">показы</span>
        <span>доля открытий</span>
        <span className="text-right">открыли</span>
        <span className="text-right">«больше»</span>
      </div>
      {rows.map(({ key, label, detail, rates }) => (
        <div
          key={key}
          className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 sm:grid-cols-[minmax(0,15rem)_5rem_minmax(0,1fr)_5rem_4.5rem]"
        >
          <div className="min-w-0">
            <p className="truncate text-sm">{label}</p>
            {detail && <p className="truncate text-xs text-outline">{detail}</p>}
          </div>
          <span className="text-right text-sm text-muted-foreground tabular-nums">
            {/* A phone has no header row: each number carries its name. */}
            <span className="mr-1 text-xs text-outline sm:hidden">показов</span>
            {formatNumber(rates.seen)}
          </span>
          <div className="col-span-2 sm:col-span-1">
            <RateBar
              rate={rates.ctr}
              low={rates.ctr_low}
              high={rates.ctr_high}
              scale={scale}
              tone={rates.enough ? 'text-primary' : 'text-outline'}
            />
          </div>
          <span
            className={clsx(
              'tabular-nums whitespace-nowrap sm:text-right',
              rates.enough ? 'text-sm' : 'text-xs text-outline',
            )}
          >
            {rates.enough && <span className="mr-1 text-xs text-outline sm:hidden">открыли</span>}
            {rates.enough ? formatPercent(rates.ctr) : 'мало данных'}
          </span>
          <span className="text-right text-sm text-muted-foreground tabular-nums">
            {rates.enough && <span className="mr-1 text-xs text-outline sm:hidden">«больше»</span>}
            {rates.enough ? formatPercent(rates.like_rate) : ''}
          </span>
        </div>
      ))}
    </div>
  )
}

const SLOT_LABELS: Record<string, [string, string]> = {
  ranked: ['Лента по интересам', 'с учётом интересов читателя'],
  explore: ['Что-то новое', 'каждая 7-я карточка'],
  newest: ['Свежее', 'пока профиль читателя не настроен'],
  saved: ['Сохранённое', 'вкладка «Сохранённое»'],
  digest: ['Выпуски', 'статьи в выпусках'],
}

export function Slots({ slots }: { slots: Analytics['slots'] }) {
  return (
    <RateRows
      empty="Показов пока нет."
      rows={slots.map((slot) => ({
        key: slot.slot,
        label: SLOT_LABELS[slot.slot]?.[0] ?? slot.slot,
        detail: SLOT_LABELS[slot.slot]?.[1],
        rates: slot,
      }))}
    />
  )
}

export function Sources({ data }: { data: Analytics }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <h3 className="mb-3 text-sm font-medium">Чаще открывают</h3>
        <RateRows
          empty="Ни у одного источника пока нет 30 показов статей."
          rows={data.sources_best.map((row) => ({
            key: String(row.source_id),
            label: row.name,
            rates: row,
          }))}
        />
      </div>
      <div>
        <h3 className="mb-3 text-sm font-medium">Чаще отклоняют</h3>
        {data.sources_rejected.length ? (
          <ul className="space-y-3">
            {data.sources_rejected.map((row) => (
              <li
                key={row.source_id}
                className="grid grid-cols-[minmax(0,1fr)_minmax(0,40%)_3.5rem] items-center gap-3"
              >
                <span className="truncate text-sm">{row.name}</span>
                <RateBar
                  rate={row.reject_rate}
                  scale={Math.max(...data.sources_rejected.map((item) => item.reject_rate))}
                  tone="text-destructive"
                />
                <span className="text-right text-sm tabular-nums">
                  {formatPercent(row.reject_rate)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Отклонённых статей пока нет.</p>
        )}
      </div>
    </div>
  )
}

export function Categories({ categories }: { categories: Analytics['categories'] }) {
  return (
    <RateRows
      empty="Показов пока нет."
      rows={categories.map((row) => ({
        key: row.category,
        label: CATEGORY_LABELS[row.category as keyof typeof CATEGORY_LABELS] ?? row.category,
        rates: row,
      }))}
    />
  )
}

export function Adaptation({ cohorts }: { cohorts: Analytics['adaptation'] }) {
  return (
    <RateRows
      empty="Показов пока нет."
      rows={cohorts.map((row) => ({
        key: String(row.adaptive),
        label: row.adaptive ? 'С автоподстройкой' : 'Без автоподстройки',
        detail: `${formatNumber(row.readers)} ${plural(row.readers, ['читатель', 'читателя', 'читателей'])}`,
        rates: row,
      }))}
    />
  )
}

const VARIANT_LABELS: Record<string, [string, string]> = {
  hand: ['Ручные веса', 'при выключенной модели'],
  control: ['Ручные веса, контрольная группа', 'при включённой модели'],
  learned: ['Обученная модель', 'группа обученной модели'],
}

const STATUS: Record<RankerRun['status'], { label: string; tone: 'ok' | 'neutral' | 'danger' }> = {
  active: { label: 'включена', tone: 'ok' },
  rejected: { label: 'не включена', tone: 'neutral' },
  retired: { label: 'снята', tone: 'danger' },
}

export function Ranker({ data }: { data: Analytics }) {
  const ranker = data.ranker
  return (
    <div className="space-y-6">
      <RateRows
        empty="Выдач пока нет."
        rows={data.variants.map((row) => ({
          key: row.variant,
          label: VARIANT_LABELS[row.variant]?.[0] ?? row.variant,
          detail: `${VARIANT_LABELS[row.variant]?.[1] ?? ''} · ${formatNumber(row.readers)} ${plural(row.readers, ['читатель', 'читателя', 'читателей'])}`,
          rates: row,
        }))}
      />
      {ranker && (
        <div>
          <h3 className="text-sm font-medium">Ночные обучения</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {ranker.active
              ? `Включена модель ${ranker.active}: её порядок выдачи получают ${formatPercent(ranker.share)} читателей.`
              : `Сейчас ранжирование идёт по ручным весам. Модель включится, только если превзойдёт их по качеству на последних днях, и охватит ${formatPercent(ranker.share)} читателей.`}
          </p>
          {ranker.runs.length ? (
            <ul className="mt-3 divide-y divide-outline-variant">
              {ranker.runs.map((run) => (
                <li key={run.version} className="py-2.5 text-sm">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="tabular-nums">{formatDateTime(run.created_at)}</span>
                    <Chip tone={STATUS[run.status].tone}>{STATUS[run.status].label}</Chip>
                    {run.hand_ndcg !== null && run.model_ndcg !== null && (
                      <span className="text-xs text-muted-foreground tabular-nums">
                        nDCG@20 {run.hand_ndcg.toFixed(3)} → {run.model_ndcg.toFixed(3)}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{run.note}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">
              Обучение ещё не запускалось: оно идёт каждую ночь.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
