import clsx from 'clsx'
import { useIsFetching, useIsMutating } from '@tanstack/react-query'
import {
  Analytics,
  ChevronLeft,
  ChevronRight,
  CompareArrows,
  DynamicFeed,
  Newspaper,
  Rss,
  Send,
  SlidersHorizontal,
  Users,
} from './icons'
import type { IconComponent } from './icons'
import { AnimatePresence, motion, Reorder } from 'motion/react'
import { useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router'
import { formatNumber, modelLabel } from '../lib/format'
import { navAccess } from '../lib/access'
import type { Access } from '../lib/access'
import { inReaderOrder, movedBy } from '../lib/navOrder'
import { useMe, useMeta, useUpdateSettings } from '../lib/queries'
import { prefetchRoute } from '../routes'
import { readOpen, writeOpen } from '../lib/remembered'
import { UserAvatar } from './UserAvatar'
import { LogoMark, Wordmark } from './Logo'
import { DURATION, EASE } from './tokens'
import { EntranceContext, newEntrance } from './entrance'
import { Skeleton } from './loading'
import { DottedVeil } from './ui/dotted-veil'
import { ThemeButton } from './ThemeToggle'
import { useDarkMode } from '../lib/useDarkMode'

type NavItem = {
  to: string
  label: string
  icon: IconComponent
  also?: string[]
  /** Reading, setting up, or running things: a gap sets the groups apart. */
  group: 'read' | 'setup' | 'manage'
  access: Access
}

// In the order of use: what a reader reads, what tunes it, what a manager runs.
const NAV: NavItem[] = [
  {
    to: '/',
    label: 'Дайджест',
    icon: Newspaper,
    also: ['/digests', '/share'],
    group: 'read',
    access: 'all',
  },
  { to: '/feed', label: 'Для вас', icon: DynamicFeed, group: 'read', access: 'all' },
  { to: '/profiles', label: 'Интересы', icon: SlidersHorizontal, group: 'setup', access: 'all' },
  { to: '/sources', label: 'Источники', icon: Rss, group: 'setup', access: 'all' },
  { to: '/compare', label: 'Сравнение', icon: CompareArrows, group: 'setup', access: 'all' },
  { to: '/channels', label: 'Каналы', icon: Send, group: 'manage', access: 'publisher' },
  { to: '/company', label: 'Компания', icon: Users, group: 'manage', access: 'manager' },
  { to: '/analytics', label: 'Аналитика', icon: Analytics, group: 'manage', access: 'admin' },
]

/**
 * A thin progress bar along the top while anything loads in the
 * background. It waits a moment before showing, so quick answers do not blink.
 */
function ActivityBar() {
  const busy = useIsFetching() + useIsMutating() > 0
  return (
    <AnimatePresence>
      {busy && (
        <motion.div
          // Shown only after a moment, so quick answers do not blink.
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, transition: { delay: 0.35, duration: 0.2 } }}
          exit={{ opacity: 0, transition: { duration: 0.15 } }}
          role="progressbar"
          aria-label="Загрузка"
          className="linear-progress fixed inset-x-0 top-0 z-50"
        />
      )}
    </AnimatePresence>
  )
}

function StatusLine() {
  const { data: meta, isError } = useMeta()
  if (isError) {
    return (
      <p className="flex items-center gap-2 text-xs text-danger">
        <span className="size-1.5 rounded-full bg-danger" />
        API недоступен
      </p>
    )
  }
  if (!meta) {
    return (
      <div className="space-y-1.5">
        <Skeleton className="h-3 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    )
  }
  // Offline means no language model at all; a model in Ollama or behind an
  // OpenAI-compatible API (Yandex AI Studio, vLLM) is named instead.
  const offline = meta.llm_provider === 'heuristic'
  return (
    <div className="space-y-1 text-xs text-muted">
      <p className="flex items-center gap-2">
        <span className={clsx('size-1.5 rounded-full', offline ? 'bg-warning' : 'bg-success')} />
        <span className="truncate" title={`Поиск: ${meta.embedding_model}`}>
          {offline ? 'Автономный режим' : modelLabel(meta.llm_model)}
        </span>
      </p>
      <p className="tabular pl-3.5 text-muted">
        {formatNumber(meta.articles)} публикаций · +{formatNumber(meta.articles_last_day)} за сутки
      </p>
    </div>
  )
}

/** The section the reader is in: the item whose path the address starts with. */
function activeSection(pathname: string): string | null {
  const found = NAV.find((item) =>
    item.to === '/'
      ? pathname === '/' || (item.also ?? []).some((prefix) => pathname.startsWith(prefix))
      : pathname.startsWith(item.to),
  )
  return found?.to ?? null
}

/** A section in the sidebar: icon and name in a row; the open one sits on a soft pill. */
function SideItem({
  item,
  active,
  isNarrow,
}: {
  item: NavItem
  active: boolean
  isNarrow: boolean
}) {
  const Icon = item.icon
  return (
    <Link
      to={item.to}
      // The row itself is dragged to a new place, not the link's address.
      draggable={false}
      // Folded, the name is the hint: the icon alone is all the row shows.
      title={isNarrow ? item.label : undefined}
      aria-label={isNarrow ? item.label : undefined}
      onPointerEnter={() => prefetchRoute(item.to)}
      onFocus={() => prefetchRoute(item.to)}
      aria-current={active ? 'page' : undefined}
      className={clsx(
        'group relative flex h-10 w-full items-center gap-3 rounded-xl text-sm outline-none',
        // The same padding folded or not: the icon stays put while the panel narrows.
        'pr-3 pl-[15px]',
        'focus-visible:ring-2 focus-visible:ring-focus',
        active ? 'font-semibold text-foreground' : 'font-medium text-muted hover:text-foreground',
      )}
    >
      {active && (
        <motion.span
          layoutId="side-pill"
          transition={{ type: 'spring', stiffness: 500, damping: 40 }}
          className="absolute inset-0 -z-10 rounded-xl bg-surface shadow-surface"
        />
      )}
      {!active && (
        <span className="absolute inset-0 -z-10 rounded-xl transition-colors group-hover:bg-default/60" />
      )}
      <Icon size={18} filled={active} className={clsx('shrink-0', active && 'text-accent')} />
      <span
        className={clsx(
          'truncate whitespace-nowrap transition-opacity duration-200',
          isNarrow && 'opacity-0',
        )}
      >
        {item.label}
      </span>
    </Link>
  )
}

/** A section in the phone's bottom bar: the icon over a short name. */
function BarItem({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon
  return (
    <Link
      to={item.to}
      aria-label={item.label}
      aria-current={active ? 'page' : undefined}
      className="relative flex min-w-0 flex-1 flex-col items-center gap-1 pt-2.5 pb-3"
    >
      <span className="relative grid h-8 w-14 place-items-center">
        {active && (
          <motion.span
            layoutId="bar-pill"
            transition={{ type: 'spring', stiffness: 500, damping: 40 }}
            className="absolute inset-0 rounded-full bg-accent-soft"
          />
        )}
        <Icon
          size={20}
          filled={active}
          className={clsx('relative', active ? 'text-accent' : 'text-muted')}
        />
      </span>
      <span
        className={clsx(
          'truncate text-[11px] leading-4',
          active ? 'font-semibold text-foreground' : 'text-muted',
        )}
      >
        {item.label}
      </span>
    </Link>
  )
}

/** The reader's picture leading to the account; in the open sidebar it is named. */
function AccountButton({ hasLabel = false }: { hasLabel?: boolean }) {
  const { data: me } = useMe()
  if (!me) return null
  return (
    <NavLink
      to="/account"
      onPointerEnter={() => prefetchRoute('/account')}
      aria-label={`Аккаунт: ${me.display_name}`}
      title={me.is_shared ? 'Общий аккаунт' : me.is_demo ? 'Временный аккаунт' : me.email}
      className="group flex shrink-0 items-center gap-2.5 rounded-full outline-none focus-visible:ring-2 focus-visible:ring-focus"
    >
      {({ isActive }) => (
        <>
          <span
            className={clsx(
              'grid size-9 shrink-0 place-items-center rounded-full transition-shadow',
              // The picture keeps its colours; the ring says this is the open section.
              isActive
                ? 'ring-2 ring-accent ring-offset-2 ring-offset-background'
                : 'group-hover:ring-2 group-hover:ring-border',
            )}
          >
            {/* The size of the button: a bigger picture pushed the letters off centre. */}
            <UserAvatar me={me} size={36} />
          </span>
          {hasLabel && (
            <span
              className={clsx(
                'text-sm',
                isActive
                  ? 'font-semibold text-foreground'
                  : 'font-medium text-muted group-hover:text-foreground',
              )}
            >
              Профиль
            </span>
          )}
        </>
      )}
    </NavLink>
  )
}

function Brand({ isNarrow }: { isNarrow: boolean }) {
  return (
    <Link
      to="/"
      aria-label="Scrap&Grep, главная"
      className={clsx(
        'flex items-center gap-2.5 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-focus',
        'px-[7px]',
      )}
    >
      <LogoMark size={34} />
      <Wordmark
        className={clsx(
          'text-[17px] whitespace-nowrap transition-opacity duration-200',
          isNarrow && 'opacity-0',
        )}
      />
    </Link>
  )
}

const RAIL_KEY = 'sidebar'

/** The sidebar folded to icons or open with names; the choice is kept per browser. */
function useNarrowSidebar(): [boolean, () => void] {
  const [isNarrow, setNarrow] = useState(() => !readOpen(RAIL_KEY, true))
  const toggle = () =>
    setNarrow((value) => {
      writeOpen(RAIL_KEY, value)
      return !value
    })
  return [isNarrow, toggle]
}

export function Layout({ children }: { children: ReactNode }) {
  const [dark, toggleDark] = useDarkMode()
  const [isNarrow, toggleNarrow] = useNarrowSidebar()
  const me = useMe()
  const isAdmin = Boolean(me.data?.is_admin && !me.data.is_demo)
  const access = navAccess(me.data)
  const ordered = inReaderOrder(
    NAV.filter((item) => access[item.access]),
    me.data?.nav_order ?? [],
  )
  // While a section is dragged, the order on screen; it is saved when let go.
  const [dragged, setDragged] = useState<NavItem[] | null>(null)
  const draggedRef = useRef<NavItem[] | null>(null)
  // A drag ends with a click on the link under the pointer: that click stays put.
  const wasDragged = useRef(false)
  const updateSettings = useUpdateSettings()
  const sections = dragged ?? ordered
  const saveOrder = (paths: string[]) => {
    if (paths.join() !== ordered.map((item) => item.to).join()) {
      updateSettings.mutate({ nav_order: paths })
    }
  }
  const reorder = (items: NavItem[]) => {
    draggedRef.current = items
    setDragged(items)
  }
  const letGo = () => {
    if (draggedRef.current) saveOrder(draggedRef.current.map((item) => item.to))
    draggedRef.current = null
    setDragged(null)
  }
  // On a phone the bottom bar holds five sections; the running ones sit up top.
  const barSections = sections.filter((item) => item.group !== 'manage').slice(0, 5)
  const topSections = sections.filter((item) => !barSections.includes(item))
  const location = useLocation()
  const section = location.pathname.split('/')[1] ?? ''
  const active = activeSection(location.pathname)
  const pageKey = section === 'digests' ? '' : section
  // A new line of card entrances for each section the reader opens.
  const entrance = useMemo(() => {
    void pageKey
    return newEntrance()
  }, [pageKey])
  return (
    // isolate: the veil sits under every card yet over the page colour.
    <div className="isolate min-h-dvh bg-background">
      <DottedVeil className="dotted-veil" />
      <ActivityBar />

      {/* Sidebar, from tablet width up. */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-30 hidden flex-col gap-6 border-r border-separator bg-background py-5 transition-[width] duration-300 ease-out md:flex',
          // Names fade inside the narrowing panel instead of leaving at once.
          'overflow-hidden px-3',
          isNarrow ? 'w-[72px]' : 'w-60',
        )}
      >
        <Brand isNarrow={isNarrow} />
        <nav aria-label="Разделы">
          {/* The reader drags sections into their own order; Alt with an arrow moves one too. */}
          <Reorder.Group
            axis="y"
            values={sections}
            onReorder={reorder}
            className="isolate flex flex-col gap-0.5"
          >
            {sections.map((item, index) => (
              <Reorder.Item
                key={item.to}
                value={item}
                onDragStart={() => {
                  wasDragged.current = true
                }}
                onDragEnd={letGo}
                onPointerDown={() => {
                  wasDragged.current = false
                }}
                onClickCapture={(event) => {
                  if (!wasDragged.current) return
                  event.preventDefault()
                  event.stopPropagation()
                  wasDragged.current = false
                }}
                onKeyDown={(event) => {
                  if (!event.altKey || (event.key !== 'ArrowUp' && event.key !== 'ArrowDown')) {
                    return
                  }
                  event.preventDefault()
                  const paths = sections.map((section) => section.to)
                  saveOrder(movedBy(paths, item.to, event.key === 'ArrowUp' ? -1 : 1))
                }}
                whileDrag={{ scale: 1.03, zIndex: 10 }}
                className={clsx(
                  'relative cursor-grab list-none rounded-xl active:cursor-grabbing',
                  index > 0 && sections[index - 1].group !== item.group && 'mt-3',
                )}
              >
                <SideItem item={item} active={item.to === active} isNarrow={isNarrow} />
              </Reorder.Item>
            ))}
          </Reorder.Group>
        </nav>
        <motion.div
          layout
          transition={{ duration: 0.3, ease: EASE }}
          className={clsx(
            'mt-auto flex items-center gap-2',
            isNarrow ? 'flex-col' : 'justify-between px-1',
          )}
        >
          <motion.div layout transition={{ duration: 0.3, ease: EASE }}>
            <AccountButton hasLabel={!isNarrow} />
          </motion.div>
          <motion.div
            layout
            transition={{ duration: 0.3, ease: EASE }}
            className={clsx('flex items-center gap-1', isNarrow && 'flex-col')}
          >
            <ThemeButton dark={dark} onToggle={toggleDark} />
            <button
              type="button"
              onClick={toggleNarrow}
              aria-label={isNarrow ? 'Развернуть меню' : 'Свернуть меню'}
              title={isNarrow ? 'Развернуть меню' : 'Свернуть меню'}
              className="button button--ghost button--icon-only button--md shrink-0 text-muted"
            >
              {isNarrow ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            </button>
          </motion.div>
        </motion.div>
      </aside>

      {/* Top app bar on phones. */}
      <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-separator bg-background/85 px-4 backdrop-blur md:hidden">
        <LogoMark size={30} />
        <Wordmark className="flex-1 text-lg" />
        {/* The bottom bar holds five sections; the others live up here. */}
        {topSections.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            aria-label={item.label}
            className={({ isActive }) =>
              clsx(
                'transition-colors hover:bg-default/70 relative grid size-10 shrink-0 place-items-center overflow-hidden rounded-full',
                isActive ? 'bg-default text-default-foreground' : 'text-muted',
              )
            }
          >
            <item.icon size={21} />
          </NavLink>
        ))}
        <ThemeButton dark={dark} onToggle={toggleDark} />
        <AccountButton />
      </header>

      <div
        className={clsx(
          'transition-[padding] duration-300 ease-out',
          isNarrow ? 'md:pl-[72px]' : 'md:pl-60',
        )}
      >
        <div className="mx-auto flex max-w-[1320px] gap-8 px-4 pt-6 pb-28 md:px-10 md:pt-9 md:pb-12">
          <main className="min-w-0 flex-1">
            {/* A soft fade between sections. Entrance only: an exit
                would keep the old wrapper alive while <Routes> inside it already
                renders the new page. Switching digests keeps the page mounted. */}
            <motion.div
              key={pageKey}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: DURATION.medium, ease: EASE }}
            >
              <EntranceContext value={entrance}>{children}</EntranceContext>
            </motion.div>
          </main>
        </div>
        {/* The model and the size of the base are the operator's business, not a reader's. */}
        {isAdmin && (
          <footer className="mx-auto hidden max-w-[1320px] px-10 pb-8 md:block">
            <StatusLine />
          </footer>
        )}
      </div>

      {/* Navigation bar on phones. */}
      <nav
        aria-label="Разделы"
        className="fixed inset-x-0 bottom-0 z-30 flex border-t border-separator bg-background/90 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      >
        {barSections.map((item) => (
          <BarItem key={item.to} item={item} active={item.to === active} />
        ))}
      </nav>
    </div>
  )
}
