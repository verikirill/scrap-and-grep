import clsx from 'clsx'
import { ArrowDown, ArrowRight, ArrowUp, GitCompareArrows, Minus, Plus } from 'lucide-react'
import { motion } from 'motion/react'
import type { ReactNode } from 'react'
import { useSearchParams } from 'react-router'
import { INPUT_CLASS, rowMotion } from '../components/tokens'
import { AnimatedNumber, Card, Chip, EmptyState, ErrorNote, PageHeader } from '../components/ui'
import type { DigestItem, DigestSummary, InterestChange } from '../lib/api'
import { externalHref, formatDateTime, SETTING_LABELS } from '../lib/format'
import { useComparison, useDigests } from '../lib/queries'

const CHANGE_LABELS: Record<InterestChange['change'], string> = {
  added: 'добавлен',
  removed: 'убран',
  changed: 'изменён',
}

const CHANGE_TONES = { added: 'ok', removed: 'danger', changed: 'spark' } as const

function optionLabel(digest: DigestSummary): string {
  return `${formatDateTime(digest.created_at)} · ${digest.profile_name} v${digest.profile_version} · ${digest.stats.selected ?? 0} публ.`
}

function Column({
  title,
  count,
  tone,
  icon,
  children,
}: {
  title: string
  count: number
  tone: string
  icon: ReactNode
  children: ReactNode
}) {
  return (
    <Card className="flex min-w-0 flex-col overflow-hidden">
      <div className="flex items-center gap-2.5 border-b border-line px-4 py-3">
        <span className={clsx('grid size-6 place-items-center rounded-md', tone)}>{icon}</span>
        <h2 className="text-sm font-semibold">{title}</h2>
        <AnimatedNumber value={count} className="ml-auto text-sm font-semibold text-muted" />
      </div>
      <ul className="divide-y divide-line">{children}</ul>
      {count === 0 && <p className="px-4 py-6 text-center text-xs text-faint">Пусто</p>}
    </Card>
  )
}

function Row({ item, index, trailing }: { item: DigestItem; index: number; trailing?: ReactNode }) {
  return (
    <motion.li {...rowMotion(index)} className="flex items-start gap-3 px-4 py-2.5">
      <div className="min-w-0 flex-1">
        <a
          href={externalHref(item.url)}
          target="_blank"
          rel="noopener noreferrer"
          className="line-clamp-2 text-[13px] leading-snug hover:text-accent-text"
        >
          {item.headline}
        </a>
        <p className="mt-0.5 truncate text-[11px] text-faint">
          {item.source_name}
          {item.interest_title && ` · ${item.interest_title}`}
        </p>
      </div>
      {trailing ?? (
        <span className="tabular mt-0.5 text-xs font-semibold text-muted">
          {item.score.toFixed(2)}
        </span>
      )}
    </motion.li>
  )
}

function Delta({ delta }: { delta: number }) {
  if (Math.abs(delta) < 0.005)
    return <span className="tabular mt-0.5 text-xs text-faint">0.00</span>
  const up = delta > 0
  return (
    <span
      className={clsx(
        'tabular mt-0.5 flex items-center gap-0.5 text-xs font-semibold',
        up ? 'text-ok' : 'text-spark',
      )}
    >
      {up ? <ArrowUp size={11} strokeWidth={3} /> : <ArrowDown size={11} strokeWidth={3} />}
      {Math.abs(delta).toFixed(2)}
    </span>
  )
}

export function ComparePage() {
  const [search, setSearch] = useSearchParams()
  const digests = useDigests()
  const done = digests.data?.filter((digest) => digest.status === 'done') ?? []

  // Default to the two most recent issues: "what changed since last time".
  const other = search.get('other') ?? done[0]?.id
  const base = search.get('base') ?? done.find((digest) => digest.id !== other)?.id
  const comparison = useComparison(base, other)

  const pick = (key: 'base' | 'other', value: string) => {
    const next = { base: base ?? '', other: other ?? '', [key]: value }
    setSearch(next, { replace: true })
  }

  return (
    <>
      <PageHeader
        title="Сравнение"
        subtitle="Два выпуска рядом: что появилось, что ушло и как изменились оценки. Удобно, чтобы увидеть эффект от правки интересов."
      />

      {digests.isSuccess && done.length < 2 ? (
        <Card>
          <EmptyState icon={<GitCompareArrows size={22} />} title="Нужно два готовых выпуска">
            Соберите дайджест, поменяйте интересы профиля и соберите ещё один. Разница появится
            здесь.
          </EmptyState>
        </Card>
      ) : (
        <>
          <Card className="mb-5 grid items-center gap-3 p-4 sm:grid-cols-[1fr_auto_1fr]">
            <select
              aria-label="Было"
              className={INPUT_CLASS}
              value={base ?? ''}
              onChange={(event) => pick('base', event.target.value)}
            >
              {done.map((digest) => (
                <option key={digest.id} value={digest.id} disabled={digest.id === other}>
                  {optionLabel(digest)}
                </option>
              ))}
            </select>
            <ArrowRight size={18} className="mx-auto hidden text-faint sm:block" />
            <select
              aria-label="Стало"
              className={INPUT_CLASS}
              value={other ?? ''}
              onChange={(event) => pick('other', event.target.value)}
            >
              {done.map((digest) => (
                <option key={digest.id} value={digest.id} disabled={digest.id === base}>
                  {optionLabel(digest)}
                </option>
              ))}
            </select>
          </Card>

          <ErrorNote error={comparison.error} />

          {comparison.data && (
            <motion.div
              key={`${base}-${other}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="space-y-5"
            >
              {(comparison.data.interest_changes.length > 0 ||
                comparison.data.settings_changed.length > 0) && (
                <Card className="p-4">
                  <h2 className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">
                    Что изменили в профиле
                  </h2>
                  <div className="flex flex-wrap gap-1.5">
                    {comparison.data.interest_changes.map((change) => (
                      <Chip
                        key={`${change.id}-${change.change}`}
                        tone={CHANGE_TONES[change.change]}
                      >
                        {change.title}: {CHANGE_LABELS[change.change]}
                      </Chip>
                    ))}
                    {comparison.data.settings_changed.map((field) => (
                      <Chip key={field}>{SETTING_LABELS[field] ?? field}</Chip>
                    ))}
                  </div>
                </Card>
              )}

              <div className="grid items-start gap-4 lg:grid-cols-3">
                <Column
                  title="Появилось"
                  count={comparison.data.added.length}
                  tone="bg-ok-soft text-ok"
                  icon={<Plus size={14} strokeWidth={3} />}
                >
                  {comparison.data.added.map((item, index) => (
                    <Row key={item.article_id} item={item} index={index} />
                  ))}
                </Column>
                <Column
                  title="Ушло"
                  count={comparison.data.removed.length}
                  tone="bg-danger-soft text-danger"
                  icon={<Minus size={14} strokeWidth={3} />}
                >
                  {comparison.data.removed.map((item, index) => (
                    <Row key={item.article_id} item={item} index={index} />
                  ))}
                </Column>
                <Column
                  title="Осталось"
                  count={comparison.data.kept.length}
                  tone="bg-sunken text-muted"
                  icon={<ArrowRight size={14} strokeWidth={3} />}
                >
                  {comparison.data.kept.map((change, index) => (
                    <Row
                      key={change.item.article_id}
                      item={change.item}
                      index={index}
                      trailing={<Delta delta={change.delta} />}
                    />
                  ))}
                </Column>
              </div>
            </motion.div>
          )}
          {comparison.isLoading && <div className="skeleton h-72" />}
        </>
      )}
    </>
  )
}
