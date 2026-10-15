import clsx from 'clsx'
import { ArrowDown, ArrowUp, Minus, Plus } from '../../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import type { ReactNode } from 'react'
import { EASE } from '../../components/tokens'
import { Loading, Skeleton } from '../../components/loading'
import { AnimatedNumber, Card, Chip, EmptyState, ErrorState, Spinner } from '../../components/ui'
import type { ProfileSpec } from '../../lib/api'
import { diffPreview } from '../../lib/diff'
import type { Movement } from '../../lib/diff'
import { AUDIENCE_DAYS, externalHref, modelLabel, periodWords, plural } from '../../lib/format'
import { usePreview } from '../../lib/queries'

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
  new: 'bg-success-soft text-success',
  up: 'bg-success-soft text-success',
  down: 'bg-warning-soft text-warning',
  same: '',
}

type Props = {
  draft: ProfileSpec
  /** The profile as stored; null for a profile that has not been saved yet. */
  saved: ProfileSpec | null
  isDirty: boolean
}

export function PreviewPanel({ draft, saved, isDirty }: Props) {
  // The period an issue of this audience is built over by default.
  const days = AUDIENCE_DAYS[draft.audience]
  const current = usePreview(draft, days)
  const baseline = usePreview(saved, days, 0)

  const baselineItems = isDirty && saved ? (baseline.data?.items ?? null) : null
  const diff = current.data ? diffPreview(baselineItems, current.data.items) : null
  const added = diff?.rows.filter((row) => row.movement === 'new').length ?? 0

  return (
    <Card className="flex max-h-[calc(100dvh-4.5rem)] flex-col overflow-hidden">
      <div className="border-b border-separator px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">Предпросмотр выпуска</h2>
          {current.isFetching && current.isValid && <Spinner className="size-3.5 text-accent" />}
        </div>
        <p className="mt-0.5 text-xs text-muted">
          За {periodWords(days)} по текущим настройкам. Обновляется при редактировании, без языковой
          модели.
        </p>
        {current.data && (
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
            <span>
              <AnimatedNumber
                value={current.data.selected}
                className="text-base font-semibold text-foreground"
              />{' '}
              из {current.data.candidates} кандидатов
            </span>
            <span className="tabular">
              {current.data.window_total}{' '}
              {plural(current.data.window_total, ['публикация', 'публикации', 'публикаций'])} за
              период
            </span>
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
                <span className="text-xs text-muted">по сравнению с сохранённым профилем</span>
              </span>
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* layoutScroll: rows reorder inside a scrolling box, so their positions
          must be measured relative to its scroll offset. */}
      <motion.div layoutScroll className="relative flex-1 overflow-y-auto">
        {!current.isValid && (
          <EmptyState title="Подборка ждёт названий" pose="waiting">
            Дайте название каждому интересу, и здесь появится подборка.
          </EmptyState>
        )}
        {current.isError && <ErrorState title="Предпросмотр не получился" error={current.error} />}
        {!current.data && current.isLoading && (
          <Loading label="Собираем предпросмотр" className="space-y-2 p-4">
            {Array.from({ length: 6 }, (_, index) => (
              <div key={index} className="flex items-center gap-3 px-1 py-1.5">
                <Skeleton className="size-6 shrink-0 rounded-full" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-11/12" />
                  <Skeleton className="h-2.5 w-1/3" />
                </div>
              </div>
            ))}
          </Loading>
        )}
        {diff && diff.rows.length === 0 && (
          <EmptyState title="Подборка пуста">
            Ни одна публикация не проходит порог. Добавьте ключевые слова или снизьте порог
            релевантности.
          </EmptyState>
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
                  className="flex items-start gap-3 border-b border-separator px-5 py-2.5 last:border-b-0"
                >
                  <span className="tabular mt-0.5 w-8 shrink-0 text-xs font-semibold text-muted">
                    {row.score.toFixed(2)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <a
                      href={externalHref(row.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="line-clamp-2 text-[13px] leading-snug hover:text-accent-soft-foreground"
                    >
                      {row.title}
                    </a>
                    <p className="mt-0.5 truncate text-[11px] text-muted">
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
          <div className="border-t border-separator bg-surface-secondary/60 px-5 py-3">
            <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted">
              <Minus size={12} strokeWidth={3} /> Выпали после правки
            </p>
            <ul className="space-y-1">
              {diff.dropped.slice(0, 8).map((item) => (
                <li key={item.article_id} className="truncate text-xs text-muted line-through">
                  {item.title}
                </li>
              ))}
            </ul>
          </div>
        )}
      </motion.div>

      {current.data && (
        <p className="border-t border-separator px-5 py-2.5 text-[11px] text-muted">
          Поиск: {modelLabel(current.data.embedding_model)}
          {current.data.lexical_only &&
            ' · векторный поиск недоступен, работает только полнотекстовый'}
        </p>
      )}
    </Card>
  )
}
