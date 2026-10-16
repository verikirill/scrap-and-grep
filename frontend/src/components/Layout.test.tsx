import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { setMediaQueries } from '../test/browser'
import { makeMe, makeMeta } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { Layout } from './Layout'

function renderLayout(route = '/feed') {
  return renderWithProviders(
    <Layout>
      <p>Страница</p>
    </Layout>,
    { route },
  )
}

/** The sidebar: in jsdom the phone's bottom bar is drawn too, with the same name. */
const sidebar = () => screen.getAllByRole('navigation', { name: 'Разделы' })[0]
const bottomBar = () => screen.getAllByRole('navigation', { name: 'Разделы' })[1]

/** The shell is drawn for the reader once their account button shows. */
const accountShown = () => screen.findAllByRole('link', { name: 'Аккаунт: Анна Петрова' })

function serveAdmin(overrides: Parameters<typeof makeMe>[0] = {}) {
  server.use(
    http.get(apiUrl('/auth/me'), () => HttpResponse.json(makeMe({ is_admin: true, ...overrides }))),
  )
}

describe('Layout', () => {
  afterEach(() => {
    document.documentElement.classList.remove('dark')
  })

  it.each([
    ['/digests/digest-7', 'Дайджест'],
    ['/share/k3Yp9', 'Дайджест'],
    ['/profiles', 'Интересы'],
  ])('marks the section of %s as open in both bars', async (route, section) => {
    renderLayout(route)
    await accountShown()
    expect(within(sidebar()).getByRole('link', { name: section })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(bottomBar()).getByRole('link', { name: section })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(sidebar()).getAllByRole('link', { current: 'page' })).toHaveLength(1)
  })

  it('shows analytics and the service status to an administrator only', async () => {
    serveAdmin()
    renderLayout()
    expect(await within(sidebar()).findByRole('link', { name: 'Аналитика' })).toBeInTheDocument()
    expect(await screen.findByText('Автономный режим')).toBeInTheDocument()
    expect(screen.getByText(/1\s200 публикаций · \+40 за сутки/)).toBeInTheDocument()
  })

  it('names the model in the status where one answers', async () => {
    serveAdmin()
    server.use(
      http.get(apiUrl('/meta'), () =>
        HttpResponse.json(makeMeta({ llm_provider: 'ollama', llm_model: 'ollama:qwen3:8b' })),
      ),
    )
    renderLayout()
    expect(await screen.findByText('qwen3:8b')).toBeInTheDocument()
  })

  it('names a model behind an OpenAI-compatible API instead of calling it offline', async () => {
    serveAdmin()
    server.use(
      http.get(apiUrl('/meta'), () =>
        HttpResponse.json(
          makeMeta({ llm_provider: 'openai', llm_model: 'qwen3.6-35b-a3b/latest' }),
        ),
      ),
    )
    renderLayout()
    expect(await screen.findByText('qwen3.6-35b-a3b')).toBeInTheDocument()
    expect(screen.queryByText('Автономный режим')).toBeNull()
  })

  it('says when the API does not answer', async () => {
    serveAdmin()
    server.use(http.get(apiUrl('/meta'), () => HttpResponse.json(null, { status: 500 })))
    renderLayout()
    expect(await screen.findByText('API недоступен')).toBeInTheDocument()
  })

  it('hides analytics from a guest, even one with the administrator flag, and from a reader', async () => {
    serveAdmin({ is_demo: true })
    const { unmount } = renderLayout()
    await accountShown()
    expect(within(sidebar()).queryByRole('link', { name: 'Аналитика' })).toBeNull()
    expect(screen.queryByText('Автономный режим')).toBeNull()
    unmount()

    server.resetHandlers()
    renderLayout()
    await accountShown()
    expect(within(sidebar()).queryByRole('link', { name: 'Аналитика' })).toBeNull()
  })

  it('shows each kind of account its own sections, reading first and running last', async () => {
    const company = (role: 'owner' | 'member') => ({
      company: 'Энергосеть',
      team: role === 'member' ? 'SOC' : null,
      role,
      job_title: null,
      manager: null,
    })
    const reading = ['Дайджест', 'Для вас', 'Интересы', 'Источники', 'Сравнение']
    const cases = [
      ['a reader on their own', makeMe(), [...reading, 'Каналы']],
      [
        'the manager of a space',
        makeMe({ company: company('owner') }),
        [...reading, 'Каналы', 'Компания'],
      ],
      ['a person a company added', makeMe({ company: company('member') }), reading],
      [
        'the administrator',
        makeMe({ is_admin: true }),
        [...reading, 'Каналы', 'Компания', 'Аналитика'],
      ],
      ['a guest', makeMe({ is_demo: true }), [...reading, 'Каналы']],
    ] as const
    for (const [, me, sections] of cases) {
      server.use(http.get(apiUrl('/auth/me'), () => HttpResponse.json(me)))
      const { unmount } = renderLayout()
      await accountShown()
      const names = within(sidebar())
        .getAllByRole('link')
        .map((link) => link.textContent)
        .filter((name) => name !== 'Scrap&Grep' && !name?.startsWith('Анна'))
      expect(names).toEqual(sections)
      // The phone keeps reading at the bottom and the running sections up top.
      expect(
        within(bottomBar())
          .getAllByRole('link')
          .map((link) => link.textContent),
      ).toEqual(reading)
      unmount()
    }
  })

  it('folds the sidebar to icons named by their sections, and keeps it folded', async () => {
    const { user, unmount } = renderLayout()
    await accountShown()
    await user.click(screen.getByRole('button', { name: 'Свернуть меню' }))

    const feed = within(sidebar()).getByRole('link', { name: 'Для вас' })
    expect(feed).toHaveAttribute('aria-label', 'Для вас')
    expect(screen.getByRole('button', { name: 'Развернуть меню' })).toBeInTheDocument()
    unmount()

    renderLayout()
    await accountShown()
    expect(screen.getByRole('button', { name: 'Развернуть меню' })).toBeInTheDocument()
  })

  it('takes the reader to their account from the avatar', async () => {
    const { user } = renderLayout()
    const [account] = await accountShown()
    await user.click(account)
    expect(screen.getByTestId('location')).toHaveTextContent('/account')
  })

  it('shows a bar along the top while something loads', async () => {
    let answer: () => void = () => {}
    const answered = new Promise<void>((resolve) => (answer = resolve))
    server.use(
      http.get(apiUrl('/auth/me'), async () => {
        await answered
        return HttpResponse.json(makeMe())
      }),
    )
    renderLayout()
    expect(await screen.findByRole('progressbar', { name: 'Загрузка' })).toBeInTheDocument()

    answer()

    await accountShown()
    await waitFor(() => expect(screen.queryByRole('progressbar')).toBeNull())
  })
})

describe('Layout account', () => {
  it('names the reader’s picture in the open menu and keeps only the picture when folded', async () => {
    const { user } = renderLayout()
    await accountShown()
    expect(screen.getByText('Профиль')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Свернуть меню' }))

    await waitFor(() => expect(screen.queryByText('Профиль')).toBeNull())
  })
})

describe('Layout theme', () => {
  afterEach(() => {
    document.documentElement.classList.remove('dark', 'theme-fading', 'theme-sweeping')
    Reflect.deleteProperty(document, 'startViewTransition')
  })

  it('starts dark where the system is dark, and the reader’s choice is kept', async () => {
    setMediaQueries({ '(prefers-color-scheme: dark)': true })
    const { user } = renderLayout()
    await accountShown()
    expect(document.documentElement).toHaveClass('dark')

    const [toggle] = screen.getAllByRole('button', { name: 'Включить светлую тему' })
    await user.click(toggle)

    expect(document.documentElement).not.toHaveClass('dark')
    expect(localStorage.getItem('radar-theme')).toBe('light')
    expect(screen.getAllByRole('button', { name: 'Включить тёмную тему' })).toHaveLength(2)
  })

  it('follows the stored choice over the system', async () => {
    localStorage.setItem('radar-theme', 'dark')
    setMediaQueries({ '(prefers-color-scheme: dark)': false })
    renderLayout()
    await accountShown()
    expect(document.documentElement).toHaveClass('dark')
  })

  it('sweeps the new theme over the old from corner to corner where the browser can', async () => {
    setMediaQueries({ '(prefers-reduced-motion: reduce)': false })
    let done = () => {}
    const finished = new Promise<void>((resolve) => {
      done = resolve
    })
    Object.defineProperty(document, 'startViewTransition', {
      configurable: true,
      value: (update: () => void) => {
        update()
        return { finished }
      },
    })
    const { user } = renderLayout()
    await accountShown()

    const [toggle] = screen.getAllByRole('button', { name: 'Включить тёмную тему' })
    await user.click(toggle)

    // While the transition runs the stylesheet sweeps the new picture in.
    expect(document.documentElement).toHaveClass('dark')
    expect(document.documentElement).toHaveClass('theme-sweeping')
    // The browser moves the pictures: the elements themselves do not ease.
    expect(document.documentElement).not.toHaveClass('theme-fading')

    done()
    await waitFor(() => expect(document.documentElement).not.toHaveClass('theme-sweeping'))
  })

  it('eases the colours of every element for a moment where view transitions are missing', async () => {
    setMediaQueries({ '(prefers-reduced-motion: reduce)': false })
    const { user } = renderLayout()
    await accountShown()
    // The first paint takes the theme at once.
    expect(document.documentElement).not.toHaveClass('theme-fading')

    await user.click(screen.getAllByRole('button', { name: 'Включить тёмную тему' })[0])

    expect(document.documentElement).toHaveClass('dark')
    expect(document.documentElement).toHaveClass('theme-fading')
    // Once the fade is over the elements get their own transitions back.
    await waitFor(() => expect(document.documentElement).not.toHaveClass('theme-fading'))
    expect(document.documentElement).toHaveClass('dark')
  })

  it('switches at once for a reader who turned motion down', async () => {
    setMediaQueries({ '(prefers-reduced-motion: reduce)': true })
    const startViewTransition = vi.fn()
    Object.defineProperty(document, 'startViewTransition', {
      configurable: true,
      value: startViewTransition,
    })
    const { user } = renderLayout()
    await accountShown()

    await user.click(screen.getAllByRole('button', { name: 'Включить тёмную тему' })[0])

    expect(document.documentElement).toHaveClass('dark')
    expect(startViewTransition).not.toHaveBeenCalled()
    expect(document.documentElement).not.toHaveClass('theme-fading')
  })
})

describe('Layout menu order', () => {
  it('lists the sections in the reader’s order and moves one with Alt and an arrow', async () => {
    let saved: string[] | null = null
    server.use(
      http.get(apiUrl('/auth/me'), () =>
        HttpResponse.json(makeMe({ nav_order: saved ?? ['/sources', '/', '/feed'] })),
      ),
      http.patch(apiUrl('/auth/me/settings'), async ({ request }) => {
        saved = ((await request.json()) as { nav_order: string[] }).nav_order
        return HttpResponse.json({
          feed_view: 'cards',
          feed_order: 'new',
          folded_sections: [],
          nav_order: saved,
        })
      }),
    )
    const { user } = renderLayout()
    await accountShown()

    const names = () =>
      within(sidebar())
        .getAllByRole('link')
        .map((link) => link.textContent)
    // Placed sections first, as placed; the rest follow in the app's own order.
    expect(names().slice(0, 5)).toEqual([
      'Источники',
      'Дайджест',
      'Для вас',
      'Интересы',
      'Сравнение',
    ])

    within(sidebar()).getByRole('link', { name: 'Дайджест' }).focus()
    await user.keyboard('{Alt>}{ArrowUp}{/Alt}')

    await waitFor(() => expect(saved?.slice(0, 3)).toEqual(['/', '/sources', '/feed']))
    await waitFor(() => expect(names()[0]).toBe('Дайджест'))
  })
})
