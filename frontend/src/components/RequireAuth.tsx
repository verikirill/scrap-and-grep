import { LogoMark } from './Logo'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { useMe } from '../lib/queries'
import { Button, ErrorNote } from './ui'

/** Where the reader was heading when the sign-in page stopped them. */
export type AuthRedirect = { from?: string }

function Splash({ children }: { children?: ReactNode }) {
  return (
    <div className="grid min-h-dvh place-items-center px-6">
      <div className="flex flex-col items-center gap-4 text-center">
        <LogoMark size={56} className="animate-pulse" />
        {children}
      </div>
    </div>
  )
}

/**
 * Gate for everything behind sign-in. This only decides what to draw: the API
 * checks the session on every request, so nothing is protected by this file.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe()
  const location = useLocation()

  if (me.isPending) {
    return (
      <Splash>
        <div className="skeleton h-2 w-28" role="status" aria-label="Проверяем вход" />
      </Splash>
    )
  }
  if (me.isError) {
    return (
      <Splash>
        <ErrorNote error={me.error} />
        <Button onClick={() => void me.refetch()}>Повторить попытку</Button>
      </Splash>
    )
  }
  if (me.data === null) {
    const state: AuthRedirect = { from: location.pathname + location.search }
    return <Navigate to="/login" replace state={state} />
  }
  return children
}
