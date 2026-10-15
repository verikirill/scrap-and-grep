import clsx from 'clsx'
import {
  ArrowUp,
  Bookmark,
  FileUp,
  Layers,
  RefreshCw,
  Schedule,
  SlidersHorizontal,
  Search,
  Target,
} from '../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import { Fragment, useRef, useState } from 'react'
import { toast } from '../lib/toast'
import { Link, useSearchParams } from 'react-router'
import { EASE, buttonClass } from '../components/tokens'
import { Loading, Skeleton, SkeletonList } from '../components/loading'
import { Button, Card, EmptyState, ErrorNote, ErrorState, PageHeader } from '../components/ui'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '../components/ui/sheet'
import { FeedCard } from '../features/feed/FeedCard'
import { FeedViewSwitch } from '../features/feed/FeedViewSwitch'
import { PostCard } from '../features/feed/PostCard'
import { TastePanel } from '../features/feed/TastePanel'
import type { FeedItem, FeedOrder, FeedView, Placement, ReactionKind } from '../lib/api'
import { formatRelative, plural } from '../lib/format'
import {
  keys,
  useFeed,
  useFeedFresh,
  useFeedback,
  useMe,
  useSaved,
  useTaste,
  useUpdateSettings,
} from '../lib/queries'
import { useMediaQuery } from '../lib/useMediaQuery'
import { SlidingPill } from '../components/SlidingPill'

// Two orders of one list, and what the reader put aside. The last order
// chosen is kept with the account and opens next time.
const TABS = [
  { id: 'new', label: 'Новое', icon: Schedule },
  { id: 'top', label: 'Важное', icon: Target },
  { id: 'saved', label: 'Сохранённое', icon: Bookmark },
] as const
type Tab = (typeof TABS)[number]['id']

const SUBTITLES: Record<Tab, string> = {
  new: 'Публикации по вашим интересам за две недели, от новых к старым. Прочитанное уходит вниз, свежее появляется автоматически.',
  top: 'Публикации за две недели, подобранные по интересам, резюме и вашим отметкам. У каждой видно, почему она здесь.',
  saved: 'Публикации, которые вы отложили кнопкой «Сохранить».',
}

const isTab = (value: string | null): value is Tab => TABS.some((tab) => tab.id === value)

// A look at the other order and back keeps both lists as they were; an
// order left longer ago than this is ranked anew.
const TAB_REUSE_MS = 5 * 60_000

/** Whether a list was ranked longer ago than a look at the other order lasts. */
function isOutdated(updatedAt: number | undefined): boolean {
  return Date.now() - (updatedAt ?? 0) > TAB_REUSE_MS
}

// Signals that change what the next feed looks like.
const TEACHING: ReactionKind[] = ['like', 'dislike', 'save', 'hide']
// What a mark does, said where the reader is; a hidden card says it in its own place.
const MARKED: Partial<Record<ReactionKind, string>> = {
  like: 'Учтено: похожего станет больше',
  save: 'Сохранено, лежит во вкладке «Сохранённое»',
}

function Skeletons({ view }: { view: FeedView }) {
  if (view === 'telegram') {
    return (
      <Loading label="Собираем ленту" className="space-y-3">
        {[0, 1, 2].map((row) => (
          <div key={row} className="flex items-end gap-2.5">
            <Skeleton className="size-10 shrink-0 rounded-full" />
            <Skeleton className="h-72 flex-1 rounded-2xl rounded-bl-md" />
          </div>
        ))}
      </Loading>
    )
  }
  return (
    <Loading label="Собираем ленту">
      <SkeletonList count={4} />
    </Loading>
  )
}

/**
 * The Telegram look: on a phone the posts sit on a chat's wallpaper from edge
 * to edge; on a wide screen there is no panel, only a column of reading width
 * in the middle of the page.
 */
function PostColumn({ view, children }: { view: FeedView; children: React.ReactNode }) {
  if (view !== 'telegram') return <div className="space-y-3">{children}</div>
  return (
    <div className="chat-wallpaper -mx-4 px-2 py-3 sm:mx-0 sm:bg-transparent sm:bg-none sm:p-0 sm:pt-1">
      <div className="mx-auto max-w-[640px] space-y-3 sm:space-y-5">{children}</div>
    </div>
  )
}

/** Where the articles the reader has not met end, as a chat marks unread messages. */
function SeenDivider({ view, isFirst }: { view: FeedView; isFirst: boolean }) {
  const text = isFirst
    ? 'Новых публикаций нет, ниже — прочитанные'
    : 'Ниже — прочитанные публикации'
  if (view === 'telegram') {
    return (
      <p className="mx-auto w-fit max-w-full rounded-full bg-foreground/10 px-4 py-1.5 text-xs text-foreground/80 backdrop-blur">
        {text}
      </p>
    )
  }
  return (
    <p className="flex items-center gap-3 pt-2 text-xs font-medium text-muted">
      <span aria-hidden className="h-px flex-1 bg-separator" />
      {text}
      <span aria-hidden className="h-px flex-1 bg-separator" />
    </p>
  )
}

function uniqueItems(items: FeedItem[]): FeedItem[] {
  const seen = new Set<number>()
  return items.filter((item) => !seen.has(item.article_id) && seen.add(item.article_id))
}

export function FeedPage() {
  const tabRow = useRef<HTMLDivElement>(null)
  const [search, setSearch] = useSearchParams()
  const me = useMe().data
  const settings = useUpdateSettings()
  const asked = search.get('tab')
  const tab: Tab = isTab(asked) ? asked : (me?.feed_order ?? 'new')
  const order: FeedOrder = tab === 'saved' ? (me?.feed_order ?? 'new') : tab
  const feed = useFeed(order)
  const saved = useSaved(tab === 'saved')
  const taste = useTaste()
  // Chosen beside the tabs and kept with the account; the cards until it says otherwise.
  const view: FeedView = me?.feed_view ?? 'cards'
  const Item = view === 'telegram' ? PostCard : FeedCard
  const feedback = useFeedback()
  const client = useQueryClient()
  // Reactions given since the feed was built: they are saved at once, but the
  // order on screen changes only when the reader asks.
  const [pendingSignals, setPendingSignals] = useState(0)
  // After a tab switch the list is just there: its cards do not rise one by one again.
  const [isQuiet, setIsQuiet] = useState(false)

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
  // New articles that passed the reader's interests since the list on screen was made.
  const fresh = useFeedFresh(tab === 'saved' ? null : feed.data?.pages[0]?.built_at)
  const freshCount = fresh.data?.fresh ?? 0
  const knowsReader = Boolean(taste.data?.facets.some((facet) => facet.kind !== 'avoid'))

  // Each mark's own outcome: with marks queued one after another, the
  // mutation's callbacks and its error follow only the last one made.
  const [markError, setMarkError] = useState<unknown>(null)
  const react = (item: FeedItem, kind: ReactionKind, isActive: boolean) => {
    setMarkError(null)
    feedback
      .mutateAsync({
        articleId: item.article_id,
        kind,
        isActive,
        context: 'feed',
        placement: placementOf(item),
      })
      .then(() => {
        if (TEACHING.includes(kind)) setPendingSignals((count) => count + 1)
        const said = MARKED[kind]
        if (isActive && said) toast.success(said)
      }, setMarkError)
  }

  // On a desktop it stands beside the feed; narrower, it opens from a button
  // instead of waiting after the whole feed.
  const isWide = useMediaQuery('(min-width: 1280px)')
  const tastePanel = (
    <>
      {taste.isError ? (
        <Card>
          <ErrorState
            title="Вкусы не загрузились"
            error={taste.error}
            className="py-6"
            action={
              <Button size="sm" onClick={() => void taste.refetch()}>
                Повторить
              </Button>
            }
          />
        </Card>
      ) : taste.data ? (
        <TastePanel taste={taste.data} />
      ) : (
        <Loading
          label="Загружаем ваши вкусы"
          className="space-y-3 rounded-3xl bg-surface p-5 shadow-surface"
        >
          <Skeleton className="h-4 w-32" />
          {[0, 1, 2, 3, 4].map((row) => (
            <div key={row} className="flex items-center gap-2">
              <Skeleton className="h-3 flex-1" />
              <Skeleton className="h-3 w-10" />
            </div>
          ))}
          <Skeleton className="h-8 w-full rounded-full" />
        </Loading>
      )}
    </>
  )

  /** Start over from the first page of a freshly ranked feed. */
  const rebuild = () => {
    setPendingSignals(0)
    setIsQuiet(false)
    void client.resetQueries({ queryKey: keys.feed })
    void taste.refetch()
  }

  const showFresh = () => {
    rebuild()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const selectTab = (id: Tab) => {
    const queryKey = [...keys.feed, id]
    const isOld = isOutdated(client.getQueryState(queryKey)?.dataUpdatedAt)
    if (id !== 'saved' && id !== tab && isOld) void client.resetQueries({ queryKey })
    setIsQuiet(true)
    setSearch({ tab: id })
    if (id !== 'saved' && me && me.feed_order !== id) settings.mutate({ feed_order: id })
  }
  const refreshLabel = tab === 'new' ? 'Обновить' : 'Пересобрать'

  return (
    <>
      <PageHeader
        title="Для вас"
        subtitle={SUBTITLES[tab]}
        actions={
          // On a phone the button joins the row of tabs as an icon: the header
          // stays two lines instead of four.
          <span className="hidden sm:block">
            <Button
              icon={<RefreshCw size={15} />}
              isBusy={feed.isRefetching}
              onClick={rebuild}
              disabled={tab === 'saved'}
            >
              {refreshLabel}
            </Button>
          </span>
        }
      />

      {/* The row's own width decides what keeps its words: with the side menu
          open a desktop row is as narrow as a tablet's. Too narrow for all
          (the smallest phones), the controls move under the tabs. */}
      <div className="@container mb-5 flex flex-wrap items-center gap-1.5 @md:gap-2">
        <div
          ref={tabRow}
          className="relative isolate inline-flex gap-1 rounded-xl bg-surface p-1 ring-1 ring-border"
          role="group"
          aria-label="Раздел"
        >
          <SlidingPill container={tabRow} activeKey={tab} className="rounded-lg bg-default" />
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              aria-pressed={tab === id}
              data-active={tab === id}
              // In a narrow row the third tab is its icon: three words and the controls do not fit.
              aria-label={id === 'saved' ? label : undefined}
              title={id === 'saved' ? label : undefined}
              onClick={() => selectTab(id)}
              className={clsx(
                'relative inline-flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors @md:px-3 @lg:px-4',
                tab === id ? 'text-foreground' : 'text-muted hover:text-foreground',
              )}
            >
              <Icon size={15} className={clsx('relative', id !== 'saved' && 'hidden @lg:block')} />
              <span className={clsx('relative', id === 'saved' && 'hidden @md:inline')}>
                {label}
              </span>
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-0.5 @md:gap-1">
          <FeedViewSwitch view={view} />
          {!isWide && (
            <Sheet>
              <SheetTrigger asChild>
                <button
                  type="button"
                  aria-label="Из чего собрана лента"
                  title="Из чего собрана лента"
                  className="transition-colors hover:bg-default/70 relative inline-flex h-9 items-center gap-2 overflow-hidden rounded-full px-2 text-sm font-medium text-accent @3xl:h-10 @3xl:px-4"
                >
                  <Layers size={19} />
                  <span className="hidden @3xl:inline">Из чего собрана лента</span>
                </button>
              </SheetTrigger>
              <SheetContent side="bottom" className="max-h-[85dvh] overflow-y-auto rounded-t-3xl">
                <SheetHeader className="sr-only">
                  <SheetTitle>Из чего собрана лента</SheetTitle>
                  <SheetDescription>Интересы, резюме и выученные по отметкам темы</SheetDescription>
                </SheetHeader>
                <div className="p-4 pt-2">{tastePanel}</div>
              </SheetContent>
            </Sheet>
          )}
          <button
            type="button"
            onClick={rebuild}
            disabled={tab === 'saved' || feed.isRefetching}
            aria-label={`${refreshLabel} ленту`}
            title={`${refreshLabel} ленту`}
            className="transition-colors hover:bg-default/70 relative grid size-9 place-items-center overflow-hidden rounded-full text-accent disabled:opacity-40 sm:hidden"
          >
            <RefreshCw size={19} className={clsx(feed.isRefetching && 'animate-spin')} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,1fr)_19rem]">
        <div className="min-w-0 space-y-3">
          {/* A list that did not load at all says so in its own place, below. */}
          <ErrorNote error={(items.length > 0 ? list.error : null) ?? markError} />

          {/* New articles wait above the list until asked for: nothing moves under the reader. */}
          <AnimatePresence>
            {freshCount > 0 && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2, ease: EASE }}
                className="sticky top-20 z-10 flex justify-center md:top-4"
              >
                <button
                  type="button"
                  onClick={showFresh}
                  className="relative inline-flex h-10 items-center gap-2 overflow-hidden rounded-full bg-accent hover:bg-accent-hover transition-colors px-4 text-sm font-medium text-accent-foreground shadow-overlay"
                >
                  <ArrowUp size={16} />
                  {freshCount}{' '}
                  {plural(freshCount, ['новая публикация', 'новые публикации', 'новых публикаций'])}
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence initial={false}>
            {tab !== 'saved' && pendingSignals > 0 && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.25, ease: EASE }}
                className="overflow-hidden"
              >
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-accent-soft px-4 py-2.5 text-sm text-accent-soft-foreground">
                  <span>
                    {pendingSignals} {plural(pendingSignals, ['отметка', 'отметки', 'отметок'])}{' '}
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

          {tab !== 'saved' && taste.isSuccess && !knowsReader && (
            <Card className="p-5">
              <h2 className="text-base font-semibold">Интересы пока не заданы</h2>
              <p className="mt-1 text-sm text-muted">
                Ниже показаны свежие публикации подряд. Загрузите резюме или настройте интересы,
                чтобы лента подстроилась под вас.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link to="/welcome" className={buttonClass('primary', 'sm')}>
                  <FileUp size={15} />
                  Загрузить резюме
                </Link>
                <Link to="/profiles" className={buttonClass('secondary', 'sm')}>
                  <SlidersHorizontal size={15} />
                  Настроить интересы
                </Link>
              </div>
            </Card>
          )}

          {list.isPending ? (
            <PostColumn view={view}>
              <Skeletons view={view} />
            </PostColumn>
          ) : items.length === 0 ? (
            // A list that did not load is not empty: it says why, with a way to try again.
            list.isError ? (
              <Card>
                <ErrorState
                  title="Лента не загрузилась"
                  error={list.error}
                  action={<Button onClick={() => void list.refetch()}>Повторить</Button>}
                />
              </Card>
            ) : (
              <Card>
                {tab === 'saved' ? (
                  <EmptyState
                    icon={<Bookmark size={22} />}
                    title="Сохранённого пока нет"
                    action={
                      <Button variant="tonal" onClick={() => selectTab('new')}>
                        Открыть новое
                      </Button>
                    }
                  >
                    Здесь будут публикации, отложенные кнопкой «Сохранить».
                  </EmptyState>
                ) : (
                  <EmptyState
                    icon={<Search size={22} />}
                    title="Подходящих публикаций не нашлось"
                    action={
                      <Link to="/profiles" className={buttonClass('tonal')}>
                        Настроить интересы
                      </Link>
                    }
                  >
                    За две недели публикаций по вашим интересам не нашлось.
                  </EmptyState>
                )}
              </Card>
            )
          ) : (
            <PostColumn view={view}>
              {items.map((item, index) => (
                <Fragment key={item.article_id}>
                  {tab === 'new' && item.seen && !items[index - 1]?.seen && (
                    <SeenDivider view={view} isFirst={index === 0} />
                  )}
                  <Item
                    item={item}
                    index={index}
                    isQuiet={isQuiet}
                    placement={placementOf(item)}
                    onReact={(kind, isActive) => react(item, kind, isActive)}
                  />
                </Fragment>
              ))}
              {list.hasNextPage && (
                <div className="flex justify-center pt-2">
                  <Button
                    isBusy={list.isFetchingNextPage}
                    onClick={() => {
                      setIsQuiet(false)
                      void list.fetchNextPage()
                    }}
                  >
                    Показать ещё
                  </Button>
                </div>
              )}
            </PostColumn>
          )}
          {tab !== 'saved' && generatedAt && items.length > 0 && (
            <p className="pt-1 text-center text-xs text-muted">
              Лента собрана {formatRelative(generatedAt)}
            </p>
          )}
        </div>

        {isWide && <aside className="sticky top-9 self-start">{tastePanel}</aside>}
      </div>
    </>
  )
}
