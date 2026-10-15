import { screen, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { setMediaQueries } from '../test/browser'
import { makeMe, makeMeta } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { AuthPage } from './AuthPage'

/** A server with no session until the reader signs in or registers. */
function serveSession({ meta = makeMeta() } = {}) {
  let isSignedIn = false
  const sent: { url: string; body: unknown }[] = []
  const signIn = async ({ request }: { request: Request }) => {
    sent.push({ url: new URL(request.url).pathname, body: await request.json() })
    isSignedIn = true
    return HttpResponse.json(makeMe())
  }
  server.use(
    http.get(apiUrl('/meta'), () => HttpResponse.json(meta)),
    http.get(apiUrl('/auth/me'), () => HttpResponse.json(isSignedIn ? makeMe() : null)),
    http.post(apiUrl('/auth/login'), signIn),
    http.post(apiUrl('/auth/register'), signIn),
    http.post(apiUrl('/auth/demo'), async ({ request }) => {
      sent.push({ url: new URL(request.url).pathname, body: null })
      isSignedIn = true
      return HttpResponse.json(makeMe({ is_demo: true }))
    }),
    http.post(apiUrl('/auth/preset/:account'), ({ request }) => {
      sent.push({ url: new URL(request.url).pathname, body: null })
      isSignedIn = true
      return HttpResponse.json(makeMe({ is_shared: true }))
    }),
  )
  return sent
}

const withGuests = () => makeMeta({ demo_login: true })

const location = () => screen.getByTestId('location').textContent

describe('AuthPage', () => {
  it('signs in and returns the reader to the page the guard stopped them at', async () => {
    const sent = serveSession()
    const { user } = renderWithProviders(<AuthPage mode="login" />, {
      route: { pathname: '/login', state: { from: '/feed?tab=top' } },
      path: '/login',
    })
    await user.type(await screen.findByLabelText('Почта'), 'analyst@example.ru')
    await user.type(screen.getByLabelText('Пароль'), 'correct horse')
    await user.click(screen.getByRole('button', { name: 'Войти' }))

    await waitFor(() => expect(location()).toBe('/feed?tab=top'))
    expect(sent).toEqual([
      {
        url: '/api/v1/auth/login',
        body: { email: 'analyst@example.ru', password: 'correct horse' },
      },
    ])
  })

  it.each(['//evil.example/feed', 'https://evil.example/', '/\\evil.example'])(
    'never follows %s to another site after signing in',
    async (from) => {
      serveSession()
      const { user } = renderWithProviders(<AuthPage mode="login" />, {
        route: { pathname: '/login', state: { from } },
        path: '/login',
      })
      await user.type(await screen.findByLabelText('Почта'), 'analyst@example.ru')
      await user.type(screen.getByLabelText('Пароль'), 'correct horse')
      await user.click(screen.getByRole('button', { name: 'Войти' }))
      await waitFor(() => expect(location()).toBe('/'))
    },
  )

  it('shows the server’s answer to a wrong password and stays on the form', async () => {
    serveSession()
    server.use(
      http.post(apiUrl('/auth/login'), () =>
        HttpResponse.json({ detail: 'Неверная почта или пароль' }, { status: 401 }),
      ),
    )
    const { user } = renderWithProviders(<AuthPage mode="login" />, {
      route: '/login',
      path: '/login',
    })
    await user.type(await screen.findByLabelText('Почта'), 'analyst@example.ru')
    await user.type(screen.getByLabelText('Пароль'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Войти' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Неверная почта или пароль')
    expect(location()).toBe('/login')
  })

  it('takes a new reader to the introduction after registration', async () => {
    const sent = serveSession()
    const { user } = renderWithProviders(<AuthPage mode="register" />, {
      route: '/register',
      path: '/register',
    })
    expect(await screen.findByText('не короче 10 символов')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Как к вам обращаться'), 'Анна')
    await user.type(screen.getByLabelText('Почта'), 'anna@example.ru')
    await user.type(screen.getByLabelText(/Пароль/), 'long enough pass')
    await user.click(screen.getByRole('button', { name: 'Зарегистрироваться' }))

    await waitFor(() => expect(location()).toBe('/start'))
    expect(sent[0]).toEqual({
      url: '/api/v1/auth/register',
      body: { email: 'anna@example.ru', password: 'long enough pass', display_name: 'Анна' },
    })
  })

  it('does not let a reader register where registration is closed', async () => {
    serveSession({ meta: makeMeta({ registration_open: false }) })
    renderWithProviders(<AuthPage mode="register" />, { route: '/register', path: '/register' })
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Зарегистрироваться' })).toBeDisabled(),
    )
  })

  it('shows the password on request', async () => {
    serveSession()
    const { user } = renderWithProviders(<AuthPage mode="login" />, {
      route: '/login',
      path: '/login',
    })
    const password = await screen.findByLabelText('Пароль')
    expect(password).toHaveAttribute('type', 'password')
    await user.click(screen.getByRole('button', { name: 'Показать пароль' }))
    expect(password).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Показать пароль' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('enters as a guest without registration and goes where the reader was heading', async () => {
    const sent = serveSession({ meta: withGuests() })
    const { user } = renderWithProviders(<AuthPage mode="login" />, {
      route: { pathname: '/login', state: { from: '/sources' } },
      path: '/login',
    })
    expect(await screen.findByText(/Временный аккаунт с примерами профилей/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Войти без регистрации' }))

    await waitFor(() => expect(location()).toBe('/sources'))
    expect(sent).toEqual([{ url: '/api/v1/auth/demo', body: null }])
  })

  it('offers no guest entry where the server has none, and shows why a guest entry failed', async () => {
    serveSession({ meta: makeMeta({ demo_login: false }) })
    const { unmount } = renderWithProviders(<AuthPage mode="login" />, {
      route: '/login',
      path: '/login',
    })
    expect(await screen.findByRole('button', { name: 'Войти' })).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Войти без регистрации' })).toBeNull(),
    )
    unmount()

    serveSession({ meta: withGuests() })
    server.use(
      http.post(apiUrl('/auth/demo'), () =>
        HttpResponse.json({ detail: 'Гостевых мест не осталось' }, { status: 429 }),
      ),
    )
    const { user } = renderWithProviders(<AuthPage mode="login" />, {
      route: '/login',
      path: '/login',
    })
    await user.click(await screen.findByRole('button', { name: 'Войти без регистрации' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Гостевых мест не осталось')
    expect(location()).toBe('/login')
  })

  it('sends a reader who is already signed in on at once', async () => {
    server.use(http.get(apiUrl('/auth/me'), () => HttpResponse.json(makeMe())))
    renderWithProviders(<AuthPage mode="login" />, {
      route: { pathname: '/login', state: { from: '/profiles' } },
      path: '/login',
    })
    await waitFor(() => expect(location()).toBe('/profiles'))
  })

  it('tells a reader with a shared profile link what happens, also on the way to registration', async () => {
    serveSession()
    const { user } = renderWithProviders(
      <Routes>
        <Route path="/login" element={<AuthPage mode="login" />} />
        <Route path="/register" element={<AuthPage mode="register" />} />
      </Routes>,
      { route: { pathname: '/login', state: { from: '/share/k3Yp9' } } },
    )
    expect(await screen.findByText(/С вами поделились профилем интересов/)).toBeInTheDocument()

    // Switching to registration keeps where the reader came from.
    await user.click(screen.getByRole('link', { name: 'Регистрация' }))
    expect(location()).toBe('/register')
    expect(await screen.findByLabelText('Как к вам обращаться')).toBeInTheDocument()
    expect(screen.getByText(/С вами поделились профилем интересов/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Регистрация' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('takes a new reader with a shared profile to it instead of the resume step', async () => {
    serveSession()
    const { user } = renderWithProviders(<AuthPage mode="register" />, {
      route: { pathname: '/register', state: { from: '/share/k3Yp9' } },
      path: '/register',
    })
    await user.type(await screen.findByLabelText('Как к вам обращаться'), 'Анна')
    await user.type(screen.getByLabelText('Почта'), 'anna@example.ru')
    await user.type(screen.getByLabelText(/Пароль/), 'long enough pass')
    await user.click(screen.getByRole('button', { name: 'Зарегистрироваться' }))

    await waitFor(() => expect(location()).toBe('/share/k3Yp9'))
  })

  it('draws the streaming headlines beside the form on a wide screen only', async () => {
    serveSession()
    const { unmount } = renderWithProviders(<AuthPage mode="login" />, {
      route: '/login',
      path: '/login',
    })
    await screen.findByRole('button', { name: 'Войти' })
    expect(screen.queryByText(/tail -f news/)).toBeNull()
    unmount()

    setMediaQueries({ '(min-width: 1024px)': true })
    renderWithProviders(<AuthPage mode="login" />, { route: '/login', path: '/login' })
    expect(await screen.findByText(/tail -f news/)).toBeInTheDocument()
    expect(screen.getByText('SIMATIC')).toBeInTheDocument()
    await screen.findByRole('button', { name: /Войти как читатель/ })
  })

  it('enters a shared account with one click and skips the introduction', async () => {
    const sent = serveSession()
    const { user } = renderWithProviders(<AuthPage mode="login" />, {
      route: { pathname: '/login', state: { from: '/feed' } },
      path: '/login',
    })
    expect(await screen.findByRole('button', { name: /Войти как читатель/ })).toBeInTheDocument()
    expect(screen.getByText(/изменения в них видят все/)).toBeInTheDocument()
    // The guest button is off on a stack with the defaults.
    expect(screen.queryByRole('button', { name: 'Войти без регистрации' })).toBeNull()

    await user.click(screen.getByRole('button', { name: /Войти как аналитик/ }))

    await waitFor(() => expect(location()).toBe('/feed'))
    expect(sent).toEqual([{ url: '/api/v1/auth/preset/analyst', body: null }])
  })

  it('shows why a one-click entry failed, and offers none where the server has it off', async () => {
    serveSession()
    server.use(
      http.post(apiUrl('/auth/preset/:account'), () =>
        HttpResponse.json({ detail: 'Вход в общие аккаунты отключён.' }, { status: 404 }),
      ),
    )
    const { user, unmount } = renderWithProviders(<AuthPage mode="login" />, {
      route: '/login',
      path: '/login',
    })
    await user.click(await screen.findByRole('button', { name: /Войти как читатель/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Вход в общие аккаунты отключён.')
    expect(location()).toBe('/login')
    unmount()

    serveSession({ meta: makeMeta({ preset_login: false }) })
    renderWithProviders(<AuthPage mode="login" />, { route: '/login', path: '/login' })
    expect(await screen.findByRole('button', { name: 'Войти' })).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /Войти как читатель/ })).toBeNull(),
    )
  })

  it('greets with the searching cat on both the sign-in and the registration form', async () => {
    serveSession()
    for (const mode of ['login', 'register'] as const) {
      const { container, unmount } = renderWithProviders(<AuthPage mode={mode} />, {
        route: `/${mode}`,
        path: `/${mode}`,
      })
      await screen.findByLabelText('Почта')
      // Decorative: the form is what the page says, not the picture.
      expect(container.querySelector('.brand-cat')).toHaveAttribute('data-pose', 'search')
      expect(container.querySelector('.brand-cat')).toHaveAttribute('aria-hidden', 'true')
      unmount()
    }
  })

  it('keeps the registration form free of the one-click entries', async () => {
    // The guest button tells that the server's answer is in.
    serveSession({ meta: withGuests() })
    renderWithProviders(<AuthPage mode="register" />, { route: '/register', path: '/register' })
    expect(await screen.findByRole('button', { name: 'Войти без регистрации' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Войти как читатель/ })).toBeNull()
  })
})
