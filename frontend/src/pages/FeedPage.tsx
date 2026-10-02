import clsx from 'clsx'
import { Bookmark, FileUp, RefreshCw, SlidersHorizontal, Sparkles } from '../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { EASE, buttonClass } from '../components/tokens'
import { Button, Card, EmptyState, ErrorNote, PageHeader } from '../components/ui'
import { FeedCard } from '../features/feed/FeedCard'
import { PostCard } from '../features/feed/PostCard'
import { TastePanel } from '../features/feed/TastePanel'
import type { FeedItem, FeedView, Placement, ReactionKind } from '../lib/api'
import { formatRelative, plural } from '../lib/format'
import { keys, useFeed, useFeedback, useMe, useSaved, useTaste } from '../lib/queries'

const TABS = [
  { id: 'feed', label: 'Лента', icon: Sparkles },
  { id: 'saved', label: 'Сохранённое', icon: Bookmark },
] as const

// Signals that change what the next feed looks like.
const TEACHING: ReactionKind[] = ['like', 'dislike', 'save', 'hide']

function Skeletons({ view }: { view: FeedView }) {
  if (view === 'telegram') {
    return (
      <div className="space-y-3" role="status" aria-label="Собираем ленту">
        {[0, 1, 2].map((row) => (
          <div key={row} className="flex items-end gap-2.5">
            <div className="skeleton size-10 shrink-0 rounded-full" />
            <div className="skeleton h-72 flex-1 rounded-2xl rounded-bl-md" />
          </div>
        ))}
      </div>
    )
  }
  return (
    <div className="space-y-3" role="status" aria-label="Собираем ленту">
      {[0, 1, 2, 3].map((row) => (
        <div key={row} className="skeleton h-32" />
      ))}
    </div>
  )
}

/** The Telegram look sits on a chat's wallpaper, in a column of a chat's width. */
function PostColumn({ view, children }: { view: FeedView; children: React.ReactNode }) {
  if (view !== 'telegram') return <div className="space-y-3">{children}</div>
  return (
    <div className="chat-wallpaper -mx-4 px-3 py-4 sm:mx-0 sm:rounded-3xl sm:px-5 sm:py-5">
      <div className="mx-auto max-w-[600px] space-y-3">{children}</div>
    </div>
  )
}

function uniqueItems(items: FeedItem[]): FeedItem[] {
  const seen = new Set<number>()
  return items.filter((item) => !seen.has(item.article_id) && seen.add(item.article_id))
}

export function FeedPage() {
  const [search, setSearch] = useSearchParams()
  const tab = search.get('tab') === 'saved' ? 'saved' : 'feed'
  const feed = useFeed()
  const saved = useSaved(tab === 'saved')
  const taste = useTaste()
  // Chosen on the account page; the cards until the account says otherwise.
  const view: FeedView = useMe().data?.feed_view ?? 'cards'
  const Item = view === 'telegram' ? PostCard : FeedCard
  const feedback = useFeedback()
  const client = useQueryClient()
  // Reactions given since the feed was built: they are saved at once, but the
  // order on screen changes only when the reader asks.
  const [pendingSignals, setPendingSignals] = useState(0)

  const list = tab === 'saved' ? saved : feed
  // Pages come from one snapshot and do not overlap; the check is a guard
  // for the rare case when a snapshot expired between two pages.
  const items = uniqueItems(list.data?.pages.flatMap((page) => page.items) ?? [])
  // The snapshot each article came from: normally one for all pages.
  const snapshotOf = new Map(
    list.data?.pages.flatMap((page) =>
      page.items.map((item) => [item.article_id, page.snapshot] as const),
    ) ?? [],
  )
  const placementOf = (item: FeedItem): Placement => ({
    listId: snapshotOf.get(item.article_id) ?? null,
    position: item.position,
    slot: item.slot,
  })
  const generatedAt = feed.data?.pages[0]?.generated_at
  const knowsReader = Boolean(taste.data?.facets.some((facet) => facet.kind !== 'avoid'))

  const react = (item: FeedItem, kind: ReactionKind, isActive: boolean) => {
    feedback.mutate(
      {
        articleId: item.article_id,
        kind,
        isActive,
        context: 'feed',
        placement: placementOf(item),
      },
      {
        onSuccess: () => {
          if (TEACHING.includes(kind)) setPendingSignals((count) => count + 1)
        },
      },
    )
  }

  /** Start over from the first page of a freshly ranked feed. */
  const rebuild = () => {
    setPendingSignals(0)
    void client.resetQueries({ queryKey: keys.feed })
    void taste.refetch()
  }

  return (
    <>
      <PageHeader
        title="Для вас"
        subtitle="Публикации последних двух недель в порядке, который подобран под вас: по интересам, по резюме и по тому, что вы отмечали раньше. У каждой видно, почему она здесь."
        actions={
          <Button
            icon={<RefreshCw size={15} />}
            isBusy={feed.isRefetching}
            onClick={rebuild}
            disabled={tab !== 'feed'}
          >
            Пересобрать
          </Button>
        }
      />

      <div
        className="mb-5 inline-flex gap-1 rounded-xl bg-surface-container p-1"
        role="group"
        aria-label="Раздел"
      >
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            aria-pressed={tab === id}
            onClick={() => setSearch(id === 'feed' ? {} : { tab: id })}
            className={clsx(
              'relative inline-flex items-center gap-2 rounded-lg px-4 py-1.5 text-sm font-medium transition-colors',
              tab === id
                ? 'text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {tab === id && (
              <motion.span
                layoutId="feed-tab"
                className="absolute inset-0 rounded-lg bg-primary shadow-elevation-1"
                transition={{ type: 'spring', stiffness: 480, damping: 38 }}
              />
            )}
            <Icon size={15} className="relative" />
            <span className="relative">{label}</span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,1fr)_19rem]">
        <div className="min-w-0 space-y-3">
          <ErrorNote error={list.error ?? feedback.error} />

          <AnimatePresence initial={false}>
            {tab === 'feed' && pendingSignals > 0 && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.25, ease: EASE }}
                className="overflow-hidden"
              >
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-primary-container px-4 py-2.5 text-sm text-on-primary-container">
                  <span>
                    {pendingSignals} {plural(pendingSignals, ['оценка', 'оценки', 'оценок'])}{' '}
                    {plural(pendingSignals, ['учтена', 'учтены', 'учтено'])}. Порядок на экране не
                    меняется, пока вы читаете.
                  </span>
                  <button type="button" onClick={rebuild} className="font-semibold hover:underline">
                    Пересобрать ленту
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {tab === 'feed' && taste.isSuccess && !knowsReader && (
            <Card className="p-5">
              <h2 className="text-base font-semibold">Лента пока не знает, что вам интересно</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Ниже просто свежие публикации. Загрузите резюме или задайте интересы, и порядок
                станет вашим.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link to="/welcome" className={buttonClass('primary', 'sm')}>
                  <FileUp size={15} />
                  Загрузить резюме
                </Link>
                <Link to="/profiles" className={buttonClass('secondary', 'sm')}>
                  <SlidersHorizontal size={15} />
                  Задать интересы
                </Link>
              </div>
            </Card>
          )}

          {list.isPending ? (
            <PostColumn view={view}>
              <Skeletons view={view} />
            </PostColumn>
          ) : items.length === 0 ? (
            <Card>
              {tab === 'saved' ? (
                <EmptyState icon={<Bookmark size={22} />} title="Сохранённого пока нет">
                  Закладка на карточке откладывает публикацию сюда и заодно говорит ленте, что тема
                  вам важна.
                </EmptyState>
              ) : (
                <EmptyState icon={<Sparkles size={22} />} title="Подходящих публикаций не нашлось">
                  За две недели по вашим интересам ничего не набралось. Проверьте, что источники
                  опрашиваются, или расширьте интересы.
                </EmptyState>
              )}
            </Card>
          ) : (
            <PostColumn view={view}>
              {items.map((item, index) => (
                <Item
                  key={item.article_id}
                  item={item}
                  index={index}
                  placement={placementOf(item)}
                  onReact={(kind, isActive) => react(item, kind, isActive)}
                />
              ))}
              {list.hasNextPage && (
                <div className="flex justify-center pt-2">
                  <Button
                    isBusy={list.isFetchingNextPage}
                    onClick={() => void list.fetchNextPage()}
                  >
                    Показать ещё
                  </Button>
                </div>
              )}
            </PostColumn>
          )}
          {tab === 'feed' && generatedAt && items.length > 0 && (
            <p className="pt-1 text-center text-xs text-outline">
              Лента собрана {formatRelative(generatedAt)}
            </p>
          )}
        </div>

        <aside className="xl:sticky xl:top-9 xl:self-start">
          {taste.isError ? (
            <Card className="space-y-3 p-5">
              <ErrorNote error={taste.error} />
              <Button size="sm" onClick={() => void taste.refetch()}>
                Повторить
              </Button>
            </Card>
          ) : taste.data ? (
            <TastePanel taste={taste.data} />
          ) : (
            <div className="skeleton h-72" />
          )}
        </aside>
      </div>
    </>
  )
}
