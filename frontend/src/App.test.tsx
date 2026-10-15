// The whole app as main.tsx mounts it: the routes, the sign-in guard, the
// navigation shell and lazily loaded pages, with a fresh query client per test.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { createQueryClient } from './lib/queryClient'
import {
  makeAnalytics,
  makeArticleRead,
  makeDigest,
  makeMe,
  makeParagraphBlock,
  makeProfile,
  makeResume,
  makeSchedule,
  makeSharedProfile,
  makeSummary,
  makeUser,
} from './test/fixtures'
import { apiUrl, server } from './test/server'

// A section whose code is gone from the server, as after a new release.
vi.mock('./pages/ChannelsPage', () => {
  throw new Error('Failed to fetch dynamically imported module: /assets/ChannelsPage.js')
})

// The first import of a page transforms its code: done once, outside the tests' time.
beforeAll(async () => {
  await Promise.all([
    import('./pages/AnalyticsPage'),
    import('./pages/ArticlePage'),
    import('./pages/ComparePage'),
    import('./pages/SharePage'),
    import('./pages/WelcomePage'),
  ])
}, 60_000)

beforeEach(() => {
  // The browser is never idle here: a page loads when a test opens it, not in
  // the background of the next test.
  vi.stubGlobal('requestIdleCallback', () => 0)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

/** Open the app at an address, as typed into the browser. */
function openApp(address: string) {
  window.history.replaceState(null, '', address)
  const user = userEvent.setup()
  render(<App client={createQueryClient()} />)
  return { user }
}

/**
 * The sidebar: in jsdom the phone's bottom bar is drawn too, with the same name.
 * Under an open dialog the page is hidden from a screen reader: hidden: true.
 */
const sidebar = ({ hidden = false } = {}) =>
  screen.getAllByRole('navigation', { name: 'Разделы', hidden })[0]

/**
 * A reader with one profile, built on weekdays, and no digests yet: the digest
 * and comparison pages have nothing to show.
 */
function serveNoDigests() {
  server.use(
    http.get(apiUrl('/profiles'), () => HttpResponse.json([makeProfile()])),
    http.get(apiUrl('/digests'), () => HttpResponse.json([])),
    http.get(apiUrl('/digest-schedules'), () => HttpResponse.json([makeSchedule()])),
  )
}

/** The digest page has loaded when the profile card names its schedule, the last request. */
async function digestPageLoaded({ hidden = false } = {}) {
  const profile = await screen.findByRole(
    'radio',
    { name: /Инженер АСУ ТП/, hidden },
    { timeout: 5000 },
  )
  await within(profile).findByText('по будням в 09:00')
}

// A whole page loads in each test: more than the default five seconds under a full run.
describe('App', { timeout: 15_000 }, () => {
  it('opens a section by its address inside the navigation shell', async () => {
    serveNoDigests()
    openApp('/compare')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Сравнение' }, { timeout: 5000 }),
    ).toBeInTheDocument()
    expect(await screen.findByText('Нужно два готовых выпуска')).toBeInTheDocument()
    expect(within(sidebar()).getByRole('link', { name: 'Сравнение' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('opens an issue by its address, not the latest one', async () => {
    serveNoDigests()
    server.use(
      http.get(apiUrl('/digests'), () =>
        HttpResponse.json([
          makeSummary({ id: 'digest-2', title: 'Выпуск за неделю', status: 'failed' }),
          makeSummary({ id: 'digest-1', title: 'Выпуск за сутки', status: 'failed' }),
        ]),
      ),
      http.get(apiUrl('/digests/digest-1'), () =>
        HttpResponse.json(
          makeDigest({ title: 'Выпуск за сутки', status: 'failed', error: 'Модель не ответила' }),
        ),
      ),
    )
    openApp('/digests/digest-1')

    expect(await screen.findByText('Модель не ответила', {}, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Выпуск за сутки' })).toBeInTheDocument()
    await digestPageLoaded()
    expect(within(sidebar()).getByRole('link', { name: 'Дайджест' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('opens an article by its address', async () => {
    const article = makeArticleRead({ id: 4321, blocks: [makeParagraphBlock()] })
    server.use(http.get(apiUrl('/articles/4321'), () => HttpResponse.json(article)))
    openApp('/articles/4321')

    expect(
      await screen.findByRole('heading', { level: 1, name: article.title }, { timeout: 5000 }),
    ).toBeInTheDocument()
  })

  it('opens a shared profile over the digest page', async () => {
    serveNoDigests()
    server.use(
      http.get(apiUrl('/shared-profiles/k3Yp9'), () => HttpResponse.json(makeSharedProfile())),
    )
    openApp('/share/k3Yp9')

    expect(
      await screen.findByRole('dialog', { name: /Защита подстанций/ }, { timeout: 5000 }),
    ).toBeInTheDocument()
    await digestPageLoaded({ hidden: true })
    expect(
      within(sidebar({ hidden: true })).getByRole('link', { name: 'Дайджест', hidden: true }),
    ).toHaveAttribute('aria-current', 'page')
  })

  it('opens analytics for an administrator', async () => {
    server.use(
      http.get(apiUrl('/auth/me'), () => HttpResponse.json(makeMe({ is_admin: true }))),
      http.get(apiUrl('/analytics/overview'), () =>
        HttpResponse.json(makeAnalytics({ enabled: false })),
      ),
    )
    openApp('/analytics')

    expect(await screen.findByText('События выключены', {}, { timeout: 5000 })).toBeInTheDocument()
    expect(within(sidebar()).getByRole('link', { name: 'Аналитика' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('says an unknown address has no page, inside the shell, and leads home', async () => {
    serveNoDigests()
    const { user } = openApp('/no-such-section')

    const main = await screen.findByRole('main', {}, { timeout: 5000 })
    expect(
      await within(main).findByRole('heading', { level: 1, name: 'Такой страницы нет' }),
    ).toBeInTheDocument()
    expect(within(main).getByText('404')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/no-such-section')
    expect(sidebar()).toBeInTheDocument()

    await user.click(within(main).getByRole('button', { name: 'На главную' }))
    await digestPageLoaded()
    expect(screen.getByText('Выпусков пока нет')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')
    expect(within(sidebar()).getByRole('link', { name: 'Дайджест' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('asks a visitor without a session to sign in, then opens the section they came for', async () => {
    serveNoDigests()
    let isSignedIn = false
    server.use(
      http.get(apiUrl('/auth/me'), () => HttpResponse.json(isSignedIn ? makeMe() : null)),
      http.post(apiUrl('/auth/login'), () => {
        isSignedIn = true
        return HttpResponse.json(makeUser())
      }),
    )
    const { user } = openApp('/compare')

    expect(
      await screen.findByRole('heading', { name: 'Вход' }, { timeout: 5000 }),
    ).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')
    expect(screen.queryByRole('navigation', { name: 'Разделы' })).toBeNull()

    await user.type(screen.getByLabelText('Почта'), 'analyst@example.ru')
    await user.type(screen.getByLabelText('Пароль'), 'correct horse')
    await user.click(screen.getByRole('button', { name: 'Войти' }))
    expect(await screen.findByText('Нужно два готовых выпуска')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/compare')
  })

  it('takes the reader to sign in when any request finds the session over, and back after', async () => {
    serveNoDigests()
    server.use(
      http.get(
        apiUrl('/digests'),
        () => HttpResponse.json({ detail: 'Требуется вход' }, { status: 401 }),
        { once: true },
      ),
      http.post(apiUrl('/auth/login'), () => HttpResponse.json(makeUser())),
    )
    // Asked who is signed in, the server would still name the reader: the 401
    // alone is what ends the session on screen.
    const { user } = openApp('/compare')

    expect(
      await screen.findByRole('heading', { name: 'Вход' }, { timeout: 5000 }),
    ).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')

    await user.type(screen.getByLabelText('Почта'), 'analyst@example.ru')
    await user.type(screen.getByLabelText('Пароль'), 'correct horse')
    await user.click(screen.getByRole('button', { name: 'Войти' }))
    expect(await screen.findByText('Нужно два готовых выпуска')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/compare')
  })

  it('takes the reader to the sign-in page when an action finds the session over', async () => {
    serveNoDigests()
    server.use(
      http.post(apiUrl('/digests'), () =>
        HttpResponse.json({ detail: 'Требуется вход' }, { status: 401 }),
      ),
    )
    const { user } = openApp('/')
    await digestPageLoaded()
    await user.click(screen.getByRole('button', { name: 'Собрать выпуск' }))

    expect(await screen.findByRole('heading', { name: 'Вход' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')
  })

  it('keeps the reader signed in when a request is refused for another reason', async () => {
    serveNoDigests()
    server.use(
      http.get(apiUrl('/profiles'), () =>
        HttpResponse.json({ detail: 'Профили временно недоступны' }, { status: 403 }),
      ),
    )
    openApp('/')

    expect(await screen.findByRole('alert', {}, { timeout: 5000 })).toHaveTextContent(
      'Профили временно недоступны',
    )
    expect(await screen.findByText('Выпусков пока нет')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')
    expect(within(sidebar()).getByRole('link', { name: 'Дайджест' })).toBeInTheDocument()
  })

  it('shows a way out in place of a section that failed to load and leaves it behind on the next one', async () => {
    // React reports the error it caught; the page shows it instead.
    vi.spyOn(console, 'error').mockImplementation(() => {})
    serveNoDigests()
    const { user } = openApp('/channels')

    const main = await screen.findByRole('main', {}, { timeout: 5000 })
    expect(await within(main).findByRole('alert')).toHaveTextContent('Что-то сломалось')
    expect(within(sidebar()).getByRole('link', { name: 'Каналы' })).toHaveAttribute(
      'aria-current',
      'page',
    )

    await user.click(within(sidebar()).getByRole('link', { name: 'Сравнение' }))
    expect(await screen.findByText('Нужно два готовых выпуска')).toBeInTheDocument()
    expect(within(screen.getByRole('main')).queryByRole('alert')).toBeNull()
  })

  it('opens the resume step on a page of its own, outside the navigation shell', async () => {
    server.use(http.get(apiUrl('/resume'), () => HttpResponse.json(makeResume())))
    openApp('/welcome')

    expect(
      await screen.findByRole(
        'heading',
        { level: 1, name: 'Анна Петрова, расскажите о своей работе' },
        { timeout: 5000 },
      ),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: 'Создать профиль и открыть ленту' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Разделы' })).toBeNull()
  })

  it('asks a visitor without a session to sign in before the resume step', async () => {
    server.use(http.get(apiUrl('/auth/me'), () => HttpResponse.json(null)))
    openApp('/welcome')

    expect(
      await screen.findByRole('heading', { name: 'Вход' }, { timeout: 5000 }),
    ).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')
  })
})
