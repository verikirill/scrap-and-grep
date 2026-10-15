import { motion } from 'motion/react'
import { useState } from 'react'
import { Link, Navigate, useParams } from 'react-router'
import { Eye, EyeOff, Target } from '../components/icons'
import { LogoMark, Wordmark } from '../components/Logo'
import { EASE, INPUT_CLASS } from '../components/tokens'
import { Button, Chip, ErrorNote, ErrorState, Field, Spinner } from '../components/ui'
import { AuthAside } from '../features/auth/AuthAside'
import type { Invite } from '../lib/company'
import { useInvite } from '../lib/companyQueries'
import { ONBOARDING_PATH } from '../lib/onboarding'
import { useSignIn } from '../lib/queries'
import { useMediaQuery } from '../lib/useMediaQuery'
import { cn } from '../lib/utils'

const PASSWORD_MIN = 10

const capitalized = (text: string) => text.slice(0, 1).toUpperCase() + text.slice(1)

/** "Олег Петров пригласил вас в команду «SOC» компании «Энергосеть»." */
function inviteLine(invite: Invite): string {
  const where = `в команду «${invite.team}» компании «${invite.company}»`
  return invite.manager ? `${invite.manager} приглашает вас ${where}.` : `Вас приглашают ${where}.`
}

function InviteForm({ token, invite }: { token: string; invite: Invite }) {
  const { invite: accept } = useSignIn()
  const [password, setPassword] = useState('')
  const [isShown, setIsShown] = useState(false)

  if (accept.isSuccess) return <Navigate to={ONBOARDING_PATH} replace />

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Здравствуйте, {invite.display_name}</h1>
      <p className="mt-1 text-sm text-muted">{inviteLine(invite)}</p>

      <section aria-label="Уже настроено" className="mt-6 rounded-2xl bg-surface-secondary p-4">
        <p className="flex items-center gap-2 text-sm font-semibold">
          <Target size={16} className="text-accent" />
          Профиль интересов уже настроен
        </p>
        <p className="mt-1 text-xs text-muted">
          {invite.job_title ? `${capitalized(invite.job_title)}. ` : ''}
          {invite.audience === 'management'
            ? 'Выпуски придут кратким брифингом для руководителя.'
            : 'Выпуски придут карточками с деталями по каждой новости.'}
        </p>
        {invite.interests.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {invite.interests.map((title) => (
              <Chip key={title} tone="accent">
                {title}
              </Chip>
            ))}
          </div>
        )}
      </section>

      <form
        className="mt-6 space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          accept.mutate({ token, password })
        }}
      >
        {/* For password managers: they save the new password under this address. */}
        <input
          type="email"
          name="username"
          autoComplete="username"
          value={invite.email}
          readOnly
          hidden
        />
        <p className="text-sm">
          <span className="text-muted">Вход по почте </span>
          <span className="font-medium break-all">{invite.email}</span>
        </p>
        <div className="relative">
          <Field label="Придумайте пароль" hint={`не короче ${PASSWORD_MIN} символов`}>
            <input
              required
              autoFocus
              type={isShown ? 'text' : 'password'}
              minLength={PASSWORD_MIN}
              maxLength={128}
              autoComplete="new-password"
              className={cn(INPUT_CLASS, 'pr-10')}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>
          <button
            type="button"
            onClick={() => setIsShown((value) => !value)}
            aria-label="Показать пароль"
            aria-pressed={isShown}
            className="absolute right-0 bottom-0 grid h-[38px] w-10 place-items-center rounded-lg text-muted hover:text-foreground"
          >
            {isShown ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
        <ErrorNote error={accept.error} />
        <Button
          type="submit"
          variant="cta"
          className="w-full"
          isBusy={accept.isPending}
          disabled={password.length < PASSWORD_MIN}
        >
          Задать пароль и войти
        </Button>
      </form>
    </>
  )
}

/**
 * Where a person a company added comes in: who invited them, what is already
 * set up, and one field for the password. Nothing else to fill in.
 */
export function InvitePage() {
  const { token = '' } = useParams()
  const invite = useInvite(token)
  const isWide = useMediaQuery('(min-width: 1024px)')

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <AuthAside isWide={isWide} />
      <main className="relative isolate flex items-center justify-center overflow-hidden px-5 py-10 lg:px-16">
        <div aria-hidden className="auth-ripple hidden lg:block">
          <span />
          <span />
          <span />
        </div>
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: EASE }}
          className="w-full max-w-sm rounded-3xl lg:max-w-md lg:bg-surface lg:p-10 lg:shadow-surface"
        >
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <LogoMark size={36} />
            <Wordmark className="text-[17px]" />
          </div>
          {invite.data ? (
            <InviteForm token={token} invite={invite.data} />
          ) : invite.error ? (
            <ErrorState
              title="Приглашение не открылось"
              error={invite.error}
              className="px-0"
              action={
                <Link to="/login" className="button button--secondary button--md">
                  Ко входу
                </Link>
              }
            />
          ) : (
            <div className="grid place-items-center py-16">
              <Spinner label="Открываем приглашение" className="size-6 text-muted" />
            </div>
          )}
        </motion.div>
      </main>
    </div>
  )
}
