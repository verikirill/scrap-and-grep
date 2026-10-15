import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Article, Page } from '../../lib/api'
import {
  makeArticles,
  makeArticlesPage,
  makeTimeline,
  makeTimelinePoint,
} from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { ArticlesList } from './ArticlesList'

type Asked = { q: string | null; category: string[]; limit: string | null; offset: string | null }

/** Answer the search with `answer`; what each request asked for is kept in order. */
function serveArticles(answer: (asked: Asked) => Page<Article>) {
  const asked: Asked[] = []
  server.use(
    http.get(apiUrl('/articles'), ({ request }) => {
      const params = new URL(request.url).searchParams
      const one = {
        q: params.get('q'),
        category: params.getAll('category'),
        limit: params.get('limit'),
        offset: params.get('offset'),
      }
      asked.push(one)
      return HttpResponse.json(answer(one))
    }),
    http.get(apiUrl('/articles/timeline'), ({ request }) =>
      new URL(request.url).searchParams.get('days') === '14'
        ? HttpResponse.json(makeTimeline(14, { count: 10 }))
        : HttpResponse.json([]),
    ),
  )
  return asked
}

/** The line over the list: «Всего» or, while searching, «Найдено», with the count. */
const countLine = () => screen.getByText(/^(Всего|Найдено):/)
const searchBox = () => screen.getByRole('searchbox', { name: 'Поиск по публикациям' })

describe('ArticlesList', () => {
  it('lists the latest articles with their source, category and full text, under a chart of two weeks', async () => {
    const [first, second] = makeArticles(2)
    const asked = serveArticles(() =>
      makeArticlesPage({ items: [first, { ...second, has_full_text: false, summary: '' }] }),
    )
    renderWithProviders(<ArticlesList />)

    const title = await screen.findByRole('link', { name: first.title })
    expect(title).toHaveAttribute('href', `/articles/${first.id}`)
    expect(
      screen.getByRole('link', { name: `«${first.title}» на сайте источника` }),
    ).toHaveAttribute('href', first.url)
    const [firstRow, secondRow] = screen.getAllByRole('listitem')
    expect(within(firstRow).getByText(first.summary)).toBeInTheDocument()
    expect(within(firstRow).getByText(first.source_name)).toBeInTheDocument()
    expect(within(firstRow).getByText('полный текст')).toBeInTheDocument()
    expect(within(secondRow).queryByText('полный текст')).toBeNull()
    expect(screen.getByText(/^Всего:/)).toHaveTextContent('Всего: 2')
    expect(
      await screen.findByRole('img', { name: 'Публикаций за 14 дней: 140' }),
    ).toBeInTheDocument()
    expect(asked).toEqual([{ q: null, category: [], limit: '30', offset: '0' }])
  })

  it('sums the categories of a day and shows the last fourteen days only', async () => {
    serveArticles(() => makeArticlesPage())
    server.use(
      http.get(apiUrl('/articles/timeline'), () =>
        HttpResponse.json([
          ...makeTimeline(16, { count: 10 }),
          makeTimelinePoint({ category: 'ics', count: 5 }),
        ]),
      ),
    )
    renderWithProviders(<ArticlesList />)

    expect(
      await screen.findByRole('img', { name: 'Публикаций за 14 дней: 145' }),
    ).toBeInTheDocument()
    await screen.findByText(/^Всего:/)
  })

  it('searches once typing pauses and narrows the search by categories', async () => {
    const [hit, similar] = makeArticles(2)
    const asked = serveArticles(({ q }) =>
      q
        ? makeArticlesPage({ items: [hit, { ...similar, match: 'meaning' }] })
        : makeArticlesPage({ items: makeArticles(3) }),
    )
    const { user } = renderWithProviders(<ArticlesList />)
    await screen.findByText(/^Всего:/)

    await user.type(searchBox(), ' SCADA ')

    // While the answer is on its way the last list stays, dimmed.
    await waitFor(() => expect(countLine()).toHaveTextContent('Найдено: 2'))
    // The words of the query come first; a match by meaning follows under a line of its own.
    expect(screen.getByText('Похоже по смыслу')).toBeInTheDocument()
    const [first, second] = screen.getAllByRole('listitem')
    expect(within(first).queryByText('по смыслу')).toBeNull()
    expect(within(second).getByText('по смыслу')).toBeInTheDocument()

    const ics = within(screen.getByRole('group', { name: 'Категории' })).getByRole('button', {
      name: 'АСУ ТП',
    })
    await user.click(ics)
    expect(ics).toHaveAttribute('aria-pressed', 'true')

    await waitFor(() => expect(asked).toHaveLength(3))
    // One request for the typed word, not one per letter.
    expect(asked.map(({ q, category }) => ({ q, category }))).toEqual([
      { q: null, category: [] },
      { q: 'SCADA', category: [] },
      { q: 'SCADA', category: ['ics'] },
    ])
    await waitFor(() => expect(countLine()).toHaveTextContent('Найдено: 2'))
  })

  it('says when nothing was found', async () => {
    serveArticles(({ q }) => makeArticlesPage({ items: q ? [] : makeArticles(1) }))
    const { user } = renderWithProviders(<ArticlesList />)
    await screen.findByText(/^Всего:/)

    await user.type(searchBox(), 'гидроэлектростанция Марса')

    expect(await screen.findByText('Ничего не найдено')).toBeInTheDocument()
    expect(screen.getByText(/^Найдено:/)).toHaveTextContent('Найдено: 0')
  })

  it('shows the next thirty articles on request, and no more button after the last', async () => {
    // The stories of the catalogue repeat after a dozen: number the titles.
    const all = makeArticles(31).map((article, index) => ({
      ...article,
      title: `${article.title} (${index + 1})`,
    }))
    const asked = serveArticles(({ offset }) => {
      const start = Number(offset)
      return makeArticlesPage({ items: all.slice(start, start + 30), total: 31, offset: start })
    })
    const { user } = renderWithProviders(<ArticlesList />)
    await screen.findByRole('link', { name: all[29].title })
    expect(screen.queryByRole('link', { name: all[30].title })).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Показать ещё' }))

    expect(await screen.findByRole('link', { name: all[30].title })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Показать ещё' })).toBeNull()
    expect(asked.map(({ offset }) => offset)).toEqual(['0', '30'])
  })

  it('shows why the articles could not be loaded', async () => {
    serveArticles(() => makeArticlesPage())
    server.use(
      http.get(apiUrl('/articles'), () =>
        HttpResponse.json({ detail: 'Поиск временно недоступен.' }, { status: 503 }),
      ),
    )
    renderWithProviders(<ArticlesList />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Поиск временно недоступен.')
    await screen.findByRole('img', { name: /^Публикаций за 14 дней/ })
  })
})
