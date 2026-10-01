import clsx from 'clsx'
import { useIsFetching, useIsMutating } from '@tanstack/react-query'
import {
  FileText,
  GitCompareArrows,
  Moon,
  Radar,
  Rss,
  Send,
  SlidersHorizontal,
  Sparkles,
  Sun,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router'
import { formatNumber, modelLabel } from '../lib/format'
import { useMe, useMeta } from '../lib/queries'
import { prefetchRoute } from '../routes'
import { DURATION, EASE } from './tokens'

type NavItem = { to: string; label: string; icon: LucideIcon; also?: string }

const NAV: NavItem[] = [
  { to: '/', label: 'Дайджест', icon: FileText, also: '/digests' },
  { to: '/feed', label: 'Для вас', icon: Sparkles },
  { to: '/profiles', label: 'Интересы', icon: SlidersHorizontal },
  { to: '/channels', label: 'Каналы', icon: Send },
  { to: '/sources', label: 'Источники', icon: Rss },
  { to: '/compare', label: 'Сравнение', icon: GitCompareArrows },
]

const THEME_KEY = 'radar-theme'

function initialTheme(): boolean {
  const stored = localStorage.getItem(THEME_KEY)
  if (stored) return stored === 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function useDarkMode(): [boolean, () => void] {
  const [dark, setDark] = useState(initialTheme)
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light')
  }, [dark])
  return [dark, () => setDark((value) => !value)]
}

/**
 * Material linear progress along the top while anything loads in the
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
      <p className="flex items-center gap-2 text-xs text-destructive">
        <span className="size-1.5 rounded-full bg-destructive" />
        API недоступен
      </p>
    )
  }
  if (!meta) return <div className="skeleton h-9 w-full" />
  const offline = meta.llm_provider !== 'ollama'
  return (
    <div className="space-y-1 text-xs text-muted-foreground">
      <p className="flex items-center gap-2">
        <span className={clsx('size-1.5 rounded-full', offline ? 'bg-spark' : 'bg-success')} />
        <span className="truncate" title={`Поиск: ${meta.embedding_model}`}>
          {offline ? 'Автономный режим' : modelLabel(meta.llm_model)}
        </span>
      </p>
      <p className="tabular pl-3.5 text-outline">
        {formatNumber(meta.articles)} публикаций · +{formatNumber(meta.articles_last_day)} за сутки
      </p>
    </div>
  )
}

function useSection(item: NavItem): boolean {
  const location = useLocation()
  return Boolean(item.also && location.pathname.startsWith(item.also))
}

/** Material navigation rail item: an icon in a pill indicator, the label under it. */
function RailItem({ item }: { item: NavItem }) {
  const isSection = useSection(item)
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      onPointerEnter={() => prefetchRoute(item.to)}
      onFocus={() => prefetchRoute(item.to)}
      aria-current={isSection ? 'page' : undefined}
      className="group flex w-full flex-col items-center gap-1 py-1 outline-none"
    >
      {({ isActive }) => {
        const active = isActive || isSection
        return (
          <>
            <span className="state-layer relative grid h-8 w-14 place-items-center overflow-hidden rounded-full text-on-surface-variant group-focus-visible:outline group-focus-visible:outline-2 group-focus-visible:outline-primary">
              {active && (
                <motion.span
                  layoutId="rail-indicator"
                  className="absolute inset-0 -z-10 rounded-full bg-secondary-container"
                  transition={{ type: 'spring', stiffness: 520, damping: 40 }}
                />
              )}
              <Icon
                size={20}
                strokeWidth={active ? 2.3 : 1.9}
                className={clsx('relative', active && 'text-on-secondary-container')}
              />
            </span>
            <span
              className={clsx(
                'text-[12px] leading-4 tracking-[0.02em]',
                active ? 'font-semibold text-on-surface' : 'font-medium text-on-surface-variant',
              )}
            >
              {item.label}
            </span>
          </>
        )
      }}
    </NavLink>
  )
}

/** Material navigation bar item for phones: the same pill, at the bottom. */
function BarItem({ item }: { item: NavItem }) {
  const isSection = useSection(item)
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      aria-label={item.label}
      aria-current={isSection ? 'page' : undefined}
      className="flex min-w-0 flex-1 flex-col items-center gap-1 pt-3 pb-4"
    >
      {({ isActive }) => {
        const active = isActive || isSection
        return (
          <>
            <span className="relative grid h-8 w-14 place-items-center">
              {active && (
                <motion.span
                  layoutId="bar-indicator"
                  className="absolute inset-0 rounded-full bg-secondary-container"
                  transition={{ type: 'spring', stiffness: 520, damping: 40 }}
                />
              )}
              <Icon
                size={20}
                className={clsx(
                  'relative',
                  active ? 'text-on-secondary-container' : 'text-on-surface-variant',
                )}
              />
            </span>
            <span
              className={clsx(
                'truncate text-[11px] leading-4',
                active ? 'font-semibold text-on-surface' : 'text-on-surface-variant',
              )}
            >
              {item.label}
            </span>
          </>
        )
      }}
    </NavLink>
  )
}

function AccountButton({ compact }: { compact?: boolean }) {
  const { data: me } = useMe()
  if (!me) return null
  return (
    <NavLink
      to="/account"
      onPointerEnter={() => prefetchRoute('/account')}
      aria-label={`Аккаунт: ${me.display_name}`}
      title={me.is_demo ? 'Демо-аккаунт' : me.email}
      className={({ isActive }) =>
        clsx(
          'grid size-10 place-items-center rounded-full text-sm font-semibold transition-shadow',
          isActive
            ? 'bg-primary text-primary-foreground shadow-elevation-1'
            : 'bg-tertiary-container text-on-tertiary-container hover:shadow-elevation-1',
          compact && 'size-9',
        )
      }
    >
      {me.display_name.slice(0, 1).toUpperCase()}
    </NavLink>
  )
}

function ThemeButton({ dark, onToggle }: { dark: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={dark ? 'Светлая тема' : 'Тёмная тема'}
      className="state-layer relative grid size-10 shrink-0 place-items-center overflow-hidden rounded-full text-on-surface-variant"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={dark ? 'moon' : 'sun'}
          initial={{ rotate: -90, scale: 0.6, opacity: 0 }}
          animate={{ rotate: 0, scale: 1, opacity: 1 }}
          exit={{ rotate: 90, scale: 0.6, opacity: 0 }}
          transition={{ duration: DURATION.short, ease: EASE }}
        >
          {dark ? <Moon size={19} /> : <Sun size={19} />}
        </motion.span>
      </AnimatePresence>
    </button>
  )
}

function Brand() {
  return (
    <span className="grid size-12 place-items-center rounded-2xl bg-primary-container text-on-primary-container">
      <Radar size={22} strokeWidth={2.2} />
    </span>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  const [dark, toggleDark] = useDarkMode()
  const location = useLocation()
  const section = location.pathname.split('/')[1] ?? ''

  return (
    <div className="min-h-dvh bg-background">
      <ActivityBar />

      {/* Navigation rail, from tablet width up. */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[92px] flex-col items-center gap-6 bg-surface-container-low py-5 md:flex">
        <Brand />
        <nav aria-label="Разделы" className="flex w-full flex-col items-center gap-3">
          {NAV.map((item) => (
            <RailItem key={item.to} item={item} />
          ))}
        </nav>
        <div className="mt-auto flex flex-col items-center gap-3">
          <ThemeButton dark={dark} onToggle={toggleDark} />
          <AccountButton />
        </div>
      </aside>

      {/* Top app bar on phones. */}
      <header className="sticky top-0 z-30 flex h-16 items-center gap-3 bg-surface-container/90 px-4 backdrop-blur md:hidden">
        <span className="grid size-9 place-items-center rounded-xl bg-primary-container text-on-primary-container">
          <Radar size={18} strokeWidth={2.2} />
        </span>
        <span className="flex-1 text-lg font-medium">Радар</span>
        {/* The bottom bar holds five sections; the sixth lives up here. */}
        <NavLink
          to="/compare"
          aria-label="Сравнение выпусков"
          className={({ isActive }) =>
            clsx(
              'state-layer relative grid size-10 shrink-0 place-items-center overflow-hidden rounded-full',
              isActive
                ? 'bg-secondary-container text-on-secondary-container'
                : 'text-on-surface-variant',
            )
          }
        >
          <GitCompareArrows size={19} />
        </NavLink>
        <ThemeButton dark={dark} onToggle={toggleDark} />
        <AccountButton compact />
      </header>

      <div className="md:pl-[92px]">
        <div className="mx-auto flex max-w-[1320px] gap-8 px-4 pt-6 pb-28 md:px-10 md:pt-9 md:pb-12">
          <main className="min-w-0 flex-1">
            {/* Material fade through between sections. Entrance only: an exit
                would keep the old wrapper alive while <Routes> inside it already
                renders the new page. Switching digests keeps the page mounted. */}
            <motion.div
              key={section === 'digests' ? '' : section}
              initial={{ opacity: 0, scale: 0.985, y: 6 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ duration: DURATION.medium, ease: EASE }}
            >
              {children}
            </motion.div>
          </main>
        </div>
        <footer className="mx-auto hidden max-w-[1320px] px-10 pb-8 md:block">
          <StatusLine />
        </footer>
      </div>

      {/* Navigation bar on phones. */}
      <nav
        aria-label="Разделы"
        className="fixed inset-x-0 bottom-0 z-30 flex bg-surface-container shadow-elevation-2 md:hidden"
      >
        {NAV.slice(0, 5).map((item) => (
          <BarItem key={item.to} item={item} />
        ))}
      </nav>
    </div>
  )
}
