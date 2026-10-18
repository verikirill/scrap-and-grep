import { cn } from '../lib/utils'
import clsx from 'clsx'
import { Eye, EyeOff } from '../components/icons'
import { LogoMark, Wordmark } from '../components/Logo'
import { motion } from 'motion/react'
import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation } from 'react-router'
import type { AuthRedirect } from '../components/RequireAuth'
import { EASE, INPUT_CLASS } from '../components/tokens'
import { Button, ErrorNote, Field } from '../components/ui'
import { SharedAccounts } from '../features/auth/SharedAccounts'
import { AuthAside } from '../features/auth/AuthAside'
import { ONBOARDING_PATH } from '../lib/onboarding'
import { useMe, useMeta, useSignIn } from '../lib/queries'
import { SlidingPill } from '../components/SlidingPill'
import { useMediaQuery } from '../lib/useMediaQuery'
import { useDarkMode } from '../lib/useDarkMode'
import { ThemeButton } from '../components/ThemeToggle'

const PASSWORD_MIN = 10

const TABS = [
  { mode: 'login', to: '/login', label: 'Вход' },
  { mode: 'register', to: '/register', label: 'Регистрация' },
] as const

type Props = {
  mode: 'login' | 'register'
}

/** Only in-app paths are followed after sign-in, never an address from outside. */
function safeTarget(state: unknown): string {
  const from = (state as AuthRedirect | null)?.from
  if (!from) return '/'
  try {
    // Parsing, not prefix checks: "/\\host" and similar tricks resolve to
    // another origin here and are refused.
    const url = new URL(from, window.location.origin)
    return url.origin === window.location.origin ? url.pathname + url.search : '/'
  } catch {
    return '/'
  }
}

export function AuthPage({ mode }: Props) {
  const tabRow = useRef<HTMLElement>(null)
  const me = useMe()
  const meta = useMeta()
  const location = useLocation()
  const { login, register, demo, shared } = useSignIn()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [isPasswordShown, setIsPasswordShown] = useState(false)
  const isWide = useMediaQuery('(min-width: 1024px)')
  const [dark, toggleDark] = useDarkMode()

  const isRegister = mode === 'register'
  const target = safeTarget(location.state)
  const pending = login.isPending || register.isPending || demo.isPending || shared.isPending
  const error = (isRegister ? register.error : login.error) ?? demo.error ?? shared.error

  // Someone sent a profile: after signing in the reader decides about it,
  // even a new one, who otherwise starts with the introduction.
  const isSharedProfile = target.startsWith('/share/')
  if (me.data && !pending) {
    return (
      <Navigate to={register.isSuccess && !isSharedProfile ? ONBOARDING_PATH : target} replace />
    )
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (isRegister) register.mutate({ email, password, displayName })
    else login.mutate({ email, password })
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <AuthAside isWide={isWide} />

      <main className="relative isolate flex items-center justify-center overflow-hidden px-5 py-10 short:py-6 shorter:py-4 lg:px-16">
        <div className="absolute top-4 right-4 z-10">
          <ThemeButton dark={dark} onToggle={toggleDark} />
        </div>
        <div aria-hidden className="auth-ripple hidden lg:block">
          <span />
          <span />
          <span />
        </div>
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: EASE }}
          className="w-full max-w-sm rounded-3xl lg:max-w-md lg:bg-surface lg:p-10 lg:shadow-surface lg:short:p-8 lg:shorter:p-6"
        >
          <div className="mb-8 flex items-center gap-2.5 short:mb-5 lg:hidden">
            <LogoMark size={36} />
            <Wordmark className="text-[17px]" />
          </div>

          <h1 className="text-2xl font-semibold tracking-tight">
            {isRegister ? 'Новый аккаунт' : 'Вход'}
          </h1>
          {/* On a very short window the plain greeting gives way; a shared
              profile's note stays, it says what happens after signing in. */}
          <p className={clsx('mt-1 text-sm text-muted', !isSharedProfile && 'shorter:hidden')}>
            {isSharedProfile
              ? 'С вами поделились профилем интересов. Он откроется после входа или регистрации, и вы решите, добавлять ли его себе.'
              : isRegister
                ? 'После регистрации можно загрузить резюме, и по нему соберётся профиль интересов.'
                : 'Войдите, чтобы открыть персональную ленту и выпуски.'}
          </p>

          <nav
            ref={tabRow}
            aria-label="Вход или регистрация"
            className="relative isolate mt-6 inline-flex gap-1 rounded-xl bg-surface-secondary p-1 short:mt-5 shorter:mt-4"
          >
            <SlidingPill
              container={tabRow}
              activeKey={mode}
              className="rounded-lg bg-surface shadow-surface"
            />
            {TABS.map((tab) => (
              <Link
                key={tab.mode}
                to={tab.to}
                state={location.state}
                replace
                aria-current={tab.mode === mode ? 'page' : undefined}
                data-active={tab.mode === mode}
                className={clsx(
                  'relative rounded-lg px-4 py-1.5 text-sm font-medium transition-colors',
                  tab.mode === mode ? 'text-foreground' : 'text-muted hover:text-foreground',
                )}
              >
                <span className="relative">{tab.label}</span>
              </Link>
            ))}
          </nav>

          <form
            onSubmit={submit}
            className="mt-6 space-y-4 short:mt-5 shorter:mt-4 shorter:space-y-3"
          >
            {isRegister && (
              <Field label="Как к вам обращаться">
                <input
                  required
                  minLength={2}
                  maxLength={80}
                  autoComplete="name"
                  className={INPUT_CLASS}
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                />
              </Field>
            )}
            <Field label="Почта">
              <input
                required
                type="email"
                maxLength={254}
                autoComplete="email"
                className={INPUT_CLASS}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>
            {/* The toggle sits next to the label, not inside it: a button within
                a <label> would become part of the field's name. */}
            <div className="relative">
              <Field
                label="Пароль"
                hint={isRegister ? `не короче ${PASSWORD_MIN} символов` : undefined}
              >
                <input
                  required
                  type={isPasswordShown ? 'text' : 'password'}
                  minLength={isRegister ? PASSWORD_MIN : undefined}
                  maxLength={128}
                  autoComplete={isRegister ? 'new-password' : 'current-password'}
                  className={cn(INPUT_CLASS, 'pr-10')}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </Field>
              <button
                type="button"
                onClick={() => setIsPasswordShown((value) => !value)}
                aria-label="Показать пароль"
                aria-pressed={isPasswordShown}
                className="absolute right-0 bottom-0 grid h-[38px] w-10 place-items-center rounded-lg text-muted hover:text-foreground"
              >
                {isPasswordShown ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            <ErrorNote error={error} />

            <Button
              type="submit"
              variant="cta"
              className="w-full"
              isBusy={login.isPending || register.isPending}
              disabled={pending || (isRegister && meta.data?.registration_open === false)}
            >
              {isRegister ? 'Зарегистрироваться' : 'Войти'}
            </Button>
          </form>

          {!isRegister && meta.data?.preset_login && (
            <SharedAccounts
              busyKey={shared.isPending ? (shared.variables ?? null) : null}
              isDisabled={pending}
              onEnter={(account) => shared.mutate(account)}
            />
          )}

          {meta.data?.demo_login && (
            <div className="mt-6 border-t border-separator pt-5 short:mt-5 short:pt-4 shorter:mt-4">
              <Button
                className="w-full"
                isBusy={demo.isPending}
                disabled={pending}
                onClick={() => demo.mutate()}
              >
                Войти без регистрации
              </Button>
              <p className="mt-2 text-center text-xs text-muted">
                Временный аккаунт с примерами профилей. Доступен только вам и удалится через 24
                часа.
              </p>
            </div>
          )}
        </motion.div>
      </main>
    </div>
  )
}
