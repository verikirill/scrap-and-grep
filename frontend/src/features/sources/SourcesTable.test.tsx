import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Source, SourceCreate } from '../../lib/api'
import { useSources } from '../../lib/queries'
import { makeDetectJob, makeDetectResult, makeSource, makeSources } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { SourcesTable } from './SourcesTable'

const minutesAgo = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString()

/** The table fed from the catalogue query, as the sources page feeds it. */
function Catalogue({ isAdmin = false, canAdd = true }: { isAdmin?: boolean; canAdd?: boolean }) {
  const sources = useSources()
  return sources.data ? (
    <SourcesTable sources={sources.data} isAdmin={isAdmin} canAdd={canAdd} />
  ) : null
}

/** What a new source looks like once the server has it. */
function added(body: SourceCreate, id: number): Source {
  return makeSource({
    id,
    slug: `custom-${id}`,
    name: body.name ?? 'Канал без названия',
    kind: body.kind,
    feed_url: 'feed_url' in body ? body.feed_url : `https://t.me/s/${body.channel}`,
    site_url: null,
    category: body.category,
    language: body.language,
    fetch_full_text: body.fetch_full_text,
    last_fetched_at: null,
    last_status: null,
    articles: 0,
    articles_last_day: 0,
    can_edit: true,
  })
}

/**
 * The catalogue as the server keeps it: a change shows on the next read. A
 * held switch is answered only once `hold` settles.
 */
function serveCatalogue(initial: Source[], { hold }: { hold?: Promise<void> } = {}) {
  let sources = initial
  let reads = 0
  const sent = {
    patches: [] as { id: number; patch: Partial<Source> }[],
    created: [] as SourceCreate[],
    removed: [] as number[],
    polled: [] as number[],
    reads: () => reads,
  }
  server.use(
    http.get(apiUrl('/sources'), () => {
      reads += 1
      return HttpResponse.json(sources)
    }),
    http.patch(apiUrl('/sources/:id'), async ({ params, request }) => {
      const id = Number(params.id)
      const patch = (await request.json()) as Partial<Source>
      sent.patches.push({ id, patch })
      await hold
      sources = sources.map((source) => (source.id === id ? { ...source, ...patch } : source))
      return HttpResponse.json(sources.find((source) => source.id === id))
    }),
    http.delete(apiUrl('/sources/:id'), ({ params }) => {
      sent.removed.push(Number(params.id))
      sources = sources.filter((source) => source.id !== Number(params.id))
      return new HttpResponse(null, { status: 204 })
    }),
    http.post(apiUrl('/sources/:id/refresh'), ({ params }) => {
      sent.polled.push(Number(params.id))
      return HttpResponse.json({ status: 'queued' })
    }),
    http.post(apiUrl('/sources'), async ({ request }) => {
      const body = (await request.json()) as SourceCreate
      sent.created.push(body)
      const source = added(body, 100 + sent.created.length)
      sources = [...sources, source]
      return HttpResponse.json(source, { status: 201 })
    }),
  )
  return sent
}

/** A source's row, found by the name on its link. */
function rowOf(name: string | RegExp): HTMLElement {
  const row = screen
    .getAllByRole('listitem')
    .find((item) => within(item).queryByRole('link', { name }) !== null)
  if (!row) throw new Error(`No row for ${String(name)}`)
  return row
}

const NAMES = makeSources(6).map((source) => source.name)

/** The sources in the order the table lists them. */
function listedNames(): string[] {
  return screen
    .getAllByRole('link')
    .map((link) => NAMES.find((name) => within(link).queryByText(name)) ?? link.textContent ?? '')
}

const location = () => screen.getByTestId('location')

/**
 * Fake timers that user-event can work under. Testing Library waits for a zero
 * timeout after every user action and advances it only for a runner named jest.
 */
function useFakeClock() {
  vi.useFakeTimers()
  vi.stubGlobal('jest', { advanceTimersByTime: (ms: number) => vi.advanceTimersByTime(ms) })
}

beforeEach(() => {
  server.use(http.get(apiUrl('/sources/avatars'), () => HttpResponse.json({})))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SourcesTable list', () => {
  it('counts the enabled sources and lists them by topic, in the order of the topics', () => {
    renderWithProviders(
      <SourcesTable
        sources={makeSources(6).map((source) =>
          source.name === 'Минэнерго России' ? { ...source, enabled: false } : source,
        )}
        isAdmin
        canAdd
      />,
    )

    expect(
      screen.getByText(
        (_, node) => node?.tagName === 'P' && /^5 из 6 источников/.test(node.textContent ?? ''),
      ),
    ).toHaveTextContent('5 из 6 источников включено · опрос каждые 15 минут')
    // Each heading ends with the number of sources under it.
    expect(
      screen.getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent),
    ).toEqual(['Безопасность1', 'АСУ ТП2', 'Энергетика1', 'ИТ1', 'Регуляторы1'])
    expect(listedNames()).toEqual([
      'SecurityLab.ru',
      'CISA ICS Advisories',
      'Kaspersky ICS CERT',
      'Минэнерго России',
      'OpenNET',
      'БДУ ФСТЭК России',
    ])
  })

  it('tells each source’s last poll, articles and language in words and by its dot', () => {
    const [securityLab, kaspersky, minenergo, openNet, , cisa] = makeSources(6)
    renderWithProviders(
      <SourcesTable
        sources={[
          { ...securityLab, last_fetched_at: minutesAgo(5) },
          { ...kaspersky, last_status: 'error', last_error: null },
          { ...minenergo, enabled: false },
          { ...openNet, last_fetched_at: null, last_status: null },
          { ...cisa, last_status: 'error', last_error: 'HTTP 403 Forbidden' },
        ]}
        isAdmin={false}
        canAdd={false}
      />,
    )

    const fresh = rowOf('SecurityLab.ru')
    expect(within(fresh).getByRole('img', { name: 'Опрошен 5 минут назад' })).toBeInTheDocument()
    expect(within(fresh).getAllByText('опрошен 5 минут назад')).not.toHaveLength(0)
    expect(within(fresh).getAllByText('2 140')).not.toHaveLength(0)
    expect(within(fresh).getAllByText('+31')[0]).toHaveTextContent('+31 за сутки')
    expect(within(fresh).getByText('RU')).toBeInTheDocument()

    const failing = rowOf('CISA ICS Advisories')
    expect(
      within(failing).getByRole('img', { name: 'Ошибка: HTTP 403 Forbidden' }),
    ).toBeInTheDocument()
    expect(within(failing).getByText('HTTP 403 Forbidden')).toBeInTheDocument()
    expect(within(failing).getByText('EN')).toBeInTheDocument()

    const silentError = rowOf('Kaspersky ICS CERT')
    expect(within(silentError).getByRole('img', { name: 'Ошибка: неизвестна' })).toBeInTheDocument()
    expect(within(silentError).getByText('ошибка опроса')).toBeInTheDocument()

    const never = rowOf('OpenNET')
    expect(within(never).getByRole('img', { name: 'Не опрашивался' })).toBeInTheDocument()
    expect(within(never).getByText('ещё не опрашивался')).toBeInTheDocument()

    // A reader who cannot switch it gets no switch, only the word.
    const off = rowOf('Минэнерго России')
    expect(within(off).getByRole('img', { name: 'Источник отключён' })).toBeInTheDocument()
    expect(within(off).getByText('выключен')).toBeInTheDocument()
    expect(screen.queryByRole('switch')).toBeNull()
  })

  it('marks a page without a feed, a channel, and a site read a step up the ladder or by proxy', () => {
    const [securityLab, kaspersky, , , bdu] = makeSources(6)
    renderWithProviders(
      <SourcesTable
        sources={[
          { ...securityLab, kind: 'page' },
          {
            ...kaspersky,
            fetch_method: 'impersonate',
            fetch_via_proxy: true,
            fetch_note: 'Сайт отвечает 403 на простой запрос.',
          },
          bdu,
        ]}
        isAdmin={false}
        canAdd={false}
      />,
    )

    expect(within(rowOf('SecurityLab.ru')).getByText('Страница')).toHaveAttribute(
      'title',
      'У сайта нет RSS-ленты, поэтому статьи берутся со страницы новостей.',
    )
    expect(
      within(rowOf('Kaspersky ICS CERT')).getByText('Отпечаток Chrome, через прокси'),
    ).toHaveAttribute(
      'title',
      'Запрос повторяет сетевой отпечаток Chrome, чтобы пройти защиту от ботов. Запросы к сайту идут через прокси.\n\nСайт отвечает 403 на простой запрос.',
    )
    expect(
      within(rowOf(/БДУ ФСТЭК России/)).getByRole('img', { name: 'Telegram-канал' }),
    ).toBeInTheDocument()
  })

  it('links a source to its site, to its feed without one, and never to a script', () => {
    const [securityLab, kaspersky, minenergo] = makeSources(3)
    renderWithProviders(
      <SourcesTable
        sources={[
          securityLab,
          { ...kaspersky, site_url: null },
          { ...minenergo, site_url: 'javascript:alert(document.cookie)' },
        ]}
        isAdmin={false}
        canAdd={false}
      />,
    )

    expect(screen.getByRole('link', { name: 'SecurityLab.ru' })).toHaveAttribute(
      'href',
      'https://www.securitylab.ru',
    )
    expect(screen.getByRole('link', { name: 'Kaspersky ICS CERT' })).toHaveAttribute(
      'href',
      'https://ics-cert.kaspersky.ru/feed/',
    )
    expect(screen.getByText('Минэнерго России')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Минэнерго России' })).toBeNull()
  })
})

describe('SourcesTable search and filters', () => {
  it('finds sources as the reader types, keeps the search in the address and reads out the count', async () => {
    const { user } = renderWithProviders(<SourcesTable sources={makeSources(6)} isAdmin canAdd />, {
      route: '/sources',
    })

    await user.type(screen.getByRole('searchbox', { name: 'Поиск по источникам' }), '@bdufstecru')

    expect(listedNames()).toEqual(['БДУ ФСТЭК России'])
    expect(location()).toHaveTextContent('/sources?q=%40bdufstecru')
    // The live region says it for a screen reader; the line above the list shows it.
    expect(screen.getByText('Найдено 1 из 6')).toBeInTheDocument()
    expect(screen.queryByText(/источников включено/)).toBeNull()

    await user.clear(screen.getByRole('searchbox', { name: 'Поиск по источникам' }))

    expect(listedNames()).toHaveLength(6)
    expect(location()).toHaveTextContent(/^\/sources$/)
    expect(screen.queryByText('Найдено 1 из 6')).toBeNull()
  })

  it('offers to drop a search that found nothing and gives the focus back to the search box', async () => {
    const { user } = renderWithProviders(<SourcesTable sources={makeSources(6)} isAdmin canAdd />, {
      route: '/sources?q=zzz',
    })
    const search = screen.getByRole('searchbox', { name: 'Поиск по источникам' })
    expect(search).toHaveValue('zzz')
    expect(screen.getByText(/Нет источников по запросу «zzz»/)).toBeInTheDocument()
    expect(screen.queryAllByRole('link')).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: 'Сбросить поиск' }))

    expect(search).toHaveValue('')
    expect(search).toHaveFocus()
    expect(listedNames()).toHaveLength(6)
    expect(location()).toHaveTextContent(/^\/sources$/)
  })

  it('groups by where the news comes from and orders by how much a source brought', async () => {
    const { user } = renderWithProviders(<SourcesTable sources={makeSources(6)} isAdmin canAdd />, {
      route: '/sources',
    })
    const grouping = screen.getByRole('radiogroup', { name: 'Группировать' })
    const order = screen.getByRole('radiogroup', { name: 'Порядок' })

    await user.click(within(grouping).getByRole('radio', { name: /Сайты и Telegram/ }))
    await user.click(within(order).getByRole('radio', { name: /Больше новостей/ }))

    expect(location()).toHaveTextContent('/sources?group=kind&order=most')
    expect(
      screen.getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent),
    ).toEqual(['Сайты5', 'Telegram-каналы1'])
    expect(listedNames()).toEqual([
      'SecurityLab.ru',
      'OpenNET',
      'CISA ICS Advisories',
      'Минэнерго России',
      'Kaspersky ICS CERT',
      'БДУ ФСТЭК России',
    ])

    await user.click(within(order).getByRole('radio', { name: /Меньше новостей/ }))
    expect(listedNames().slice(0, 5)).toEqual([
      'Kaspersky ICS CERT',
      'Минэнерго России',
      'CISA ICS Advisories',
      'OpenNET',
      'SecurityLab.ru',
    ])

    // The defaults leave the address clean.
    await user.click(within(grouping).getByRole('radio', { name: /По темам/ }))
    await user.click(within(order).getByRole('radio', { name: /По названию/ }))
    expect(location()).toHaveTextContent(/^\/sources$/)
  })

  it('shows only the failing or the protected sources, and only one language', async () => {
    const [securityLab, kaspersky, minenergo, openNet, bdu, cisa] = makeSources(6)
    const { user } = renderWithProviders(
      <SourcesTable
        sources={[
          securityLab,
          { ...kaspersky, last_status: 'error', last_error: 'HTTP 403 Forbidden' },
          // Switched off, its old error does not count.
          { ...minenergo, enabled: false, last_status: 'error', last_error: 'ReadTimeout' },
          { ...openNet, fetch_method: 'browser' },
          { ...bdu, fetch_via_proxy: true },
          cisa,
        ]}
        isAdmin
        canAdd
      />,
      { route: '/sources' },
    )
    const shown = screen.getByRole('radiogroup', { name: 'Показать' })

    await user.click(within(shown).getByRole('radio', { name: /С ошибками/ }))
    expect(listedNames()).toEqual(['Kaspersky ICS CERT'])
    expect(location()).toHaveTextContent('/sources?show=failing')

    await user.click(within(shown).getByRole('radio', { name: /Защищённые/ }))
    expect(listedNames()).toEqual(['OpenNET', 'БДУ ФСТЭК России'])

    await user.click(within(shown).getByRole('radio', { name: /^Все/ }))
    await user.click(
      within(screen.getByRole('radiogroup', { name: 'Язык' })).getByRole('radio', { name: /EN/ }),
    )
    expect(listedNames()).toEqual(['CISA ICS Advisories'])
    expect(location()).toHaveTextContent(/^\/sources\?lang=en$/)
  })

  it('opens with the view the address carries, ignoring what it does not know', () => {
    renderWithProviders(<SourcesTable sources={makeSources(6)} isAdmin canAdd />, {
      route: '/sources?group=kind&order=least&lang=en&show=everything',
    })

    expect(screen.getByRole('radio', { name: /Сайты и Telegram/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: /Меньше новостей/ })).toBeChecked()
    expect(
      within(screen.getByRole('radiogroup', { name: 'Язык' })).getByRole('radio', { name: /EN/ }),
    ).toBeChecked()
    expect(
      within(screen.getByRole('radiogroup', { name: 'Показать' })).getByRole('radio', {
        name: /^Все/,
      }),
    ).toBeChecked()
    expect(listedNames()).toEqual(['CISA ICS Advisories'])
  })
})

describe('SourcesTable for readers and administrators', () => {
  it('tells a reader who may add sources that the ones they add are theirs to manage', () => {
    renderWithProviders(<SourcesTable sources={makeSources(2)} isAdmin={false} canAdd />)
    expect(
      screen.getByText(
        'Добавить можно любой сайт или канал. Добавленные вами источники вы отключаете и удаляете самостоятельно.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Опросить сейчас' })).toBeNull()
  })

  it('tells a reader of a closed catalogue that only an administrator switches sources', () => {
    renderWithProviders(<SourcesTable sources={makeSources(2)} isAdmin={false} canAdd={false} />)
    expect(
      screen.getByText('Включать и отключать источники может только администратор.'),
    ).toBeInTheDocument()
  })

  it('confirms a poll of the whole catalogue for four seconds, then offers it again', async () => {
    useFakeClock()
    let polls = 0
    server.use(
      http.post(apiUrl('/sources/refresh'), () => {
        polls += 1
        return HttpResponse.json({ status: 'queued' })
      }),
    )
    const { user } = renderWithProviders(<SourcesTable sources={makeSources(2)} isAdmin canAdd />, {
      userOptions: { advanceTimers: vi.advanceTimersByTime },
    })
    // An administrator manages every source and is told nothing about it.
    expect(screen.queryByText(/может только администратор/)).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Опросить сейчас' }))
    await vi.waitFor(() =>
      expect(screen.getByRole('button', { name: 'Опрос запущен' })).toBeInTheDocument(),
    )

    await vi.advanceTimersByTimeAsync(3000)
    expect(screen.getByRole('button', { name: 'Опрос запущен' })).toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(1000)
    await vi.waitFor(() =>
      expect(screen.getByRole('button', { name: 'Опросить сейчас' })).toBeInTheDocument(),
    )
    expect(polls).toBe(1)
  })

  it('shows why a poll of the whole catalogue was refused', async () => {
    server.use(
      http.post(apiUrl('/sources/refresh'), () =>
        HttpResponse.json({ detail: 'Очередь опроса недоступна.' }, { status: 503 }),
      ),
    )
    const { user } = renderWithProviders(<SourcesTable sources={makeSources(2)} isAdmin canAdd />)

    await user.click(screen.getByRole('button', { name: 'Опросить сейчас' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Очередь опроса недоступна.')
    expect(screen.getByRole('button', { name: 'Опросить сейчас' })).toBeInTheDocument()
  })
})

describe('SourcesTable switching, polling and removing a source', () => {
  it('switches a source off at once and keeps it off once the server agrees', async () => {
    let answer!: () => void
    const sent = serveCatalogue(makeSources(2, { can_edit: true }), {
      hold: new Promise<void>((resolve) => {
        answer = resolve
      }),
    })
    const { user } = renderWithProviders(<Catalogue />)

    await user.click(await screen.findByRole('switch', { name: 'Отключить SecurityLab.ru' }))

    // Off before the server has answered.
    await waitFor(() => expect(sent.patches).toEqual([{ id: 1, patch: { enabled: false } }]))
    expect(screen.getByRole('switch', { name: 'Включить SecurityLab.ru' })).toHaveAttribute(
      'aria-checked',
      'false',
    )
    expect(screen.getByText(/источников включено/)).toHaveTextContent(/^1 из 2/)

    answer()

    // The catalogue is read again and agrees.
    await waitFor(() => expect(sent.reads()).toBe(2))
    expect(screen.getByRole('switch', { name: 'Включить SecurityLab.ru' })).toHaveAttribute(
      'aria-checked',
      'false',
    )
    expect(screen.getByRole('img', { name: 'Источник отключён' })).toBeInTheDocument()
  })

  it('puts the switch back and says why when the server refuses, even if the list cannot be read again', async () => {
    let failedReads = 0
    server.use(
      http.get(apiUrl('/sources'), () => HttpResponse.json(makeSources(2, { can_edit: true })), {
        once: true,
      }),
      http.get(apiUrl('/sources'), () => {
        failedReads += 1
        return HttpResponse.json({ detail: 'Сервис недоступен' }, { status: 503 })
      }),
      http.patch(apiUrl('/sources/:id'), () =>
        HttpResponse.json({ detail: 'Источник сейчас опрашивается.' }, { status: 409 }),
      ),
    )
    const { user } = renderWithProviders(<Catalogue />)

    await user.click(await screen.findByRole('switch', { name: 'Отключить SecurityLab.ru' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Источник сейчас опрашивается.')
    await waitFor(() => expect(failedReads).toBe(1))
    expect(screen.getByRole('switch', { name: 'Отключить SecurityLab.ru' })).toHaveAttribute(
      'aria-checked',
      'true',
    )
    expect(screen.getByText(/источников включено/)).toHaveTextContent(/^2 из 2/)
  })

  it('removes a source with its articles once the reader confirms', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const sent = serveCatalogue(makeSources(3, { can_edit: true }))
    const { user } = renderWithProviders(<Catalogue />)

    await screen.findByRole('link', { name: 'Минэнерго России' })
    await user.click(
      within(rowOf('Минэнерго России')).getByRole('button', { name: 'Удалить источник' }),
    )

    await waitFor(() => expect(screen.queryByRole('link', { name: 'Минэнерго России' })).toBeNull())
    expect(confirm).toHaveBeenCalledWith('Удалить «Минэнерго России» вместе с его публикациями?')
    expect(sent.removed).toEqual([3])
    expect(listedNames()).toEqual(['SecurityLab.ru', 'Kaspersky ICS CERT'])
  })

  it('keeps a source the reader did not confirm removing, and polls one on request', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const sent = serveCatalogue(makeSources(3, { can_edit: true }))
    const { user } = renderWithProviders(<Catalogue />)

    await screen.findByRole('link', { name: 'Минэнерго России' })
    const row = rowOf('Минэнерго России')
    await user.click(within(row).getByRole('button', { name: 'Удалить источник' }))
    // The poll asked for after it is answered after anything the cancel could have sent.
    await user.click(within(row).getByRole('button', { name: 'Опросить источник' }))

    await waitFor(() => expect(sent.polled).toEqual([3]))
    expect(sent.removed).toEqual([])
    expect(screen.getByRole('link', { name: 'Минэнерго России' })).toBeInTheDocument()
  })

  it('says why a source could not be removed, then why it could not be polled', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    serveCatalogue(makeSources(2, { can_edit: true }))
    server.use(
      http.post(apiUrl('/sources/:id/refresh'), () =>
        HttpResponse.json({ detail: 'Опрос уже идёт.' }, { status: 409 }),
      ),
      http.delete(apiUrl('/sources/:id'), () =>
        HttpResponse.json({ detail: 'Удалить можно только свой источник.' }, { status: 403 }),
      ),
    )
    const { user } = renderWithProviders(<Catalogue />)

    await screen.findByRole('link', { name: 'Kaspersky ICS CERT' })
    const row = rowOf('Kaspersky ICS CERT')
    await user.click(within(row).getByRole('button', { name: 'Удалить источник' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Удалить можно только свой источник.',
    )
    expect(screen.getByRole('link', { name: 'Kaspersky ICS CERT' })).toBeInTheDocument()

    await user.click(within(row).getByRole('button', { name: 'Опросить источник' }))
    // The newer refusal replaces the older one.
    expect(await screen.findByRole('alert')).toHaveTextContent('Опрос уже идёт.')
    expect(screen.queryByText('Удалить можно только свой источник.')).toBeNull()
  })
})

describe('SourcesTable adding a source', () => {
  /** Open the form and pick how the source is given. */
  async function openForm(user: ReturnType<typeof renderWithProviders>['user'], mode: RegExp) {
    await user.click(await screen.findByRole('button', { name: 'Добавить источник' }))
    await user.click(
      within(screen.getByRole('radiogroup', { name: 'Тип источника' })).getByRole('radio', {
        name: mode,
      }),
    )
  }

  async function choose(
    user: ReturnType<typeof renderWithProviders>['user'],
    field: RegExp,
    option: string,
  ) {
    await user.click(screen.getByRole('button', { name: field }))
    await user.click(await screen.findByRole('option', { name: option }))
  }

  // Two HeroUI selects opened by clicks take seconds under a parallel run.
  it('adds a feed by hand with its address, category, language and full texts', async () => {
    const sent = serveCatalogue(makeSources(2))
    const { user } = renderWithProviders(<Catalogue />)

    await openForm(user, /Лента RSS или Atom/)
    await user.type(screen.getByRole('textbox', { name: 'Название' }), '  Хабр: SCADA ')
    await user.type(
      screen.getByRole('textbox', { name: 'Адрес RSS или Atom' }),
      ' https://habr.com/ru/rss/hubs/scada/articles/all/ ',
    )
    await choose(user, /Категория:/, 'Энергетика')
    await choose(user, /Язык:/, 'Английский')
    await user.click(screen.getByRole('switch', { name: 'Загружать полный текст' }))
    await user.click(screen.getByRole('button', { name: 'Добавить и опросить' }))

    expect(await screen.findByRole('link', { name: 'Хабр: SCADA' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Добавить и опросить' })).toBeNull()
    expect(sent.created).toEqual([
      {
        kind: 'rss',
        name: 'Хабр: SCADA',
        feed_url: 'https://habr.com/ru/rss/hubs/scada/articles/all/',
        category: 'energy',
        language: 'en',
        fetch_full_text: true,
      },
    ])
  }, 15_000)

  it.each([
    { typed: '', sentName: {} },
    { typed: '  SecAtor ', sentName: { name: 'SecAtor' } },
  ])(
    'adds a channel by hand, named by the reader or after itself ($typed)',
    async ({ typed, sentName }) => {
      const sent = serveCatalogue(makeSources(2))
      const { user } = renderWithProviders(<Catalogue />)

      await openForm(user, /Telegram-канал/)
      const channel = screen.getByRole('textbox', { name: 'Канал' })
      expect(channel).toHaveAccessibleDescription(/^Канал читается через веб-страницу t\.me\/s\//)
      // Channel posts are short: the articles they point to are worth opening.
      expect(screen.getByRole('switch', { name: 'Загружать полный текст' })).toHaveAttribute(
        'aria-checked',
        'true',
      )
      if (typed) await user.type(screen.getByRole('textbox', { name: /^Название/ }), typed)
      await user.type(channel, ' @true_secator ')
      await user.click(screen.getByRole('button', { name: 'Добавить и опросить' }))

      await waitFor(() =>
        expect(screen.queryByRole('button', { name: 'Добавить и опросить' })).toBeNull(),
      )
      expect(sent.created).toEqual([
        {
          kind: 'telegram',
          channel: '@true_secator',
          ...sentName,
          category: 'security',
          language: 'ru',
          fetch_full_text: true,
        },
      ])
      await waitFor(() => expect(sent.reads()).toBe(2))
    },
  )

  it('does not send a feed without a name or with an address that is not a web address', async () => {
    const sent = serveCatalogue(makeSources(2))
    const { user } = renderWithProviders(<Catalogue />)

    await openForm(user, /Лента RSS или Atom/)
    const name = screen.getByRole('textbox', { name: 'Название' })
    const address = screen.getByRole('textbox', { name: 'Адрес RSS или Atom' })
    const save = screen.getByRole('button', { name: 'Добавить и опросить' })

    await user.type(address, 'https://habr.com/ru/rss/')
    await user.click(save)
    await user.type(name, 'Хабр')
    await user.clear(address)
    await user.type(address, 'habr.com/ru/rss/')
    await user.click(save)
    // Only a whole form leaves; it is the one to wait for.
    await user.clear(address)
    await user.type(address, 'https://habr.com/ru/rss/')
    await user.click(save)

    expect(await screen.findByRole('link', { name: 'Хабр' })).toBeInTheDocument()
    expect(sent.created).toEqual([
      expect.objectContaining({ name: 'Хабр', feed_url: 'https://habr.com/ru/rss/' }),
    ])
  })

  it('keeps the form open with the server’s refusal', async () => {
    serveCatalogue(makeSources(2))
    server.use(
      http.post(apiUrl('/sources'), () =>
        HttpResponse.json({ detail: 'Источник уже добавлен.' }, { status: 409 }),
      ),
    )
    const { user } = renderWithProviders(<Catalogue />)

    await openForm(user, /Лента RSS или Atom/)
    await user.type(screen.getByRole('textbox', { name: 'Название' }), 'SecurityLab')
    await user.type(
      screen.getByRole('textbox', { name: 'Адрес RSS или Atom' }),
      'https://www.securitylab.ru/_services/export/rss/',
    )
    await user.click(screen.getByRole('button', { name: 'Добавить и опросить' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Источник уже добавлен.')
    expect(screen.getByRole('textbox', { name: 'Название' })).toHaveValue('SecurityLab')
  })

  it('drops an address typed for another kind of source, and cancels', async () => {
    serveCatalogue(makeSources(2))
    const { user } = renderWithProviders(<Catalogue />)

    await openForm(user, /Лента RSS или Atom/)
    await user.type(
      screen.getByRole('textbox', { name: 'Адрес RSS или Atom' }),
      'https://habr.com/rss/',
    )
    expect(screen.getByRole('switch', { name: 'Загружать полный текст' })).toHaveAttribute(
      'aria-checked',
      'false',
    )

    await user.click(screen.getByRole('radio', { name: /Telegram-канал/ }))
    expect(screen.getByRole('textbox', { name: 'Канал' })).toHaveValue('')

    // Any address goes to the worker to find out what it is.
    await user.click(screen.getByRole('radio', { name: /Любой адрес/ }))
    expect(screen.getByRole('button', { name: 'Проверить' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Отмена' }))
    await waitFor(() =>
      expect(screen.queryByRole('radiogroup', { name: 'Тип источника' })).toBeNull(),
    )
  })

  it('adds what an address turns out to be and clears a search it would hide behind', async () => {
    const sent = serveCatalogue(makeSources(2))
    server.use(
      http.post(apiUrl('/sources/detect'), () => HttpResponse.json(makeDetectJob())),
      http.get(apiUrl('/sources/detect/:requestId'), () => HttpResponse.json(makeDetectResult())),
    )
    const { user } = renderWithProviders(<Catalogue />, { route: '/sources?q=modbus' })

    expect(await screen.findByText(/Нет источников по запросу «modbus»/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Добавить источник' }))
    await user.type(screen.getByRole('textbox', { name: /^Адрес/ }), 'habr.com/ru/hubs/scada')
    await user.click(screen.getByRole('button', { name: 'Проверить' }))
    await user.click(await screen.findByRole('button', { name: 'Добавить и опросить' }))

    expect(await screen.findByRole('link', { name: 'Хабр: SCADA' })).toBeInTheDocument()
    expect(location()).toHaveTextContent(/^\/sources$/)
    expect(screen.queryByRole('button', { name: 'Проверить' })).toBeNull()
    expect(sent.created).toEqual([expect.objectContaining({ kind: 'rss', name: 'Хабр: SCADA' })])
  })
})
