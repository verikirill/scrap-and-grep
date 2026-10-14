import { screen, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DetectResult, SourceCreate } from '../../lib/api'
import {
  makeDetectJob,
  makeDetectResult,
  makeDetectedSource,
  makeSource,
} from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { DetectSourceForm } from './DetectSourceForm'

type Check = { address: string; link_selector: string | null }

const PENDING: DetectResult = { status: 'pending', found: null, error: null }

/**
 * Fake timers that user-event can work under. Testing Library waits for a zero
 * timeout after every user action and advances it only for a runner named jest.
 */
function useFakeClock() {
  vi.useFakeTimers()
  vi.stubGlobal('jest', { advanceTimersByTime: (ms: number) => vi.advanceTimersByTime(ms) })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

/**
 * The detector: every check gets an id of its own, and the worker's answer to
 * an id comes from `answer`, asked once per poll.
 */
function serveDetection(answer: (poll: number) => DetectResult) {
  const checks: Check[] = []
  let polls = 0
  server.use(
    http.post(apiUrl('/sources/detect'), async ({ request }) => {
      checks.push((await request.json()) as Check)
      return HttpResponse.json(makeDetectJob({ request_id: `check${checks.length}` }), {
        status: 202,
      })
    }),
    http.get(apiUrl('/sources/detect/:requestId'), () => {
      polls += 1
      return HttpResponse.json(answer(polls))
    }),
  )
  return { checks, polls: () => polls }
}

/** The catalogue taking a new source: what was sent, in order. */
function serveCreate() {
  const created: SourceCreate[] = []
  server.use(
    http.post(apiUrl('/sources'), async ({ request }) => {
      const body = (await request.json()) as SourceCreate
      created.push(body)
      return HttpResponse.json(makeSource({ id: 7, name: body.name ?? 'Новый', can_edit: true }), {
        status: 201,
      })
    }),
  )
  return created
}

function renderForm(options: Parameters<typeof renderWithProviders>[1] = {}) {
  const onDone = vi.fn()
  const onAdded = vi.fn()
  const view = renderWithProviders(<DetectSourceForm onDone={onDone} onAdded={onAdded} />, options)
  return { ...view, onDone, onAdded }
}

const addressBox = () => screen.getByRole('textbox', { name: /^Адрес/ })
const checkButton = () => screen.getByRole('button', { name: 'Проверить' })
const nameBox = () => screen.getByRole('textbox', { name: 'Название' })

describe('DetectSourceForm', () => {
  it('asks for the answer every second and a half while the worker looks, and stops once it is done', async () => {
    useFakeClock()
    const detector = serveDetection((poll) => (poll < 3 ? PENDING : makeDetectResult()))
    serveCreate()
    const { user, onDone } = renderForm({
      userOptions: { advanceTimers: vi.advanceTimersByTime },
    })

    await user.type(addressBox(), 'habr.com/ru/hubs/scada')
    await user.click(checkButton())

    await vi.waitFor(() => expect(detector.polls()).toBe(1))
    expect(screen.getByRole('status')).toHaveTextContent(/^Ищем RSS-ленту, новости и статьи/)
    expect(checkButton()).toHaveAttribute('aria-busy', 'true')

    await vi.advanceTimersByTimeAsync(1500)
    await vi.waitFor(() => expect(detector.polls()).toBe(2))
    expect(screen.queryByRole('textbox', { name: 'Название' })).toBeNull()

    await vi.advanceTimersByTimeAsync(1500)
    await vi.waitFor(() => expect(nameBox()).toHaveValue('Хабр: SCADA'))
    expect(screen.queryByRole('status')).toBeNull()
    expect(checkButton()).not.toHaveAttribute('aria-busy')

    // A minute later nobody has asked again; the add is there to wait for.
    await vi.advanceTimersByTimeAsync(60_000)
    await user.click(screen.getByRole('button', { name: 'Добавить и опросить' }))
    await vi.waitFor(() => expect(onDone).toHaveBeenCalledOnce())
    expect(detector.polls()).toBe(3)
  })

  it('adds the feed it found under the name and category the reader chose', async () => {
    const detector = serveDetection(() => makeDetectResult())
    const created = serveCreate()
    const { user, onAdded, onDone } = renderForm()

    await user.type(addressBox(), '  habr.com/ru/hubs/scada ')
    await user.click(checkButton())

    expect(await screen.findByText('Лента RSS или Atom')).toBeInTheDocument()
    expect(detector.checks).toEqual([{ address: 'habr.com/ru/hubs/scada', link_selector: null }])
    expect(
      screen.getByText('https://habr.com/ru/rss/hubs/scada/articles/all/?fl=ru'),
    ).toBeInTheDocument()
    // The latest articles show what the source would bring, with their dates.
    expect(
      screen.getByRole('link', {
        name: 'Как мы сегментировали технологическую сеть подстанции без её остановки',
      }),
    ).toHaveAttribute('href', 'https://habr.com/ru/articles/851204/')
    expect(screen.getByText('13 окт.')).toBeInTheDocument()
    expect(screen.getByText('11 окт.')).toBeInTheDocument()

    await user.clear(nameBox())
    await user.type(nameBox(), '  Хабр: защита АСУ ТП ')
    await user.click(screen.getByRole('button', { name: /Категория/ }))
    await user.click(await screen.findByRole('option', { name: 'АСУ ТП' }))
    await user.click(screen.getByRole('button', { name: 'Добавить и опросить' }))

    await waitFor(() => expect(onDone).toHaveBeenCalledOnce())
    expect(onAdded).toHaveBeenCalledOnce()
    expect(created).toEqual([
      {
        kind: 'rss',
        name: 'Хабр: защита АСУ ТП',
        feed_url: 'https://habr.com/ru/rss/hubs/scada/articles/all/?fl=ru',
        category: 'ics',
        language: 'ru',
        fetch_full_text: false,
      },
    ])
  })

  it('adds a channel it found with the articles its posts point to', async () => {
    serveDetection(() =>
      makeDetectResult({
        found: makeDetectedSource({
          kind: 'telegram',
          address: '@true_secator',
          name: 'SecAtor',
          site_url: 'https://t.me/true_secator',
          samples: [],
        }),
      }),
    )
    const created = serveCreate()
    const { user, onDone } = renderForm()

    await user.type(addressBox(), 't.me/true_secator')
    await user.click(checkButton())
    expect(await screen.findByText('Telegram-канал')).toBeInTheDocument()
    expect(screen.queryByText('Последние статьи')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Добавить и опросить' }))

    await waitFor(() => expect(onDone).toHaveBeenCalledOnce())
    expect(created).toEqual([
      {
        kind: 'telegram',
        channel: '@true_secator',
        name: 'SecAtor',
        category: 'security',
        language: 'ru',
        fetch_full_text: true,
      },
    ])
  })

  it('adds a news page with its site and link selector, and says how a protected site is read', async () => {
    const note = 'Сайт рисует список статей скриптом.'
    serveDetection(() =>
      makeDetectResult({
        found: makeDetectedSource({
          kind: 'page',
          address: 'https://www.cisa.gov/news-events/cybersecurity-advisories',
          name: 'CISA Advisories',
          site_url: 'https://www.cisa.gov',
          language: 'en',
          link_selector: 'article h3 a',
          fetch_method: 'browser',
          fetch_note: note,
        }),
      }),
    )
    const created = serveCreate()
    const { user, onDone } = renderForm()

    await user.type(addressBox(), 'cisa.gov/news-events/cybersecurity-advisories')
    await user.click(checkButton())

    expect(await screen.findByText('Веб-страница без RSS')).toBeInTheDocument()
    // The step of the ladder, and on hover what it does and why this site needed it.
    expect(screen.getByText('Браузер')).toHaveAttribute(
      'title',
      expect.stringMatching(
        /^Страница открывается в настоящем браузере[^]*Сайт рисует список статей скриптом\.$/,
      ),
    )
    await user.click(screen.getByRole('button', { name: 'Добавить и опросить' }))

    await waitFor(() => expect(onDone).toHaveBeenCalledOnce())
    expect(created).toEqual([
      {
        kind: 'page',
        name: 'CISA Advisories',
        feed_url: 'https://www.cisa.gov/news-events/cybersecurity-advisories',
        site_url: 'https://www.cisa.gov',
        link_selector: 'article h3 a',
        category: 'security',
        language: 'en',
        fetch_full_text: false,
      },
    ])
  })

  it('adds a WordPress API without a site or selector it did not find, in Russian unless English', async () => {
    serveDetection(() =>
      makeDetectResult({
        found: makeDetectedSource({
          kind: 'wordpress',
          address: 'https://energybase.ru/wp-json/wp/v2/posts',
          name: 'Energybase',
          site_url: null,
          language: 'uk',
          link_selector: null,
        }),
      }),
    )
    const created = serveCreate()
    const { user, onDone } = renderForm()

    await user.type(addressBox(), 'energybase.ru')
    await user.click(checkButton())
    expect(await screen.findByText('WordPress API')).toBeInTheDocument()
    expect(screen.queryByText('Браузер')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Добавить и опросить' }))

    await waitFor(() => expect(onDone).toHaveBeenCalledOnce())
    expect(created).toEqual([
      {
        kind: 'wordpress',
        name: 'Energybase',
        feed_url: 'https://energybase.ru/wp-json/wp/v2/posts',
        category: 'security',
        language: 'ru',
        fetch_full_text: false,
      },
    ])
  })

  it('sends the link selector the reader gave', async () => {
    const detector = serveDetection(() => makeDetectResult())
    const { user } = renderForm()

    await user.click(screen.getByRole('button', { name: 'Указать селектор ссылок' }))
    await user.type(screen.getByRole('textbox', { name: /^CSS-селектор ссылок/ }), ' article h2 a ')
    await user.type(addressBox(), 'habr.com/ru/hubs/scada')
    await user.click(checkButton())

    expect(await screen.findByText('Лента RSS или Atom')).toBeInTheDocument()
    expect(detector.checks).toEqual([
      { address: 'habr.com/ru/hubs/scada', link_selector: 'article h2 a' },
    ])
  })

  it('shows a sample by its address when it has no title, and links only to web addresses', async () => {
    serveDetection(() =>
      makeDetectResult({
        found: makeDetectedSource({
          samples: [
            { title: '', url: 'https://habr.com/ru/articles/851300/', published_at: null },
            {
              title: 'Ссылка со скриптом',
              url: 'javascript:alert(document.cookie)',
              published_at: '2026-10-12T09:00:00Z',
            },
          ],
        }),
      }),
    )
    const { user } = renderForm()

    await user.type(addressBox(), 'habr.com/ru/hubs/scada')
    await user.click(checkButton())

    expect(
      await screen.findByRole('link', { name: 'https://habr.com/ru/articles/851300/' }),
    ).toHaveAttribute('href', 'https://habr.com/ru/articles/851300/')
    expect(screen.getByText('Ссылка со скриптом')).not.toHaveAttribute('href')
    expect(screen.queryByRole('link', { name: 'Ссылка со скриптом' })).toBeNull()
    expect(screen.getByText('12 окт.')).toBeInTheDocument()
  })

  it('says what the worker could not read and offers nothing to add', async () => {
    serveDetection(() =>
      makeDetectResult({ found: null, error: 'По адресу нет ни ленты, ни списка статей.' }),
    )
    const { user, onDone } = renderForm()

    await user.type(addressBox(), 'example.org')
    await user.click(checkButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'По адресу нет ни ленты, ни списка статей.',
    )
    expect(screen.queryByRole('button', { name: 'Добавить и опросить' })).toBeNull()
    expect(checkButton()).toBeEnabled()
    await user.click(screen.getByRole('button', { name: 'Отмена' }))
    expect(onDone).toHaveBeenCalledOnce()
  })

  it('shows why a check could not start', async () => {
    server.use(
      http.post(apiUrl('/sources/detect'), () =>
        HttpResponse.json({ detail: 'Слишком много проверок, подождите минуту.' }, { status: 429 }),
      ),
    )
    const { user } = renderForm()

    await user.type(addressBox(), 'habr.com')
    await user.click(checkButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Слишком много проверок, подождите минуту.',
    )
    expect(screen.queryByRole('status')).toBeNull()
    expect(checkButton()).toBeEnabled()
  })

  it('stops waiting and says so when the answer cannot be fetched', async () => {
    server.use(
      http.post(apiUrl('/sources/detect'), () => HttpResponse.json(makeDetectJob())),
      http.get(apiUrl('/sources/detect/:requestId'), () =>
        HttpResponse.json({ detail: 'Проверка не найдена.' }, { status: 404 }),
      ),
    )
    const { user } = renderForm()

    await user.type(addressBox(), 'habr.com')
    await user.click(checkButton())

    expect(await screen.findByRole('alert')).toHaveTextContent('Проверка не найдена.')
    expect(screen.queryByRole('status')).toBeNull()
    expect(checkButton()).toBeEnabled()
  })

  it('shows a refused add in place, and a new check forgets it and the edited name', async () => {
    serveDetection(() => makeDetectResult())
    server.use(
      http.post(apiUrl('/sources'), () =>
        HttpResponse.json({ detail: 'Источник уже добавлен.' }, { status: 409 }),
      ),
    )
    const { user, onDone, onAdded } = renderForm()

    await user.type(addressBox(), 'habr.com/ru/hubs/scada')
    await user.click(checkButton())
    await user.type(await screen.findByRole('textbox', { name: 'Название' }), ' (копия)')
    await user.click(screen.getByRole('button', { name: 'Добавить и опросить' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Источник уже добавлен.')
    expect(onDone).not.toHaveBeenCalled()
    expect(onAdded).not.toHaveBeenCalled()

    await user.click(checkButton())

    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
    expect(await screen.findByRole('textbox', { name: 'Название' })).toHaveValue('Хабр: SCADA')
  })

  // No handler for adding: a request to add would fail the test.
  it('lets the reader cancel once something is found', async () => {
    serveDetection(() => makeDetectResult())
    const { user, onDone, onAdded } = renderForm()

    await user.type(addressBox(), 'habr.com/ru/hubs/scada')
    await user.click(checkButton())
    expect(await screen.findByText('Лента RSS или Atom')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Отмена' }))

    expect(onDone).toHaveBeenCalledOnce()
    expect(onAdded).not.toHaveBeenCalled()
  })
})
