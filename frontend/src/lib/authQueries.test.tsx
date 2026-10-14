// Who is signed in: the session hooks of lib/queries.ts against the API.
import { act, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { makeMe, makeMeta, makeProfile, makeUser } from '../test/fixtures'
import { renderHookWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { keys, useMe, useSignIn, useSignOut } from './queries'

const guest = makeMe({ id: 'guest-7', display_name: 'Гость', is_demo: true })

/**
 * A server where a visitor has no session until they sign in, sign out or
 * enter as a guest; it records the guests it made.
 */
function serveSessions({ signInRequired }: { signInRequired: boolean }) {
  let current: ReturnType<typeof makeMe> | null = null
  const guestsMade: string[] = []
  server.use(
    http.get(apiUrl('/meta'), () =>
      HttpResponse.json(makeMeta({ sign_in_required: signInRequired })),
    ),
    http.get(apiUrl('/auth/me'), () => HttpResponse.json(current)),
    http.post(apiUrl('/auth/demo'), () => {
      current = guest
      guestsMade.push(guest.id)
      return HttpResponse.json(makeUser({ id: guest.id, is_demo: true }))
    }),
    http.post(apiUrl('/auth/login'), () => {
      current = makeMe()
      return HttpResponse.json(makeUser())
    }),
    http.post(apiUrl('/auth/logout'), () => {
      current = null
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return { guestsMade, signIn: (me: ReturnType<typeof makeMe>) => (current = me) }
}

function useSession() {
  return { me: useMe(), signIn: useSignIn(), signOut: useSignOut() }
}

describe('useMe', () => {
  it('makes a visitor a guest at once where the server needs no sign-in', async () => {
    const { guestsMade } = serveSessions({ signInRequired: false })
    const { result } = renderHookWithProviders(() => useMe())

    await waitFor(() => expect(result.current.data).toEqual(guest))
    expect(guestsMade).toEqual(['guest-7'])
  })

  it('leaves a visitor signed out where the server asks for sign-in', async () => {
    const { guestsMade } = serveSessions({ signInRequired: true })
    const { result } = renderHookWithProviders(() => useMe())

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toBeNull()
    expect(guestsMade).toEqual([])
  })

  it('answers nobody when making a guest fails, so the sign-in page shows', async () => {
    serveSessions({ signInRequired: false })
    server.use(
      http.post(apiUrl('/auth/demo'), () =>
        HttpResponse.json({ detail: 'Гостевой вход выключен' }, { status: 403 }),
      ),
    )
    const { result } = renderHookWithProviders(() => useMe())

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toBeNull()
  })

  it('drops what was cached for the previous reader when another tab signed in as someone else', async () => {
    const session = serveSessions({ signInRequired: true })
    session.signIn(makeMe())
    const { result, client } = renderHookWithProviders(() => useMe())
    await waitFor(() => expect(result.current.data?.id).toBe('user-1'))
    client.setQueryData(keys.profiles, [makeProfile()])

    session.signIn(makeMe({ id: 'user-2', display_name: 'Олег' }))
    await act(() => result.current.refetch())

    await waitFor(() => expect(result.current.data?.id).toBe('user-2'))
    expect(client.getQueryData(keys.profiles)).toBeUndefined()
  })
})

describe('useSignIn and useSignOut', () => {
  it('signs in, dropping what was cached for nobody', async () => {
    serveSessions({ signInRequired: true })
    const { result, client } = renderHookWithProviders(useSession)
    await waitFor(() => expect(result.current.me.isSuccess).toBe(true))
    client.setQueryData(keys.profiles, [makeProfile()])

    await act(() =>
      result.current.signIn.login.mutateAsync({ email: 'analyst@example.ru', password: 'x' }),
    )

    await waitFor(() => expect(result.current.me.data?.id).toBe('user-1'))
    expect(client.getQueryData(keys.profiles)).toBeUndefined()
  })

  it('fails loudly when the browser did not keep the session cookie', async () => {
    serveSessions({ signInRequired: true })
    // The server accepts the password, but the next request comes without a session.
    server.use(http.post(apiUrl('/auth/login'), () => HttpResponse.json(makeUser())))
    const { result } = renderHookWithProviders(useSession)
    await waitFor(() => expect(result.current.me.isSuccess).toBe(true))

    await act(async () => {
      await result.current.signIn.login
        .mutateAsync({ email: 'analyst@example.ru', password: 'x' })
        .catch(() => {})
    })

    await waitFor(() =>
      expect(result.current.signIn.login.error?.message).toBe(
        'Не удалось войти, потому что браузер заблокировал cookie сессии.',
      ),
    )
  })

  it('signs out for good: no guest is made behind the reader’s back afterwards', async () => {
    const session = serveSessions({ signInRequired: false })
    session.signIn(makeMe())
    const { result, client } = renderHookWithProviders(useSession)
    await waitFor(() => expect(result.current.me.data?.id).toBe('user-1'))
    client.setQueryData(keys.profiles, [makeProfile()])

    await act(() => result.current.signOut.logout.mutateAsync())

    await waitFor(() => expect(result.current.me.data).toBeNull())
    expect(client.getQueryData(keys.profiles)).toBeUndefined()
    // Asked again (a focus, a reload of the tab): still nobody, and no guest.
    const again = await act(() => result.current.me.refetch())
    expect(again.data).toBeNull()
    expect(session.guestsMade).toEqual([])
  })

  it('lets a reader who signed out enter as a guest on purpose', async () => {
    const session = serveSessions({ signInRequired: false })
    session.signIn(makeMe())
    const { result } = renderHookWithProviders(useSession)
    await waitFor(() => expect(result.current.me.data?.id).toBe('user-1'))
    await act(() => result.current.signOut.logout.mutateAsync())

    await act(() => result.current.signIn.demo.mutateAsync())

    await waitFor(() => expect(result.current.me.data).toEqual(guest))
    // The purposeful sign-out is forgotten: a later visit becomes a guest again.
    expect(sessionStorage.getItem('radar-signed-out')).toBeNull()
  })
})
