import clsx from 'clsx'
import { FileText, Search } from '../../components/icons'
import { motion } from 'motion/react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { EASE, rowMotion } from '../../components/tokens'
import { Button, Card, Chip, EmptyState, ErrorNote, Spinner } from '../../components/ui'
import type { SourceCategory, TimelinePoint } from '../../lib/api'
import { CATEGORY_LABELS, formatDateTime, formatNumber } from '../../lib/format'
import { useArticles, useTimeline } from '../../lib/queries'
import { OriginalLink } from '../reader/OriginalLink'
import { articlePath } from '../reader/paths'

const CATEGORIES = Object.keys(CATEGORY_LABELS) as SourceCategory[]
const TIMELINE_DAYS = 14
const PAGE_SIZE = 30

/** Articles per day as plain bars: enough to see that the feeds are alive. */
function Timeline({ points }: { points: TimelinePoint[] }) {
  const days = useMemo(() => {
    const totals = new Map<string, number>()
    for (const point of points) {
      const key = point.day.slice(0, 10)
      totals.set(key, (totals.get(key) ?? 0) + point.count)
    }
    return [...totals.entries()].sort(([a], [b]) => a.localeCompare(b)).slice(-TIMELINE_DAYS)
  }, [points])
  const max = Math.max(...days.map(([, count]) => count), 1)
  const total = days.reduce((sum, [, count]) => sum + count, 0)

  return (
    <div
      className="flex h-16 items-end gap-1"
      role="img"
      aria-label={`Публикаций за ${TIMELINE_DAYS} дней: ${formatNumber(total)}`}
    >
      {days.map(([day, count], index) => (
        <div
          key={day}
          className="h-full flex-1"
          title={`${day.slice(8, 10)}.${day.slice(5, 7)}: ${formatNumber(count)}`}
        >
          <motion.div
            className="h-full origin-bottom rounded-t bg-primary/70 transition-colors hover:bg-primary"
            initial={{ scaleY: 0 }}
            animate={{ scaleY: Math.max(count / max, 0.03) }}
            transition={{ duration: 0.5, delay: index * 0.025, ease: EASE }}
          />
        </div>
      ))}
    </div>
  )
}

export function ArticlesList() {
  const [input, setInput] = useState('')
  const [q, setQ] = useState('')
  const [categories, setCategories] = useState<SourceCategory[]>([])
  const timeline = useTimeline(TIMELINE_DAYS)

  useEffect(() => {
    const timer = setTimeout(() => setQ(input.trim()), 300)
    return () => clearTimeout(timer)
  }, [input])

  const articles = useArticles({ q, category: categories })
  const pages = articles.data?.pages
  const items = pages?.flatMap((page) => page.items) ?? []
  const total = pages?.[0]?.total

  const toggleCategory = (category: SourceCategory) => {
    setCategories((current) =>
      current.includes(category)
        ? current.filter((item) => item !== category)
        : [...current, category],
    )
  }

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="min-w-0 flex-1">
            <div className="relative">
              <Search size={16} className="absolute top-1/2 left-3 -translate-y-1/2 text-outline" />
              <input
                type="search"
                aria-label="Поиск по публикациям"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder='Поиск по публикациям: уязвимость SCADA, "цифровая подстанция"'
                className="w-full rounded-lg border border-outline-variant bg-card py-2.5 pr-10 pl-9 text-sm placeholder:text-outline hover:border-outline focus:border-primary focus:outline-none"
              />
              {articles.isFetching && (
                <Spinner className="absolute top-1/2 right-3 size-3.5 -translate-y-1/2 text-primary" />
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5" role="group" aria-label="Категории">
              {CATEGORIES.map((category) => {
                const active = categories.includes(category)
                return (
                  <button
                    key={category}
                    type="button"
                    aria-pressed={active}
                    onClick={() => toggleCategory(category)}
                    className={clsx(
                      'rounded-lg border px-2.5 py-1 text-[13px] transition-colors duration-150',
                      active
                        ? 'border-primary bg-primary-container text-on-primary-container'
                        : 'border-outline-variant text-muted-foreground hover:border-outline hover:text-foreground',
                    )}
                  >
                    {CATEGORY_LABELS[category]}
                  </button>
                )
              })}
            </div>
          </div>
          {/* While searching, the results matter more than the chart: on a phone it steps aside. */}
          <div className={clsx('w-full sm:block sm:w-56', q && 'hidden')}>
            <p className="mb-1.5 text-xs text-muted-foreground">Публикаций за 14 дней</p>
            {timeline.data ? (
              <Timeline points={timeline.data} />
            ) : (
              <div className="skeleton h-16" />
            )}
          </div>
        </div>
      </Card>

      <ErrorNote error={articles.error} />

      {total !== undefined && (
        <p className="px-1 text-xs text-muted-foreground" aria-live="polite">
          {q ? 'Найдено' : 'Всего'}:{' '}
          <span className="tabular font-semibold text-foreground">{formatNumber(total)}</span>
        </p>
      )}

      <Card
        className={clsx(
          'overflow-hidden transition-opacity',
          articles.isPlaceholderData && 'opacity-60',
        )}
      >
        {pages && items.length === 0 && (
          <EmptyState icon={<FileText size={22} />} title="Ничего не найдено">
            Попробуйте изменить запрос. Поиск учитывает словоформы и смысл, включая запросы на
            других языках.
          </EmptyState>
        )}
        {!pages && articles.isLoading && (
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }, (_, index) => (
              <div key={index} className="skeleton h-14" />
            ))}
          </div>
        )}
        <ul className="divide-y divide-outline-variant">
          {items.map((article, index) => (
            <motion.li key={article.id} {...rowMotion(index % PAGE_SIZE)} className="px-5 py-3">
              {/* Matches by meaning come after those with the words, under a line of their own. */}
              {article.match === 'meaning' && items[index - 1]?.match !== 'meaning' && (
                <p className="-mx-5 -mt-3 mb-3 bg-surface-container px-5 py-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                  Похоже по смыслу
                </p>
              )}
              <div className="group flex items-start gap-1">
                <Link
                  to={articlePath(article.id)}
                  className="min-w-0 flex-1 text-sm font-medium hover:text-on-primary-container"
                >
                  {article.title}
                </Link>
                <OriginalLink url={article.url} title={article.title} />
              </div>
              {article.summary && (
                <p className="mt-0.5 line-clamp-2 text-[13px] text-muted-foreground">
                  {article.summary}
                </p>
              )}
              <p className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-outline">
                <span className="font-medium text-muted-foreground">{article.source_name}</span>
                <span>{formatDateTime(article.published_at)}</span>
                <Chip>{CATEGORY_LABELS[article.source_category]}</Chip>
                {article.has_full_text && <Chip tone="ok">полный текст</Chip>}
                {article.match === 'meaning' && (
                  <Chip title="Слов запроса в статье нет, но она о том же">по смыслу</Chip>
                )}
              </p>
            </motion.li>
          ))}
        </ul>
      </Card>

      {articles.hasNextPage && (
        <div className="flex justify-center">
          <Button
            isBusy={articles.isFetchingNextPage}
            onClick={() => void articles.fetchNextPage()}
          >
            Показать ещё
          </Button>
        </div>
      )}
    </div>
  )
}
