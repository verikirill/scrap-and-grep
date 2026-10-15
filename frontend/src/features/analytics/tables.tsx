import clsx from 'clsx'
import type { ReactNode } from 'react'
import { Chip } from '../../components/ui'
import type { Analytics, RankerRun, Rates } from '../../lib/api'
import { CATEGORY_LABELS, formatDateTime, formatNumber, plural } from '../../lib/format'
import { formatPercent } from '../../lib/analyticsFormat'
import { RateBar } from './charts'

/** Nothing to list yet: a quiet tinted box rather than a stray line of text. */
export function EmptyRows({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-2xl bg-surface-secondary px-4 py-6 text-center text-sm text-muted">
      {children}
    </p>
  )
}

const HEAD = 'text-[11px] font-medium text-muted'
const NUMBER = 'text-right text-sm tabular-nums'

/*
 * The columns of a breakdown. In a narrow card the bar takes its own line under
 * the row; from 42rem of card it gets a column between the views and the rates.
 * The card's width decides, not the screen's: half a desktop is a narrow card.
 */
const COLUMNS =
  'grid grid-cols-[minmax(0,1fr)_3rem_3.75rem_3.75rem] gap-x-3 @2xl:grid-cols-[minmax(0,15rem)_4.5rem_minmax(0,1fr)_4.5rem_4.5rem]'
const AT = {
  seen: 'col-start-2 row-start-1',
  bar: 'col-[1/-1] row-start-2 @2xl:col-[3/4] @2xl:row-start-1',
  ctr: 'col-start-3 row-start-1 @2xl:col-start-4',
  lowData: 'col-[3/5] row-start-1 @2xl:col-[4/6]',
  like: 'col-start-4 row-start-1 @2xl:col-start-5',
}

export type RateRow = { key: string; label: ReactNode; detail?: string; rates: Rates }

/**
 * Rows of one breakdown as a table: a name, how many were seen, the share
 * opened with its interval, and the share marked «больше». A row with too few
 * views says so instead of a rate that means nothing.
 */
export function RateRows({
  rows,
  empty,
  label,
}: {
  rows: RateRow[]
  empty: string
  label: string
}) {
  if (!rows.length) return <EmptyRows>{empty}</EmptyRows>
  // A row with a handful of views has an interval up to 100 %: it must not squeeze the rest.
  const sure = rows.filter((row) => row.rates.enough)
  const scale = Math.max(0.05, ...(sure.length ? sure : rows).map((row) => row.rates.ctr_high))
  return (
    <div className="@container">
      <div role="table" aria-label={label}>
        <div role="row" className={clsx(COLUMNS, 'border-b border-separator pb-2')}>
          <span role="columnheader" className={clsx(HEAD, 'col-start-1 row-start-1')}>
            <span className="sr-only">Название</span>
          </span>
          <span role="columnheader" className={clsx(HEAD, AT.seen, 'text-right')}>
            показы
          </span>
          <span aria-hidden className={clsx(HEAD, 'col-[3/4] row-start-1 hidden @2xl:block')}>
            доля открытий
          </span>
          <span role="columnheader" className={clsx(HEAD, AT.ctr, 'text-right')}>
            открыли
          </span>
          <span role="columnheader" className={clsx(HEAD, AT.like, 'text-right')}>
            «больше»
          </span>
        </div>
        <div className="divide-y divide-separator">
          {rows.map(({ key, label: name, detail, rates }) => (
            <div key={key} role="row" className={clsx(COLUMNS, 'items-center gap-y-2 py-3')}>
              <div role="rowheader" className="col-start-1 row-start-1 min-w-0">
                <p className="line-clamp-2 text-sm font-medium break-words">{name}</p>
                {detail && (
                  <p title={detail} className="truncate text-xs text-muted">
                    {detail}
                  </p>
                )}
              </div>
              <span role="cell" className={clsx(NUMBER, AT.seen, 'text-muted')}>
                {formatNumber(rates.seen)}
              </span>
              <div aria-hidden className={AT.bar}>
                <RateBar
                  rate={rates.ctr}
                  low={rates.ctr_low}
                  high={rates.ctr_high}
                  scale={scale}
                  tone={rates.enough ? 'accent' : 'muted'}
                />
              </div>
              {rates.enough ? (
                <>
                  <span role="cell" className={clsx(NUMBER, AT.ctr, 'font-semibold')}>
                    {formatPercent(rates.ctr)}
                  </span>
                  <span role="cell" className={clsx(NUMBER, AT.like)}>
                    {formatPercent(rates.like_rate)}
                  </span>
                </>
              ) : (
                <span role="cell" aria-colspan={2} className={clsx(AT.lowData, 'justify-self-end')}>
                  <Chip className="text-[11px] whitespace-nowrap">мало данных</Chip>
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
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
      label="Места в ленте и выпусках"
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

function SubHead({ children }: { children: ReactNode }) {
  return <h3 className="mb-3 text-sm font-semibold">{children}</h3>
}

const REJECT_COLUMNS =
  'grid grid-cols-[minmax(0,1fr)_3.75rem] gap-x-3 @md:grid-cols-[minmax(0,1fr)_minmax(0,40%)_3.75rem]'

/** Sources by the share of their articles hidden or marked «меньше». */
function Rejected({ rows }: { rows: Analytics['sources_rejected'] }) {
  if (!rows.length) return <EmptyRows>Отклонённых статей пока нет.</EmptyRows>
  const scale = Math.max(...rows.map((item) => item.reject_rate))
  return (
    <div className="@container">
      <div role="table" aria-label="Чаще отклоняют">
        <div role="row" className={clsx(REJECT_COLUMNS, 'border-b border-separator pb-2')}>
          <span role="columnheader" className={clsx(HEAD, 'col-start-1')}>
            <span className="sr-only">Источник</span>
          </span>
          <span
            role="columnheader"
            className={clsx(HEAD, 'col-start-2 text-right @md:col-start-3')}
          >
            отклоняют
          </span>
        </div>
        <div className="divide-y divide-separator">
          {rows.map((row) => (
            <div
              key={row.source_id}
              role="row"
              className={clsx(REJECT_COLUMNS, 'items-center gap-y-2 py-3')}
            >
              <span
                role="rowheader"
                className="col-start-1 row-start-1 truncate text-sm font-medium"
              >
                {row.name}
              </span>
              <div aria-hidden className="col-[1/-1] row-start-2 @md:col-[2/3] @md:row-start-1">
                <RateBar rate={row.reject_rate} scale={scale} tone="danger" />
              </div>
              <span
                role="cell"
                className={clsx(NUMBER, 'col-start-2 row-start-1 font-semibold @md:col-start-3')}
              >
                {formatPercent(row.reject_rate)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function Sources({ data }: { data: Analytics }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2 lg:gap-8">
      <div className="min-w-0">
        <SubHead>Чаще открывают</SubHead>
        <RateRows
          label="Чаще открывают"
          empty="Ни у одного источника пока нет 30 показов статей."
          rows={data.sources_best.map((row) => ({
            key: String(row.source_id),
            label: row.name,
            rates: row,
          }))}
        />
      </div>
      <div className="min-w-0">
        <SubHead>Чаще отклоняют</SubHead>
        <Rejected rows={data.sources_rejected} />
      </div>
    </div>
  )
}

export function Categories({ categories }: { categories: Analytics['categories'] }) {
  return (
    <RateRows
      label="Категории"
      empty="Показов пока нет."
      rows={categories.map((row) => ({
        key: row.category,
        label: CATEGORY_LABELS[row.category as keyof typeof CATEGORY_LABELS] ?? row.category,
        rates: row,
      }))}
    />
  )
}

const readersWord = (count: number) =>
  `${formatNumber(count)} ${plural(count, ['читатель', 'читателя', 'читателей'])}`

export function Adaptation({ cohorts }: { cohorts: Analytics['adaptation'] }) {
  return (
    <RateRows
      label="Подстройка профилей"
      empty="Показов пока нет."
      rows={cohorts.map((row) => ({
        key: String(row.adaptive),
        label: row.adaptive ? 'С автоподстройкой' : 'Без автоподстройки',
        detail: readersWord(row.readers),
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

function Runs({ ranker }: { ranker: NonNullable<Analytics['ranker']> }) {
  return (
    <div className="mt-6 border-t border-separator pt-5">
      <h3 className="text-sm font-semibold">Ночные обучения</h3>
      <p className="mt-1 text-xs text-muted">
        {ranker.active
          ? `Включена модель ${ranker.active}: её порядок выдачи получают ${formatPercent(ranker.share)} читателей.`
          : `Сейчас ранжирование идёт по ручным весам. Модель включится, только если превзойдёт их по качеству на последних днях, и охватит ${formatPercent(ranker.share)} читателей.`}
      </p>
      {ranker.runs.length ? (
        <ul className="mt-3 divide-y divide-separator">
          {ranker.runs.map((run) => (
            <li key={run.version} className="py-3 text-sm">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="font-medium tabular-nums">{formatDateTime(run.created_at)}</span>
                <Chip tone={STATUS[run.status].tone}>{STATUS[run.status].label}</Chip>
                {run.hand_ndcg !== null && run.model_ndcg !== null && (
                  <span className="text-xs text-muted tabular-nums">
                    nDCG@20 {run.hand_ndcg.toFixed(3)} → {run.model_ndcg.toFixed(3)}
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-muted">{run.note}</p>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-3">
          <EmptyRows>Обучение ещё не запускалось, оно идёт каждую ночь.</EmptyRows>
        </div>
      )}
    </div>
  )
}

export function Ranker({ data }: { data: Analytics }) {
  return (
    <div>
      <RateRows
        label="Ранжирование ленты"
        empty="Выдач пока нет."
        rows={data.variants.map((row) => ({
          key: row.variant,
          label: VARIANT_LABELS[row.variant]?.[0] ?? row.variant,
          detail: `${VARIANT_LABELS[row.variant]?.[1] ?? ''} · ${readersWord(row.readers)}`,
          rates: row,
        }))}
      />
      {data.ranker && <Runs ranker={data.ranker} />}
    </div>
  )
}
