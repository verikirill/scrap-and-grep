import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RequireAuth } from '../components/RequireAuth'
import type {
  FeedFresh,
  FeedItem,
  FeedOrder,
  FeedPage as FeedPageData,
  ListSlot,
  Me,
  ReactionKind,
  Settings,
  Taste,
} from '../lib/api'
import { setMediaQueries } from '../test/browser'
import {
  makeFeedFresh,
  makeFeedItems,
  makeFeedPage,
  makeMe,
  makeSavedPage,
  makeSettings,
  makeTaste,
  makeTasteFacet,
} from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { FeedPage } from './FeedPage'

/** A reader's mark as the page sends it (POST /feedback). */
type Mark = {
  article_id: number
  kind: ReactionKind
  active: boolean
  context: 'feed' | 'digest'
  list_id?: string | null
  position?: number
  slot?: ListSlot
}

type Answer = (params: URLSearchParams) => FeedPageData

/** One list per order of the feed. */
const byOrder =
  (lists: Record<FeedOrder, FeedPageData>): Answer =>
  (params) =>
    lists[params.get('order') as FeedOrder]

/** Answers one after another, the last one from then on. */
function inTurn<T>(...answers: T[]): () => T {
  let next = 0
  return () => answers[Math.min(next++, answers.length - 1)]
}

/**
 * The catalogue's six stories cut into lists of the given lengths: lists of one
 * test never share a headline. (Two calls of makeFeedItems start from the same story.)
 */
function stories(...lengths: number[]): FeedItem[][] {
  const all = makeFeedItems(lengths.reduce((sum, length) => sum + length, 0))
  let start = 0
  return lengths.map((length) => all.slice(start, (start += length)))
}

/** `count` items titled «Публикация N» from N = `from`: lists longer than the catalogue's six stories. */
function numbered(count: number, from = 1, overrides: Partial<FeedItem> = {}): FeedItem[] {
  return makeFeedItems(count, overrides).map((item, index) => ({
    ...item,
    title: `Публикация ${from + index}`,
    position: from + index,
  }))
}

/**
 * The reader's account and feed as the server keeps them: settings sent are
 * in the account on the next read. Each request is written down as the query
 * it carried or the body it sent.
 */
function serveFeed({
  me = makeMe(),
  feed,
  saved = () => makeSavedPage({ items: [] }),
  taste = () => makeTaste(),
  fresh = () => makeFeedFresh(),
}: {
  me?: Me
  feed?: Answer
  saved?: Answer
  taste?: () => Taste
  fresh?: (since: string) => FeedFresh
} = {}) {
  let account = me
  const ranked = makeFeedPage()
  const answerFeed = feed ?? (() => ranked)
  const sent = {
    feed: [] as string[],
    saved: [] as string[],
    fresh: [] as string[],
    settings: [] as Partial<Settings>[],
    marks: [] as Mark[],
  }
  server.use(
    http.get(apiUrl('/auth/me'), () => HttpResponse.json(account)),
    http.patch(apiUrl('/auth/me/settings'), async ({ request }) => {
      const patch = (await request.json()) as Partial<Settings>
      sent.settings.push(patch)
      account = { ...account, ...patch }
      return HttpResponse.json(
        makeSettings({ feed_view: account.feed_view, feed_order: account.feed_order }),
      )
    }),
    http.get(apiUrl('/feed'), ({ request }) => {
      const params = new URL(request.url).searchParams
      sent.feed.push(params.toString())
      return HttpResponse.json(answerFeed(params))
    }),
    http.get(apiUrl('/feed/saved'), ({ request }) => {
      const params = new URL(request.url).searchParams
      sent.saved.push(params.toString())
      return HttpResponse.json(saved(params))
    }),
    http.get(apiUrl('/feed/fresh'), ({ request }) => {
      const since = new URL(request.url).searchParams.get('since') ?? ''
      sent.fresh.push(since)
      return HttpResponse.json(fresh(since))
    }),
    http.get(apiUrl('/taste'), () => HttpResponse.json(taste())),
    http.post(apiUrl('/feedback'), async ({ request }) => {
      sent.marks.push((await request.json()) as Mark)
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return sent
}

/** The page as the app mounts it: behind the guard that loads the account first. */
function renderFeed(route = '/feed', userOptions?: Parameters<typeof renderWithProviders>[1]) {
  return renderWithProviders(
    <RequireAuth>
      <FeedPage />
    </RequireAuth>,
    { route, ...userOptions },
  )
}

/** A promise the server waits on until the test lets it answer. */
function gate() {
  let open = () => {}
  const closed = new Promise<void>((resolve) => {
    open = resolve
  })
  return { closed, open }
}

const location = () => screen.getByTestId('location').textContent
const titleLink = (item: FeedItem) => screen.getByRole('link', { name: item.title })
const isBefore = (first: Node, second: Node) =>
  Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING)

const SUBTITLE = {
  new: 'Публикации по вашим интересам за две недели, от новых к старым. Прочитанное уходит вниз, свежее появляется автоматически.',
  top: 'Публикации за две недели, подобранные по интересам, резюме и вашим отметкам. У каждой видно, почему она здесь.',
  saved: 'Публикации, которые вы отложили кнопкой «Сохранить».',
}
const MARKS_NOTE = 'Порядок на экране не меняется, пока вы читаете.'

describe('FeedPage tabs', () => {
  it.each(['/feed', '/feed?tab=everything'])(
    'opens on the order the reader chose last time at %s',
    async (route) => {
      const [latest, best] = stories(2, 2)
      const top = makeFeedPage({ items: best })
      const sent = serveFeed({
        me: makeMe({ feed_order: 'top' }),
        feed: byOrder({ new: makeFeedPage({ items: latest }), top }),
      })
      renderFeed(route)

      expect(await screen.findByRole('link', { name: top.items[0].title })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Важное' })).toBePressed()
      expect(screen.getByRole('button', { name: 'Новое' })).not.toBePressed()
      expect(screen.getByText(SUBTITLE.top)).toBeInTheDocument()
      // The best-first order is rebuilt rather than refreshed.
      expect(screen.getByRole('button', { name: 'Пересобрать' })).toBeEnabled()
      expect(sent.feed).toEqual(['order=top&limit=20&offset=0'])
    },
  )

  it('lets the address pick the tab over the order kept with the account', async () => {
    const [newest, best] = stories(2, 2)
    const latest = makeFeedPage({ items: newest })
    const sent = serveFeed({
      me: makeMe({ feed_order: 'top' }),
      feed: byOrder({ new: latest, top: makeFeedPage({ items: best }) }),
    })
    renderFeed('/feed?tab=new')

    expect(await screen.findByRole('link', { name: latest.items[0].title })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Новое' })).toBePressed()
    expect(screen.getByText(SUBTITLE.new)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Обновить' })).toBeEnabled()
    expect(sent.feed).toEqual(['order=new&limit=20&offset=0'])
  })

  it('keeps the chosen order with the account and in the address', async () => {
    const [latest, best] = stories(2, 2)
    const sent = serveFeed({
      feed: byOrder({
        new: makeFeedPage({ items: latest }),
        top: makeFeedPage({ items: [best[1], best[0]] }),
      }),
    })
    const { user } = renderFeed()
    await screen.findByRole('link', { name: latest[0].title })

    await user.click(screen.getByRole('button', { name: 'Важное' }))

    await waitFor(() => expect(location()).toBe('/feed?tab=top'))
    expect(screen.getByRole('button', { name: 'Важное' })).toBePressed()
    // The best-first list puts the second story first.
    const links = await screen.findAllByRole('link', { name: best[1].title })
    expect(isBefore(links[0], titleLink(best[0]))).toBe(true)
    expect(sent.settings).toEqual([{ feed_order: 'top' }])
    expect(sent.feed).toEqual(['order=new&limit=20&offset=0', 'order=top&limit=20&offset=0'])
  })

  it('shows what the reader saved in its own tab and leaves the kept order as it is', async () => {
    const [latest, shelf] = stories(2, 2)
    const kept = makeSavedPage({
      items: shelf.map((item) => ({ ...item, reactions: ['save'], slot: 'saved' })),
    })
    const sent = serveFeed({ feed: () => makeFeedPage({ items: latest }), saved: () => kept })
    const { user } = renderFeed()
    await screen.findByText(/^Лента собрана/)

    await user.click(screen.getByRole('button', { name: 'Сохранённое' }))

    expect(await screen.findByRole('link', { name: kept.items[0].title })).toBeInTheDocument()
    expect(location()).toBe('/feed?tab=saved')
    expect(screen.getByRole('button', { name: 'Сохранённое' })).toBePressed()
    expect(screen.getByText(SUBTITLE.saved)).toBeInTheDocument()
    // Saved articles keep the order they were saved in: there is nothing to rebuild.
    expect(screen.getByRole('button', { name: 'Пересобрать' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Пересобрать ленту' })).toBeDisabled()
    expect(screen.queryByText(/^Лента собрана/)).toBeNull()
    expect(sent.saved).toEqual(['limit=20&offset=0'])
    expect(sent.settings).toEqual([])
  })
})

describe('FeedPage tabs over time', () => {
  // Only the clock is fake: what ages a list is the time the reader spends elsewhere.
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-14T09:00:00Z'))
  })

  it('shows a look at the other order and back as both lists were', async () => {
    const [latest, best, rebuilt] = stories(2, 2, 2)
    const top = inTurn(makeFeedPage({ items: best }), makeFeedPage({ items: rebuilt }))
    const sent = serveFeed({
      feed: (params) => (params.get('order') === 'new' ? makeFeedPage({ items: latest }) : top()),
    })
    const { user } = renderFeed()
    await screen.findByRole('link', { name: latest[0].title })
    await user.click(screen.getByRole('button', { name: 'Важное' }))
    await screen.findByRole('button', { name: `Больше такого: ${best[0].title}` })

    vi.setSystemTime(new Date('2026-10-14T09:04:00Z'))
    await user.click(screen.getByRole('button', { name: 'Новое' }))
    expect(await screen.findByRole('button', { name: 'Новое', pressed: true })).toBeInTheDocument()
    expect(titleLink(latest[0])).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Важное' }))
    expect(await screen.findByRole('button', { name: 'Важное', pressed: true })).toBeInTheDocument()

    // The open tab is never ranked anew by a click on it, however old it is.
    vi.setSystemTime(new Date('2026-10-14T09:10:00Z'))
    await user.click(screen.getByRole('button', { name: 'Важное' }))

    // A rebuild asked for reaches the server; a reload of either tab would have come before it.
    await user.click(screen.getByRole('button', { name: 'Пересобрать' }))
    expect(
      await screen.findByRole('button', { name: `Больше такого: ${rebuilt[0].title}` }),
    ).toBeInTheDocument()
    expect(sent.feed).toEqual([
      'order=new&limit=20&offset=0',
      'order=top&limit=20&offset=0',
      'order=top&limit=20&offset=0',
    ])
  })

  it('ranks an order anew when the reader comes back to it after five minutes', async () => {
    const [before, after, best] = stories(2, 2, 2)
    const latest = inTurn(makeFeedPage({ items: before }), makeFeedPage({ items: after }))
    const sent = serveFeed({
      feed: (params) => (params.get('order') === 'new' ? latest() : makeFeedPage({ items: best })),
    })
    const { user } = renderFeed()
    await screen.findByRole('button', { name: `Больше такого: ${before[0].title}` })
    await user.click(screen.getByRole('button', { name: 'Важное' }))
    await screen.findByRole('button', { name: `Больше такого: ${best[0].title}` })

    vi.setSystemTime(new Date('2026-10-14T09:05:01Z'))
    await user.click(screen.getByRole('button', { name: 'Новое' }))

    expect(
      await screen.findByRole('button', { name: `Больше такого: ${after[1].title}` }),
    ).toBeInTheDocument()
    expect(sent.feed).toEqual([
      'order=new&limit=20&offset=0',
      'order=top&limit=20&offset=0',
      'order=new&limit=20&offset=0',
    ])
  })
})

describe('FeedPage marks', () => {
  it('sends a like with the article’s place in the ranking and says what it changes', async () => {
    const items = makeFeedItems(3)
    const sent = serveFeed({ feed: () => makeFeedPage({ items, snapshot: 'snapshot-7' }) })
    const { user } = renderFeed()
    const like = await screen.findByRole('button', { name: `Больше такого: ${items[1].title}` })

    await user.click(like)

    expect(await screen.findByText('Учтено: похожего станет больше')).toBeInTheDocument()
    expect(like).toBePressed()
    expect(screen.getByText(`1 отметка учтена. ${MARKS_NOTE}`)).toBeInTheDocument()
    expect(sent.marks).toEqual([
      {
        article_id: items[1].article_id,
        kind: 'like',
        active: true,
        context: 'feed',
        list_id: 'snapshot-7',
        position: 2,
        slot: 'ranked',
      },
    ])
  })

  it('counts the marks that teach the feed and ranks it anew on request', async () => {
    const [ranked, rebuilt] = stories(3, 3)
    const sent = serveFeed({
      feed: inTurn(makeFeedPage({ items: ranked }), makeFeedPage({ items: rebuilt })),
    })
    const { user } = renderFeed()

    await user.click(
      await screen.findByRole('button', { name: `Больше такого: ${ranked[0].title}` }),
    )
    await screen.findByText('Учтено: похожего станет больше')
    await user.click(screen.getByRole('button', { name: `Сохранить: ${ranked[1].title}` }))
    await screen.findByText('Сохранено, лежит во вкладке «Сохранённое»')
    // Opening an article is a mark too, but it does not change the next feed.
    await user.click(titleLink(ranked[2]))
    await waitFor(() => expect(sent.marks).toHaveLength(3))
    expect(sent.marks[2]).toMatchObject({ article_id: ranked[2].article_id, kind: 'open' })
    expect(screen.getByText(`2 отметки учтены. ${MARKS_NOTE}`)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Пересобрать ленту' }))

    expect(await screen.findByRole('link', { name: rebuilt[0].title })).toBeInTheDocument()
    expect(screen.queryByText(/учтены\./)).toBeNull()
    expect(sent.feed).toEqual(['order=new&limit=20&offset=0', 'order=new&limit=20&offset=0'])
  })

  it('counts and confirms each mark of a quick series', async () => {
    const items = makeFeedItems(2)
    const sent = serveFeed({ feed: () => makeFeedPage({ items }) })
    const first = gate()
    server.use(
      http.post(apiUrl('/feedback'), async ({ request }) => {
        const mark = (await request.json()) as Mark
        sent.marks.push(mark)
        if (mark.kind === 'like') await first.closed
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { user } = renderFeed()
    await user.click(
      await screen.findByRole('button', { name: `Больше такого: ${items[0].title}` }),
    )
    await waitFor(() => expect(sent.marks).toHaveLength(1))

    // The second mark is made while the first is still on its way.
    await user.click(screen.getByRole('button', { name: `Сохранить: ${items[1].title}` }))
    first.open()

    expect(await screen.findByText(`2 отметки учтены. ${MARKS_NOTE}`)).toBeInTheDocument()
    expect(screen.getByText('Учтено: похожего станет больше')).toBeInTheDocument()
    expect(screen.getByText('Сохранено, лежит во вкладке «Сохранённое»')).toBeInTheDocument()
    expect(sent.marks.map((mark) => mark.kind)).toEqual(['like', 'save'])
  })

  it('takes a mark back and says why when the server refuses it', async () => {
    const items = makeFeedItems(2)
    serveFeed({ feed: () => makeFeedPage({ items }) })
    server.use(
      http.post(apiUrl('/feedback'), () =>
        HttpResponse.json({ detail: 'Отметки сейчас не принимаются' }, { status: 503 }),
      ),
    )
    const { user } = renderFeed()
    const like = await screen.findByRole('button', { name: `Больше такого: ${items[0].title}` })

    await user.click(like)

    expect(await screen.findByRole('alert')).toHaveTextContent('Отметки сейчас не принимаются')
    expect(like).not.toBePressed()
    expect(screen.queryByText(/учтена\./)).toBeNull()
  })

  it('takes back only the mark the server refused, and says why', async () => {
    const [refused, accepted] = makeFeedItems(2)
    const sent = serveFeed({ feed: () => makeFeedPage({ items: [refused, accepted] }) })
    const first = gate()
    server.use(
      http.post(apiUrl('/feedback'), async ({ request }) => {
        const mark = (await request.json()) as Mark
        sent.marks.push(mark)
        if (mark.article_id !== refused.article_id) return new HttpResponse(null, { status: 204 })
        await first.closed
        return HttpResponse.json({ detail: 'Отметки сейчас не принимаются' }, { status: 503 })
      }),
    )
    const { user } = renderFeed()
    const likeRefused = await screen.findByRole('button', {
      name: `Больше такого: ${refused.title}`,
    })
    const likeAccepted = screen.getByRole('button', { name: `Больше такого: ${accepted.title}` })
    await user.click(likeRefused)
    await waitFor(() => expect(sent.marks).toHaveLength(1))
    await user.click(likeAccepted)
    // Both buttons answer at once, before the server does.
    expect(likeRefused).toBePressed()
    expect(likeAccepted).toBePressed()

    first.open()

    await waitFor(() => expect(likeRefused).not.toBePressed())
    expect(await screen.findByText('Отметки сейчас не принимаются')).toBeInTheDocument()
    await waitFor(() => expect(sent.marks).toHaveLength(2))
    expect(await screen.findByText(`1 отметка учтена. ${MARKS_NOTE}`)).toBeInTheDocument()
    expect(likeAccepted).toBePressed()
  })

  it('shows a mark in the other order too, without asking the server again', async () => {
    const [shared, other] = makeFeedItems(2)
    const sent = serveFeed({
      feed: byOrder({
        new: makeFeedPage({ items: [shared, other] }),
        top: makeFeedPage({ items: [other, shared] }),
      }),
    })
    const { user } = renderFeed()
    await screen.findByRole('link', { name: shared.title })
    await user.click(screen.getByRole('button', { name: 'Важное' }))
    await screen.findByRole('button', { name: 'Важное', pressed: true })
    await user.click(screen.getByRole('button', { name: `Больше такого: ${shared.title}` }))
    await screen.findByText('Учтено: похожего станет больше')

    await user.click(screen.getByRole('button', { name: 'Новое' }))

    await screen.findByRole('button', { name: 'Новое', pressed: true })
    expect(screen.getByRole('button', { name: `Больше такого: ${shared.title}` })).toBePressed()
    expect(screen.getByRole('button', { name: `Больше такого: ${other.title}` })).not.toBePressed()
    expect(sent.feed).toHaveLength(2)
  })

  it('finds a saved article in the saved tab and drops it there once taken back', async () => {
    const [kept, other] = makeFeedItems(2)
    let shelf: FeedItem[] = []
    const sent = serveFeed({
      feed: () => makeFeedPage({ items: [kept, other] }),
      saved: () => makeSavedPage({ items: shelf }),
    })
    server.use(
      http.post(apiUrl('/feedback'), async ({ request }) => {
        const mark = (await request.json()) as Mark
        sent.marks.push(mark)
        if (mark.kind === 'save') {
          shelf = mark.active
            ? [{ ...kept, reactions: ['save'], reasons: [], parts: {}, slot: 'saved' }]
            : []
        }
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { user } = renderFeed()
    await user.click(await screen.findByRole('button', { name: `Сохранить: ${kept.title}` }))
    await screen.findByText('Сохранено, лежит во вкладке «Сохранённое»')

    await user.click(screen.getByRole('button', { name: 'Сохранённое' }))
    const unsave = await screen.findByRole('button', { name: `Сохранить: ${kept.title}` })
    expect(unsave).toBePressed()
    expect(screen.queryByRole('link', { name: other.title })).toBeNull()

    await user.click(unsave)

    expect(await screen.findByText('Сохранённого пока нет')).toBeInTheDocument()
    expect(sent.marks.map(({ kind, active }) => [kind, active])).toEqual([
      ['save', true],
      ['save', false],
    ])
  })

  it('folds a hidden article into a line, hands it the focus, and brings it back', async () => {
    const [hidden, other] = makeFeedItems(2)
    const sent = serveFeed({ feed: () => makeFeedPage({ items: [hidden, other] }) })
    const { user } = renderFeed()

    await user.click(await screen.findByRole('button', { name: `Скрыть: ${hidden.title}` }))

    expect(await screen.findByRole('status')).toHaveTextContent(`Скрыто: ${hidden.title}`)
    const undo = screen.getByRole('button', { name: 'Вернуть в ленту' })
    expect(undo).toHaveFocus()
    expect(screen.queryByRole('link', { name: hidden.title })).toBeNull()

    await user.click(undo)

    expect(await screen.findByRole('link', { name: hidden.title })).toBeInTheDocument()
    expect(sent.marks.map(({ kind, active }) => [kind, active])).toEqual([
      ['hide', true],
      ['hide', false],
    ])
  })
})

describe('FeedPage new arrivals', () => {
  it('offers what arrived since the feed was ranked and shows it on request', async () => {
    const [before, after] = stories(3, 3)
    const ranked = makeFeedPage({ items: before, built_at: '2026-10-14T08:55:00Z' })
    const rebuilt = makeFeedPage({ items: after, built_at: '2026-10-14T09:20:00Z' })
    const sent = serveFeed({
      feed: inTurn(ranked, rebuilt),
      fresh: (since) => makeFeedFresh({ fresh: since === ranked.built_at ? 3 : 0 }),
    })
    const scroll = vi.spyOn(window, 'scrollTo')
    const { user } = renderFeed()

    await user.click(await screen.findByRole('button', { name: '3 новые публикации' }))

    expect(await screen.findByRole('link', { name: after[0].title })).toBeInTheDocument()
    await waitFor(() => expect(sent.fresh).toEqual([ranked.built_at, rebuilt.built_at]))
    expect(screen.queryByRole('button', { name: /новые публикации/ })).toBeNull()
    expect(scroll).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
  })

  it('keeps the offer of new articles to the feed and away from the saved tab', async () => {
    serveFeed({ fresh: () => makeFeedFresh({ fresh: 1 }) })
    const { user } = renderFeed()
    expect(await screen.findByRole('button', { name: '1 новая публикация' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Сохранённое' }))

    expect(await screen.findByText('Сохранённого пока нет')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '1 новая публикация' })).toBeNull()
  })

  it('asks for a ranking without a time only once it has one', async () => {
    const sent = serveFeed({ feed: () => makeFeedPage({ built_at: null }) })
    const { user } = renderFeed()
    await screen.findByText(/^Лента собрана/)
    // The rebuild is the sentinel: by its answer a question about news would have gone too.
    await user.click(screen.getByRole('button', { name: 'Обновить' }))
    await waitFor(() => expect(sent.feed).toHaveLength(2))
    await screen.findByRole('button', { name: 'Обновить' })
    expect(sent.fresh).toEqual([])
  })
})

describe('FeedPage new arrivals over time', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    Reflect.deleteProperty(document, 'visibilityState')
  })

  /** The browser tells the page it was hidden or shown again. */
  function setTabVisible(isVisible: boolean) {
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: isVisible ? 'visible' : 'hidden',
    })
    document.dispatchEvent(new Event('visibilitychange', { bubbles: true }))
  }

  it('asks every two minutes whether the feed has fallen behind', async () => {
    const sent = serveFeed({
      fresh: inTurn(makeFeedFresh({ fresh: 0 }), makeFeedFresh({ fresh: 2 })),
    })
    renderFeed()
    await vi.waitFor(() => expect(sent.fresh).toHaveLength(1))
    await vi.waitFor(() => expect(screen.getByText(/^Лента собрана/)).toBeInTheDocument())

    await vi.advanceTimersByTimeAsync(120_000)

    await vi.waitFor(() =>
      expect(screen.getByRole('button', { name: '2 новые публикации' })).toBeInTheDocument(),
    )
    expect(sent.fresh).toHaveLength(2)
  })

  it('does not ask while the tab is hidden and asks at once when the reader is back', async () => {
    const sent = serveFeed({
      fresh: inTurn(makeFeedFresh({ fresh: 0 }), makeFeedFresh({ fresh: 4 })),
    })
    renderFeed()
    await vi.waitFor(() => expect(sent.fresh).toHaveLength(1))

    setTabVisible(false)
    await vi.advanceTimersByTimeAsync(5 * 60_000)
    setTabVisible(true)

    await vi.waitFor(() =>
      expect(screen.getByRole('button', { name: '4 новые публикации' })).toBeInTheDocument(),
    )
    expect(sent.fresh).toHaveLength(2)
  })
})

describe('FeedPage list', () => {
  it('shows the next twenty articles of the same ranking on request', async () => {
    const [first, second] = [numbered(20), numbered(5, 21)]
    const sent = serveFeed({
      feed: (params) =>
        params.get('offset') === '20'
          ? makeFeedPage({ items: second, total: 25, offset: 20, snapshot: 'snapshot-1' })
          : makeFeedPage({ items: first, total: 25, snapshot: 'snapshot-1' }),
    })
    const { user } = renderFeed()
    await screen.findByRole('link', { name: 'Публикация 20' })
    expect(screen.getAllByRole('article')).toHaveLength(20)

    await user.click(screen.getByRole('button', { name: 'Показать ещё' }))

    expect(await screen.findByRole('link', { name: 'Публикация 25' })).toBeInTheDocument()
    expect(screen.getAllByRole('article')).toHaveLength(25)
    expect(screen.queryByRole('button', { name: 'Показать ещё' })).toBeNull()
    expect(sent.feed).toEqual([
      'order=new&limit=20&offset=0',
      'order=new&limit=20&offset=20&snapshot=snapshot-1',
    ])
  })

  it('pages through the new ranking after a rebuild', async () => {
    let builds = 0
    const sent = serveFeed({
      feed: (params) => {
        if (params.get('offset') === '0') builds += 1
        const snapshot = `snapshot-${builds}`
        return params.get('offset') === '20'
          ? makeFeedPage({ items: numbered(5, builds * 100 + 21), offset: 20, total: 25, snapshot })
          : makeFeedPage({ items: numbered(20, builds * 100 + 1), total: 25, snapshot })
      },
    })
    const { user } = renderFeed()
    await screen.findByRole('link', { name: 'Публикация 101' })

    await user.click(screen.getByRole('button', { name: 'Обновить' }))
    await screen.findByRole('link', { name: 'Публикация 201' })
    await user.click(screen.getByRole('button', { name: 'Показать ещё' }))

    expect(await screen.findByRole('link', { name: 'Публикация 225' })).toBeInTheDocument()
    expect(sent.feed).toEqual([
      'order=new&limit=20&offset=0',
      'order=new&limit=20&offset=0',
      'order=new&limit=20&offset=20&snapshot=snapshot-2',
    ])
  })

  it('shows an article once when two pages both carry it', async () => {
    const first = numbered(20)
    const second = [first[19], ...numbered(4, 21)]
    serveFeed({
      feed: (params) =>
        params.get('offset') === '20'
          ? makeFeedPage({ items: second, total: 25, offset: 20 })
          : makeFeedPage({ items: first, total: 25 }),
    })
    const { user } = renderFeed()
    await user.click(await screen.findByRole('button', { name: 'Показать ещё' }))

    expect(await screen.findByRole('link', { name: 'Публикация 24' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Публикация 20' })).toHaveLength(1)
    expect(screen.getAllByRole('article')).toHaveLength(24)
  })

  it('marks where the articles met before begin, in the newest-first order only', async () => {
    const items = makeFeedItems(4).map((item, index) => ({ ...item, seen: index >= 2 }))
    serveFeed({ feed: () => makeFeedPage({ items }) })
    const { user } = renderFeed()
    await screen.findByRole('link', { name: items[0].title })

    const divider = screen.getByText('Ниже — прочитанные публикации')
    expect(isBefore(titleLink(items[1]), divider)).toBe(true)
    expect(isBefore(divider, titleLink(items[2]))).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Важное' }))
    await screen.findByRole('button', { name: 'Важное', pressed: true })
    await screen.findByRole('link', { name: items[0].title })
    expect(screen.queryByText(/прочитанные/)).toBeNull()
  })

  it('says there is nothing new when every article was met before', async () => {
    const items = makeFeedItems(2, { seen: true })
    serveFeed({ feed: () => makeFeedPage({ items }) })
    renderFeed()

    const divider = await screen.findByText('Новых публикаций нет, ниже — прочитанные')
    expect(isBefore(divider, titleLink(items[0]))).toBe(true)
  })

  it('suggests the interests when nothing matches them', async () => {
    serveFeed({ feed: () => makeFeedPage({ items: [] }) })
    renderFeed()

    expect(await screen.findByText('Подходящих публикаций не нашлось')).toBeInTheDocument()
    expect(
      screen.getByText('За две недели публикаций по вашим интересам не нашлось.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Настроить интересы' })).toHaveAttribute(
      'href',
      '/profiles',
    )
    expect(screen.queryByText(/^Лента собрана/)).toBeNull()
  })

  it('sends a reader with nothing saved to the new articles', async () => {
    const latest = makeFeedPage()
    serveFeed({ feed: () => latest })
    const { user } = renderFeed('/feed?tab=saved')
    expect(await screen.findByText('Сохранённого пока нет')).toBeInTheDocument()
    expect(
      screen.getByText('Здесь будут публикации, отложенные кнопкой «Сохранить».'),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Открыть новое' }))

    expect(await screen.findByRole('link', { name: latest.items[0].title })).toBeInTheDocument()
    expect(location()).toBe('/feed?tab=new')
  })

  it.each([
    ['/feed', '/feed', 'Подходящих публикаций не нашлось'],
    ['/feed?tab=saved', '/feed/saved', 'Сохранённого пока нет'],
  ])(
    'says why %s did not load instead of calling it empty',
    async (route, endpoint, emptyTitle) => {
      serveFeed()
      server.use(
        http.get(apiUrl(endpoint), () =>
          HttpResponse.json({ detail: 'Лента временно недоступна' }, { status: 503 }),
        ),
      )
      renderFeed(route)

      expect(await screen.findByRole('alert')).toHaveTextContent('Лента временно недоступна')
      expect(screen.queryByText(emptyTitle)).toBeNull()
    },
  )

  it('says when the feed on screen was ranked', async () => {
    const generatedAt = new Date(Date.now() - 3 * 60_000).toISOString()
    serveFeed({ feed: () => makeFeedPage({ generated_at: generatedAt }) })
    renderFeed()

    expect(await screen.findByText('Лента собрана 3 минуты назад')).toBeInTheDocument()
  })

  it('holds the place of the feed while it is being ranked', async () => {
    const latest = makeFeedPage()
    const ranking = gate()
    serveFeed()
    server.use(
      http.get(apiUrl('/feed'), async () => {
        await ranking.closed
        return HttpResponse.json(latest)
      }),
    )
    renderFeed()
    expect(await screen.findByRole('status', { name: 'Собираем ленту' })).toBeInTheDocument()

    ranking.open()

    expect(await screen.findByRole('link', { name: latest.items[0].title })).toBeInTheDocument()
    expect(screen.queryByRole('status', { name: 'Собираем ленту' })).toBeNull()
  })
})

describe('FeedPage taste', () => {
  it('puts what the feed is built from beside it on a wide screen and follows the marks', async () => {
    setMediaQueries({ '(min-width: 1280px)': true })
    let positives = 14
    const items = makeFeedItems(2)
    const sent = serveFeed({
      feed: () => makeFeedPage({ items }),
      taste: () => makeTaste({ positives }),
    })
    server.use(
      http.post(apiUrl('/feedback'), async ({ request }) => {
        sent.marks.push((await request.json()) as Mark)
        positives += 1
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { user } = renderFeed()
    const aside = await screen.findByRole('complementary')
    expect(await within(aside).findByText(/^18 отметок за последнее время/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Из чего собрана лента' })).toBeNull()

    await user.click(screen.getByRole('button', { name: `Больше такого: ${items[0].title}` }))

    expect(await within(aside).findByText(/^19 отметок за последнее время/)).toBeInTheDocument()
  })

  it('opens what the feed is built from as a sheet on a narrower screen', async () => {
    serveFeed()
    const { user } = renderFeed()

    await user.click(await screen.findByRole('button', { name: 'Из чего собрана лента' }))

    const sheet = await screen.findByRole('dialog', { name: 'Из чего собрана лента' })
    expect(await within(sheet).findByText(/^18 отметок за последнее время/)).toBeInTheDocument()
    expect(screen.queryByRole('complementary')).toBeNull()
  })

  it('asks for the taste again when it did not load', async () => {
    setMediaQueries({ '(min-width: 1280px)': true })
    serveFeed()
    server.use(
      http.get(
        apiUrl('/taste'),
        () => HttpResponse.json({ detail: 'Не удалось прочитать отметки' }, { status: 503 }),
        { once: true },
      ),
    )
    const { user } = renderFeed()
    const aside = await screen.findByRole('complementary')
    expect(await within(aside).findByRole('alert')).toHaveTextContent(
      'Не удалось прочитать отметки',
    )

    await user.click(within(aside).getByRole('button', { name: 'Повторить' }))

    expect(await within(aside).findByText(/^18 отметок за последнее время/)).toBeInTheDocument()
    expect(within(aside).queryByRole('alert')).toBeNull()
  })

  it('asks the reader for interests while the feed knows nothing about them', async () => {
    serveFeed({
      taste: () =>
        makeTaste({ facets: [makeTasteFacet({ kind: 'avoid', label: 'Курс биткоина' })] }),
    })
    const { user } = renderFeed()

    expect(await screen.findByText('Интересы пока не заданы')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Загрузить резюме' })).toHaveAttribute(
      'href',
      '/welcome',
    )
    expect(screen.getByRole('link', { name: 'Настроить интересы' })).toHaveAttribute(
      'href',
      '/profiles',
    )

    await user.click(screen.getByRole('button', { name: 'Сохранённое' }))
    await screen.findByText('Сохранённого пока нет')
    expect(screen.queryByText('Интересы пока не заданы')).toBeNull()
  })
})

describe('FeedPage in the look of a Telegram channel', () => {
  it('draws the articles as posts when the reader chose that look', async () => {
    const items = makeFeedItems(2)
    serveFeed({ me: makeMe({ feed_view: 'telegram' }), feed: () => makeFeedPage({ items }) })
    server.use(http.get(apiUrl('/sources/avatars'), () => HttpResponse.json({})))
    renderFeed()

    const post = await screen.findByRole('article', { name: items[0].title })
    expect(within(post).getByText(items[0].source_name)).toBeInTheDocument()
    expect(screen.getByRole('article', { name: items[1].title })).toBeInTheDocument()
  })

  it('switches the look beside the tabs at once and keeps it with the account', async () => {
    const items = makeFeedItems(2)
    const sent = serveFeed({ feed: () => makeFeedPage({ items }) })
    const answer = gate()
    server.use(
      http.get(apiUrl('/sources/avatars'), () => HttpResponse.json({})),
      // Held back, then handed on to the account above: the look comes first.
      http.patch(apiUrl('/auth/me/settings'), () => answer.closed),
    )
    const { user } = renderFeed()
    await screen.findByRole('link', { name: items[0].title })
    expect(screen.getByRole('radio', { name: 'Карточки' })).toBeChecked()
    expect(screen.queryByRole('article', { name: items[0].title })).toBeNull()

    await user.click(screen.getByRole('radio', { name: 'Как в Telegram' }))

    expect(screen.getByRole('radio', { name: 'Как в Telegram' })).toBeChecked()
    expect(await screen.findByRole('article', { name: items[0].title })).toBeInTheDocument()
    expect(sent.settings).toEqual([])
    answer.open()
    await waitFor(() => expect(sent.settings).toEqual([{ feed_view: 'telegram' }]))
    expect(screen.getByRole('radio', { name: 'Как в Telegram' })).toBeChecked()
  })

  it('puts the look back and says why when the server refuses it', async () => {
    const items = makeFeedItems(2)
    serveFeed({ feed: () => makeFeedPage({ items }) })
    // The account asked again after the refusal waits: only the rollback can
    // bring the cards back.
    const reread = gate()
    let isHeld = false
    let isReread = false
    server.use(
      http.get(apiUrl('/sources/avatars'), () => HttpResponse.json({})),
      http.get(apiUrl('/auth/me'), async () => {
        if (!isHeld) return
        isReread = true
        await reread.closed
      }),
      http.patch(apiUrl('/auth/me/settings'), () =>
        HttpResponse.json({ detail: 'Настройки сейчас не сохраняются' }, { status: 503 }),
      ),
    )
    const { user } = renderFeed()
    await screen.findByRole('link', { name: items[0].title })
    isHeld = true

    await user.click(screen.getByRole('radio', { name: 'Как в Telegram' }))

    await waitFor(() => expect(isReread).toBe(true))
    expect(screen.getByRole('radio', { name: 'Карточки' })).toBeChecked()
    expect(screen.queryByRole('article', { name: items[0].title })).toBeNull()
    reread.open()
    expect(await screen.findByText('Вид ленты не сохранился')).toBeInTheDocument()
    expect(screen.getByText('Настройки сейчас не сохраняются')).toBeInTheDocument()
  })
})
