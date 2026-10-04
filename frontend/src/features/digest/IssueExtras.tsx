import clsx from 'clsx'
import { motion } from 'motion/react'
import { useState } from 'react'
import {
  Analytics,
  EventRepeat,
  ListOrdered,
  Minus,
  Schedule,
  TrendingDown,
  TrendingUp,
} from '../../components/icons'
import { EASE, rowMotion } from '../../components/tokens'
import { Card, Chip } from '../../components/ui'
import type { Digest, PlanEntry, TagCount, VulnerabilityChange } from '../../lib/api'
import { durationWords, externalHref, formatDate, formatNumber, plural } from '../../lib/format'

/** The issue's work as an analyst would do it by hand, by a rule it states. */
export function ManualWork({ digest }: { digest: Digest }) {
  const work = digest.manual
  if (!work) return null
  return (
    <p className="mt-3 flex items-start gap-2.5 rounded-lg bg-primary-container/60 px-3 py-2.5 text-sm">
      <Schedule size={18} className="mt-0.5 shrink-0 text-primary" />
      <span>
        <span className="font-semibold">
          Вместо ручной работы: около {durationWords(work.minutes)}
        </span>
        {work.seconds ? `, ассистенту хватило ${Math.round(work.seconds)} с` : ''}.{' '}
        <span className="text-muted-foreground">
          Расчёт: {formatNumber(work.headlines)}{' '}
          {plural(work.headlines, ['заголовок', 'заголовка', 'заголовков'])} по 5 с и {work.entries}{' '}
          {plural(work.entries, ['запись', 'записи', 'записей'])} по 3 мин.
        </span>
      </span>
    </p>
  )
}

function SectionHead({
  icon,
  title,
  note,
}: {
  icon: React.ReactNode
  title: string
  note: string
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-primary-container text-primary">
        {icon}
      </span>
      <div>
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="text-xs text-muted-foreground">{note}</p>
      </div>
    </div>
  )
}

function PlanRow({ entry, index }: { entry: PlanEntry; index: number }) {
  const [done, setDone] = useState(false)
  const id = `plan-${index}`
  return (
    <motion.li {...rowMotion(index)} className="flex gap-3 py-3">
      <input
        id={id}
        type="checkbox"
        checked={done}
        onChange={(event) => setDone(event.target.checked)}
        className="mt-1 size-4 shrink-0 accent-primary"
        aria-label={`Сделано: ${entry.headline}`}
      />
      <div className={clsx('min-w-0 flex-1 transition-opacity', done && 'opacity-50')}>
        <a
          href={externalHref(entry.url)}
          target="_blank"
          rel="noreferrer noopener"
          className={clsx(
            'font-medium text-foreground decoration-primary/40 underline-offset-4 hover:underline',
            done && 'line-through',
          )}
        >
          {entry.headline}
        </a>
        {entry.steps.length > 0 && (
          <ul className="mt-1 space-y-0.5 text-sm text-muted-foreground">
            {entry.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        )}
        {entry.facts.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {entry.facts.map((fact) => (
              <Chip key={fact} tone={fact.startsWith('в каталоге CISA KEV') ? 'danger' : 'neutral'}>
                {fact}
              </Chip>
            ))}
          </div>
        )}
      </div>
    </motion.li>
  )
}

function ShiftPlan({ entries }: { entries: PlanEntry[] }) {
  return (
    <Card className="p-6">
      <SectionHead
        icon={<ListOrdered size={18} />}
        title="План на смену"
        note="Срочное из выпуска, эксплуатируемые уязвимости первыми. Шаги взяты из карточек"
      />
      <ol className="mt-3 divide-y divide-outline-variant">
        {entries.map((entry, index) => (
          <PlanRow key={entry.url} entry={entry} index={index} />
        ))}
      </ol>
    </Card>
  )
}

function Changes({ changes }: { changes: VulnerabilityChange[] }) {
  return (
    <Card className="p-6">
      <SectionHead
        icon={<EventRepeat size={18} />}
        title="Что изменилось с прошлых выпусков"
        note="Уязвимости, которые уже были в выпусках этого профиля за 30 дней"
      />
      <ul className="mt-3 divide-y divide-outline-variant">
        {changes.map((change, index) => (
          <motion.li key={change.id} {...rowMotion(index)} className="py-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Chip tone="accent">{change.id}</Chip>
              <a
                href={externalHref(change.url)}
                target="_blank"
                rel="noreferrer noopener"
                className="font-medium text-foreground decoration-primary/40 underline-offset-4 hover:underline"
              >
                {change.headline}
              </a>
            </div>
            <p className="mt-1 text-muted-foreground">
              {change.what.join('; ')}. В выпуске от {formatDate(change.since)} этого не было.
            </p>
          </motion.li>
        ))}
      </ul>
    </Card>
  )
}

function Delta({ row }: { row: TagCount }) {
  if (row.before === null || row.before === undefined) return null
  const delta = row.count - row.before
  const Icon = delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus
  const words =
    delta === 0 ? 'как в прошлом выпуске' : `${delta > 0 ? '+' : '-'}${Math.abs(delta)} к прошлому`
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <Icon size={14} />
      {words}
    </span>
  )
}

function Numbers({ rows, title }: { rows: TagCount[]; title: string }) {
  const max = Math.max(...rows.map((row) => Math.max(row.count, row.before ?? 0)), 1)
  return (
    <Card className="p-6">
      <SectionHead
        icon={<Analytics size={18} />}
        title={title}
        note="Записи выпуска по признакам датасета"
      />
      <ul className="mt-4 space-y-3">
        {rows.map((row, index) => (
          <li
            key={row.tag}
            title={`${row.label}: ${row.count}${row.before !== null && row.before !== undefined ? `, в прошлом выпуске ${row.before}` : ''}`}
          >
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span>{row.label}</span>
              <span className="flex items-baseline gap-3">
                <Delta row={row} />
                <span className="tabular font-semibold">{row.count}</span>
              </span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-container">
              <motion.div
                className="h-full origin-left rounded-full bg-primary"
                initial={{ scaleX: 0 }}
                animate={{ scaleX: row.count / max }}
                transition={{ duration: 0.6, ease: EASE, delay: 0.04 * index }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

/**
 * What the issue adds beside its entries, worked out from them and never by
 * the model: a specialist's plan for the shift and what changed since earlier
 * issues, management's period in numbers.
 */
export function IssueExtras({ digest }: { digest: Digest }) {
  const plan = digest.plan ?? []
  const changes = digest.changes ?? []
  const numbers = digest.numbers ?? []
  if (plan.length + changes.length + numbers.length === 0) return null
  return (
    <div className="space-y-6">
      {plan.length > 0 && <ShiftPlan entries={plan} />}
      {changes.length > 0 && <Changes changes={changes} />}
      {numbers.length > 0 && (
        <Numbers rows={numbers} title={digest.numbers_title || 'Период в цифрах'} />
      )}
    </div>
  )
}
