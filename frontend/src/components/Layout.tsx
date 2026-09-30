import clsx from 'clsx'
import {
  FileText,
  GitCompareArrows,
  Moon,
  Radar,
  Rss,
  SlidersHorizontal,
  Sparkles,
  Sun,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router'
import { formatNumber, modelLabel } from '../lib/format'
import { useMe, useMeta } from '../lib/queries'
import { EASE } from './tokens'

const NAV = [
  { to: '/', label: 'Дайджест', icon: FileText, also: '/digests' },
  { to: '/feed', label: 'Для вас', icon: Sparkles },
  { to: '/profiles', label: 'Интересы', icon: SlidersHorizontal },
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
  if (!meta) return <div className="skeleton h-9 w-full" />
  const offline = meta.llm_provider !== 'ollama'
  return (
    <div className="space-y-1 text-xs text-muted">
      <p className="flex items-center gap-2">
        <span className={clsx('size-1.5 rounded-full', offline ? 'bg-spark' : 'bg-ok')} />
        <span className="truncate" title={`Поиск: ${meta.embedding_model}`}>
          {offline ? 'Автономный режим' : modelLabel(meta.llm_model)}
        </span>
      </p>
      <p className="tabular pl-3.5 text-faint">
        {formatNumber(meta.articles)} публикаций · +{formatNumber(meta.articles_last_day)} за сутки
      </p>
    </div>
  )
}

function AccountLink() {
  const { data: me } = useMe()
  if (!me) return null
  return (
    <NavLink
      to="/account"
      aria-label={`Аккаунт: ${me.display_name}`}
      className={({ isActive }) =>
        clsx(
          'flex shrink-0 items-center gap-2.5 rounded-lg p-1 transition-colors md:px-2 md:py-1.5',
          isActive ? 'bg-accent-soft text-accent-text' : 'text-text hover:bg-sunken',
        )
      }
    >
      <span
        aria-hidden
        className="grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent-text"
      >
        {me.display_name.slice(0, 1).toUpperCase()}
      </span>
      <span className="hidden min-w-0 leading-tight md:block">
        <span className="block truncate text-[13px] font-medium">{me.display_name}</span>
        <span className="block truncate text-[11px] text-faint">
          {me.is_demo ? 'демо-аккаунт' : me.email}
        </span>
      </span>
    </NavLink>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  const [dark, toggleDark] = useDarkMode()
  const location = useLocation()
  const section = location.pathname.split('/')[1] ?? ''

  return (
    <div className="mx-auto flex min-h-dvh max-w-[1400px] flex-col md:flex-row">
      <aside className="sticky top-0 z-20 flex shrink-0 items-center gap-2 border-b border-line bg-bg/85 px-4 py-3 backdrop-blur md:h-dvh md:w-60 md:flex-col md:items-stretch md:gap-0 md:border-r md:border-b-0 md:px-4 md:py-6">
        <div className="flex items-center gap-2.5 md:mb-8 md:px-2">
          <span className="grid size-8 place-items-center rounded-xl bg-accent text-white dark:text-[#0b0f17]">
            <Radar size={18} strokeWidth={2.2} />
          </span>
          <span className="hidden leading-tight sm:block">
            <span className="block text-[15px] font-semibold tracking-tight">Радар</span>
            <span className="block text-[11px] text-faint">дайджесты ИТ и ИБ</span>
          </span>
        </div>

        <nav className="flex flex-1 items-center gap-1 overflow-x-auto md:flex-none md:flex-col md:items-stretch md:overflow-visible">
          {NAV.map(({ to, label, icon: Icon, also }) => {
            // A digest opened by id lives under /digests but belongs to the first tab.
            const isSection = Boolean(also && location.pathname.startsWith(also))
            return (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                // The text label is hidden on narrow screens; the name must not be.
                aria-label={label}
                aria-current={isSection ? 'page' : undefined}
                className={({ isActive }) =>
                  clsx(
                    'relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive || isSection ? 'text-accent-text' : 'text-muted hover:text-text',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {(isActive || isSection) && (
                      <motion.span
                        layoutId="nav-active"
                        className="absolute inset-0 rounded-lg bg-accent-soft"
                        transition={{ type: 'spring', stiffness: 480, damping: 38 }}
                      />
                    )}
                    <Icon size={17} className="relative shrink-0" />
                    <span className="relative hidden sm:inline">{label}</span>
                  </>
                )}
              </NavLink>
            )
          })}
        </nav>

        <div className="hidden md:mt-auto md:block md:px-2">
          <StatusLine />
        </div>
        <div className="md:mt-4">
          <AccountLink />
        </div>
        <button
          type="button"
          onClick={toggleDark}
          aria-label={dark ? 'Светлая тема' : 'Тёмная тема'}
          className="grid size-9 shrink-0 place-items-center rounded-lg text-muted transition-colors hover:bg-sunken hover:text-text md:mt-2 md:ml-0.5"
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={dark ? 'moon' : 'sun'}
              initial={{ rotate: -60, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: 60, opacity: 0 }}
              transition={{ duration: 0.18 }}
            >
              {dark ? <Moon size={17} /> : <Sun size={17} />}
            </motion.span>
          </AnimatePresence>
        </button>
      </aside>

      <main className="min-w-0 flex-1 px-4 py-6 md:px-10 md:py-9">
        {/* Entrance only. An exit animation would keep the old wrapper alive
            while <Routes> inside it already renders the new page. Switching
            between digests keeps the page mounted; only a change of section
            replays the entrance. */}
        <motion.div
          key={section === 'digests' ? '' : section}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: EASE }}
        >
          {children}
        </motion.div>
      </main>
    </div>
  )
}
