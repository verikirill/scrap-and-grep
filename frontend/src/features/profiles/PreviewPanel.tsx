import clsx from 'clsx'
import { ArrowDown, ArrowUp, Minus, Plus } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import type { ReactNode } from 'react'
import { EASE } from '../../components/tokens'
import { AnimatedNumber, Card, Chip, Spinner } from '../../components/ui'
import type { ProfileSpec } from '../../lib/api'
import { diffPreview } from '../../lib/diff'
import type { Movement } from '../../lib/diff'
import { externalHref, modelLabel, plural } from '../../lib/format'
import { usePreview } from '../../lib/queries'

const PERIOD_DAYS = 7

const MOVEMENT_ICON: Record<Movement, ReactNode> = {
  new: <Plus size={12} strokeWidth={3} />,
  up: <ArrowUp size={12} strokeWidth={3} />,
  down: <ArrowDown size={12} strokeWidth={3} />,
  same: null,
}

const MOVEMENT_LABEL: Record<Movement, string> = {
  new: 'Появилась после правки',
  up: 'Оценка выросла',
  down: 'Оценка снизилась',
  same: '',
}

const MOVEMENT_STYLE: Record<Movement, string> = {
  new: 'bg-success-container text-success',
  up: 'bg-success-container text-success',
  down: 'bg-spark-container text-spark',
  same: '',
}

type Props = {
  draft: ProfileSpec
  /** The profile as stored; null for a profile that has not been saved yet. */
  saved: ProfileSpec | null
  isDirty: boolean
}

export function PreviewPanel({ draft, saved, isDirty }: Props) {
  const current = usePreview(draft, PERIOD_DAYS)
  const baseline = usePreview(saved, PERIOD_DAYS, 0)

  const baselineItems = isDirty && saved ? (baseline.data?.items ?? null) : null
  const diff = current.data ? diffPreview(baselineItems, current.data.items) : null
  const added = diff?.rows.filter((row) => row.movement === 'new').length ?? 0

  return (
    <Card className="flex max-h-[calc(100dvh-4.5rem)] flex-col overflow-hidden">
      <div className="border-b border-outline-variant px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">Что попадёт в выпуск</h2>
          {current.isFetching && current.isValid && <Spinner className="size-3.5 text-primary" />}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">
          За неделю, по текущим настройкам. Обновляется по мере правки, без языковой модели.
        </p>
        {current.data && (
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>
              <AnimatedNumber
                value={current.data.selected}
                className="text-base font-semibold text-foreground"
              />{' '}
              из {current.data.candidates} кандидатов
            </span>
            <span className="tabular">{current.data.window_total} публикаций за период</span>
          </div>
        )}
        <AnimatePresence>
          {isDirty && diff && (added > 0 || diff.dropped.length > 0) && (
            <motion.p
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <span className="mt-3 flex flex-wrap gap-1.5">
                {added > 0 && (
                  <Chip tone="ok">
                    +{added} {plural(added, ['новая', 'новые', 'новых'])}
                  </Chip>
                )}
                {diff.dropped.length > 0 && (
                  <Chip tone="danger">
                    -{diff.dropped.length}{' '}
                    {plural(diff.dropped.length, ['выпала', 'выпали', 'выпало'])}
                  </Chip>
                )}
                <span className="text-xs text-outline">по сравнению с сохранённым профилем</span>
              </span>
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* layoutScroll: rows reorder inside a scrolling box, so their positions
          must be measured relative to its scroll offset. */}
      <motion.div layoutScroll className="relative flex-1 overflow-y-auto">
        {!current.isValid && (
          <p className="px-5 py-8 text-center text-sm text-muted-foreground">
            Дайте название каждому интересу, и здесь появится подборка.
          </p>
        )}
        {current.isError && (
          <p className="px-5 py-6 text-sm text-destructive">
            {current.error instanceof Error
              ? current.error.message
              : 'Не удалось получить предпросмотр.'}
          </p>
        )}
        {!current.data && current.isLoading && (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }, (_, index) => (
              <div key={index} className="skeleton h-12" />
            ))}
          </div>
        )}
        {diff && diff.rows.length === 0 && (
          <p className="px-5 py-8 text-center text-sm text-muted-foreground">
            Ничего не проходит порог. Добавьте ключевые слова или снизьте порог релевантности.
          </p>
        )}
        {diff && (
          <ul className="relative">
            <AnimatePresence initial={false} mode="popLayout">
              {diff.rows.map((row) => (
                <motion.li
                  key={row.article_id}
                  layout
                  initial={{ opacity: 0, x: 16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -16 }}
                  transition={{ duration: 0.3, ease: EASE }}
                  className="flex items-start gap-3 border-b border-outline-variant px-5 py-2.5 last:border-b-0"
                >
                  <span className="tabular mt-0.5 w-8 shrink-0 text-xs font-semibold text-muted-foreground">
                    {row.score.toFixed(2)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <a
                      href={externalHref(row.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="line-clamp-2 text-[13px] leading-snug hover:text-on-primary-container"
                    >
                      {row.title}
                    </a>
                    <p className="mt-0.5 truncate text-[11px] text-outline">
                      {row.source_name}
                      {row.interest_title && ` · ${row.interest_title}`}
                    </p>
                  </div>
                  {row.movement !== 'same' && (
                    <span
                      role="img"
                      title={MOVEMENT_LABEL[row.movement]}
                      aria-label={MOVEMENT_LABEL[row.movement]}
                      className={clsx(
                        'mt-0.5 grid size-5 shrink-0 place-items-center rounded-md',
                        MOVEMENT_STYLE[row.movement],
                      )}
                    >
                      {MOVEMENT_ICON[row.movement]}
                    </span>
                  )}
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
        {diff && diff.dropped.length > 0 && (
          <div className="border-t border-outline-variant bg-surface-container/60 px-5 py-3">
            <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Minus size={12} strokeWidth={3} /> Выпали после правки
            </p>
            <ul className="space-y-1">
              {diff.dropped.slice(0, 8).map((item) => (
                <li key={item.article_id} className="truncate text-xs text-outline line-through">
                  {item.title}
                </li>
              ))}
            </ul>
          </div>
        )}
      </motion.div>

      {current.data && (
        <p className="border-t border-outline-variant px-5 py-2.5 text-[11px] text-outline">
          Поиск: {modelLabel(current.data.embedding_model)}
          {current.data.lexical_only && ' · модель эмбеддингов недоступна, только полнотекстовый'}
        </p>
      )}
    </Card>
  )
}
