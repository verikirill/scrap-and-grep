import clsx from 'clsx'
import {
  ArrowUp,
  Bookmark,
  FileUp,
  Psychology,
  RefreshCw,
  Schedule,
  SlidersHorizontal,
  Sparkles,
} from '../components/icons'
import { AnimatePresence, motion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import { Fragment, useState } from 'react'
import { toast } from 'sonner'
import { Link, useSearchParams } from 'react-router'
import { EASE, buttonClass } from '../components/tokens'
import { Button, Card, EmptyState, ErrorNote, PageHeader } from '../components/ui'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '../components/ui/sheet'
import { FeedCard } from '../features/feed/FeedCard'
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

// Two orders of one list, and what the reader put aside. The last order
// chosen is kept with the account and opens next time.
const TABS = [
  { id: 'new', label: 'Новое', icon: Schedule },
  { id: 'top', label: 'Важное', icon: Sparkles },
  { id: 'saved', label: 'Сохранённое', icon: Bookmark },
] as const
type Tab = (typeof TABS)[number]['id']

const SUBTITLES: Record<Tab, string> = {
  new: 'Публикации за две недели, прошедшие отбор по вашим интересам, от новых к старым. Просмотренное уходит ниже, новое появляется само.',
  top: 'Публикации за две недели, упорядоченные под вас: по интересам, резюме и прошлым отметкам. У каждой видно, почему она здесь.',
  saved: 'Публикации, которые вы отложили кнопкой «Сохранить».',
}

const isTab = (value: string | null): value is Tab => TABS.some((tab) => tab.id === value)

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
    <div className="chat-wallpaper -mx-4 px-2 py-3 sm:mx-0 sm:rounded-3xl sm:px-5 sm:py-5">
      <div className="mx-auto max-w-[600px] space-y-3">{children}</div>
    </div>
  )
}

/** Where the articles the reader has not met end, as a chat marks unread messages. */
function SeenDivider({ view, isFirst }: { view: FeedView; isFirst: boolean }) {
  const text = isFirst ? 'Нового пока нет, ниже уже просмотренное' : 'Ниже уже просмотренное'
  if (view === 'telegram') {
    return (
      <p className="mx-auto w-fit max-w-full rounded-full bg-on-surface/10 px-4 py-1.5 text-xs text-foreground/80 backdrop-blur">
        {text}
      </p>
    )
  }
  return (
    <p className="flex items-center gap-3 pt-2 text-xs font-medium text-muted-foreground">
      <span aria-hidden className="h-px flex-1 bg-outline-variant" />
      {text}
      <span aria-hidden className="h-px flex-1 bg-outline-variant" />
    </p>
  )
}

function uniqueItems(items: FeedItem[]): FeedItem[] {
  const seen = new Set<number>()
  return items.filter((item) => !seen.has(item.article_id) && seen.add(item.article_id))
}

export function FeedPage() {
  const [search, setSearch] = useSearchParams()
  const me = useMe().data
  const settings = useUpdateSettings()
  const asked = search.get('tab')
  const tab: Tab = isTab(asked) ? asked : (me?.feed_order ?? 'new')
  const order: FeedOrder = tab === 'saved' ? (me?.feed_order ?? 'new') : tab
  const feed = useFeed(order)
  const saved = useSaved(tab === 'saved')
  const taste = useTaste()
  // Chosen on the account page; the cards until the account says otherwise.
  const view: FeedView = me?.feed_view ?? 'cards'
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
  // New articles that passed the reader's interests since the list on screen was made.
  const fresh = useFeedFresh(tab === 'saved' ? null : feed.data?.pages[0]?.built_at)
  const freshCount = fresh.data?.fresh ?? 0
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
          const said = MARKED[kind]
          if (isActive && said) toast.success(said)
        },
      },
    )
  }

  // On a desktop it stands beside the feed; narrower, it opens from a button
  // instead of waiting after the whole feed.
  const isWide = useMediaQuery('(min-width: 1280px)')
  const tastePanel = (
    <>
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
    </>
  )

  /** Start over from the first page of a freshly ranked feed. */
  const rebuild = () => {
    setPendingSignals(0)
    void client.resetQueries({ queryKey: keys.feed })
    void taste.refetch()
  }

  const showFresh = () => {
    rebuild()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const selectTab = (id: Tab) => {
    // An order left a while ago would come back as it was: it is made anew.
    if (id !== 'saved' && id !== tab) void client.resetQueries({ queryKey: [...keys.feed, id] })
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

      <div className="mb-5 flex items-center gap-2">
        <div
          className="inline-flex gap-1 rounded-xl bg-surface-container p-1"
          role="group"
          aria-label="Раздел"
        >
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              aria-pressed={tab === id}
              // On a phone the third tab is its icon: three words and two buttons do not fit.
              aria-label={id === 'saved' ? label : undefined}
              title={id === 'saved' ? label : undefined}
              onClick={() => selectTab(id)}
              className={clsx(
                'relative inline-flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors sm:px-4',
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
              <Icon size={15} className={clsx('relative', id !== 'saved' && 'hidden sm:block')} />
              <span className={clsx('relative', id === 'saved' && 'hidden sm:inline')}>
                {label}
              </span>
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-1">
          {!isWide && (
            <Sheet>
              <SheetTrigger asChild>
                <button
                  type="button"
                  aria-label="Что лента знает о вас"
                  title="Что лента знает о вас"
                  className="state-layer relative inline-flex h-10 items-center gap-2 overflow-hidden rounded-full px-2.5 text-sm font-medium text-primary sm:px-4"
                >
                  <Psychology size={19} />
                  <span className="hidden sm:inline">Что лента знает о вас</span>
                </button>
              </SheetTrigger>
              <SheetContent side="bottom" className="max-h-[85dvh] overflow-y-auto rounded-t-3xl">
                <SheetHeader className="sr-only">
                  <SheetTitle>Что лента знает о вас</SheetTitle>
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
            className="state-layer relative grid size-10 place-items-center overflow-hidden rounded-full text-primary disabled:opacity-40 sm:hidden"
          >
            <RefreshCw size={19} className={clsx(feed.isRefetching && 'animate-spin')} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,1fr)_19rem]">
        <div className="min-w-0 space-y-3">
          <ErrorNote error={list.error ?? feedback.error} />

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
                  className="state-layer relative inline-flex h-10 items-center gap-2 overflow-hidden rounded-full bg-primary px-4 text-sm font-medium text-primary-foreground shadow-elevation-2"
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
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-primary-container px-4 py-2.5 text-sm text-on-primary-container">
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
                  Кнопка «Сохранить» на карточке откладывает публикацию сюда и заодно говорит ленте,
                  что тема вам важна.
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
                <Fragment key={item.article_id}>
                  {tab === 'new' && item.seen && !items[index - 1]?.seen && (
                    <SeenDivider view={view} isFirst={index === 0} />
                  )}
                  <Item
                    item={item}
                    index={index}
                    placement={placementOf(item)}
                    onReact={(kind, isActive) => react(item, kind, isActive)}
                  />
                </Fragment>
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
          {tab !== 'saved' && generatedAt && items.length > 0 && (
            <p className="pt-1 text-center text-xs text-outline">
              Лента собрана {formatRelative(generatedAt)}
            </p>
          )}
        </div>

        {isWide && <aside className="sticky top-9 self-start">{tastePanel}</aside>}
      </div>
    </>
  )
}
