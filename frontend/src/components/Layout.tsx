import clsx from 'clsx'
import { useIsFetching, useIsMutating } from '@tanstack/react-query'
import {
  Analytics,
  ChevronLeft,
  ChevronRight,
  CompareArrows,
  DynamicFeed,
  Moon,
  Newspaper,
  Rss,
  Send,
  SlidersHorizontal,
  Sun,
} from './icons'
import type { IconComponent } from './icons'
import { AnimatePresence, motion } from 'motion/react'
import { useLayoutEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { Link, NavLink, useLocation } from 'react-router'
import { formatNumber, modelLabel } from '../lib/format'
import { useMe, useMeta } from '../lib/queries'
import { prefetchRoute } from '../routes'
import { readOpen, writeOpen } from '../lib/remembered'
import { UserAvatar } from './UserAvatar'
import { LogoMark, Wordmark } from './Logo'
import { DURATION, EASE } from './tokens'
import { EntranceContext, newEntrance } from './entrance'
import { Skeleton } from './loading'

type NavItem = {
  to: string
  label: string
  icon: IconComponent
  also?: string[]
  isAdminOnly?: boolean
}

const NAV: NavItem[] = [
  { to: '/', label: 'Дайджест', icon: Newspaper, also: ['/digests', '/share'] },
  { to: '/feed', label: 'Для вас', icon: DynamicFeed },
  { to: '/profiles', label: 'Интересы', icon: SlidersHorizontal },
  { to: '/channels', label: 'Каналы', icon: Send },
  { to: '/sources', label: 'Источники', icon: Rss },
  { to: '/compare', label: 'Сравнение', icon: CompareArrows },
  { to: '/analytics', label: 'Аналитика', icon: Analytics, isAdminOnly: true },
]

const THEME_KEY = 'radar-theme'

function initialTheme(): boolean {
  const stored = localStorage.getItem(THEME_KEY)
  if (stored) return stored === 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function useDarkMode(): [boolean, (from: HTMLElement) => void] {
  const [dark, setDark] = useState(initialTheme)
  useLayoutEffect(() => {
    const root = document.documentElement
    // Every colour changes in one frame. With transitions on, text and chips
    // lagged behind the backgrounds, which change at once.
    root.classList.add('theme-switching')
    root.classList.toggle('dark', dark)
    void root.offsetHeight
    root.classList.remove('theme-switching')
    localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light')
  }, [dark])
  // The new theme grows as a circle out of the button that was pressed.
  const toggle = (from: HTMLElement) => {
    const flip = () => flushSync(() => setDark((value) => !value))
    if (!document.startViewTransition || matchMedia('(prefers-reduced-motion: reduce)').matches) {
      flip()
      return
    }
    const box = from.getBoundingClientRect()
    const x = box.left + box.width / 2
    const y = box.top + box.height / 2
    const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y))
    const transition = document.startViewTransition(flip)
    transition.ready
      .then(() => {
        document.documentElement.animate(
          {
            clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`],
          },
          {
            duration: DURATION.long * 1000,
            easing: `cubic-bezier(${EASE.join(', ')})`,
            pseudoElement: '::view-transition-new(root)',
          },
        )
      })
      // Skipped (another transition began): the theme has changed all the same.
      .catch(() => {})
  }
  return [dark, toggle]
}

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
  const offline = meta.llm_provider !== 'ollama'
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

function AccountButton() {
  const { data: me } = useMe()
  if (!me) return null
  return (
    <NavLink
      to="/account"
      onPointerEnter={() => prefetchRoute('/account')}
      aria-label={`Аккаунт: ${me.display_name}`}
      title={me.is_demo ? 'Временный аккаунт' : me.email}
      className={({ isActive }) =>
        clsx(
          'grid size-9 shrink-0 place-items-center rounded-full transition-shadow',
          // The picture keeps its colours; the ring says this is the open section.
          isActive
            ? 'ring-2 ring-accent ring-offset-2 ring-offset-background'
            : 'hover:ring-2 hover:ring-border',
        )
      }
    >
      {/* The size of the button: a bigger picture pushed the letters off centre. */}
      <UserAvatar me={me} size={36} />
    </NavLink>
  )
}

function ThemeButton({ dark, onToggle }: { dark: boolean; onToggle: (from: HTMLElement) => void }) {
  return (
    <button
      type="button"
      onClick={(event) => onToggle(event.currentTarget)}
      // The icon and the name both say where a press leads, not where one is.
      aria-label={dark ? 'Включить светлую тему' : 'Включить тёмную тему'}
      title={dark ? 'Включить светлую тему' : 'Включить тёмную тему'}
      className="button button--ghost button--icon-only button--md shrink-0 text-muted"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={dark ? 'sun' : 'moon'}
          initial={{ rotate: -90, scale: 0.6, opacity: 0 }}
          animate={{ rotate: 0, scale: 1, opacity: 1 }}
          exit={{ rotate: 90, scale: 0.6, opacity: 0 }}
          transition={{ duration: DURATION.short, ease: EASE }}
        >
          {dark ? <Sun size={19} /> : <Moon size={19} />}
        </motion.span>
      </AnimatePresence>
    </button>
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
  const sections = NAV.filter((item) => isAdmin || !item.isAdminOnly)
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
    <div className="min-h-dvh bg-background">
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
        <nav aria-label="Разделы" className="isolate flex flex-col gap-0.5">
          {sections.map((item) => (
            <SideItem key={item.to} item={item} active={item.to === active} isNarrow={isNarrow} />
          ))}
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
            <AccountButton />
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
        <NavLink
          to="/compare"
          aria-label="Сравнение выпусков"
          className={({ isActive }) =>
            clsx(
              'button button--ghost button--icon-only button--md shrink-0',
              isActive ? 'bg-default text-foreground' : 'text-muted',
            )
          }
        >
          <CompareArrows size={21} />
        </NavLink>
        {isAdmin && (
          <NavLink
            to="/analytics"
            aria-label="Аналитика"
            className={({ isActive }) =>
              clsx(
                'transition-colors hover:bg-default/70 relative grid size-10 shrink-0 place-items-center overflow-hidden rounded-full',
                isActive ? 'bg-default text-default-foreground' : 'text-muted',
              )
            }
          >
            <Analytics size={21} />
          </NavLink>
        )}
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
        {NAV.slice(0, 5).map((item) => (
          <BarItem key={item.to} item={item} active={item.to === active} />
        ))}
      </nav>
    </div>
  )
}
