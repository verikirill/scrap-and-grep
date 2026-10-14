import { screen } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { ArticleRead } from '../lib/api'
import { makeArticleRead } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { ArticlePage } from './ArticlePage'

const ARTICLE = makeArticleRead({ id: 501, url: 'https://www.securitylab.ru/news/562811.php' })

/** The article the API reads; the ids it was asked for. */
function serveArticle(article: ArticleRead = ARTICLE) {
  const asked: string[] = []
  server.use(
    http.get(apiUrl('/articles/:id'), ({ params }) => {
      asked.push(String(params.id))
      return HttpResponse.json(article)
    }),
  )
  return asked
}

function renderArticle(id: string | number = ARTICLE.id) {
  return renderWithProviders(<ArticlePage />, {
    route: `/articles/${id}`,
    path: '/articles/:articleId',
  })
}

describe('ArticlePage', () => {
  it('shows the article and puts the reader at its headline', async () => {
    serveArticle()
    renderArticle()

    const heading = await screen.findByRole('heading', { level: 1, name: ARTICLE.title })
    expect(heading).toHaveFocus()
    expect(screen.getByText(ARTICLE.source_name)).toBeInTheDocument()
    expect(screen.getByText('4 мин чтения')).toBeInTheDocument()
    expect(screen.getByText('Алексей Смирнов')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Таблица' })).toBeInTheDocument()
    expect(screen.queryByText(/не вернул страницу/)).toBeNull()
  })

  it('links to the original by the site’s name, at the top and at the end', async () => {
    serveArticle()
    renderArticle()

    const top = await screen.findByRole('link', { name: 'Оригинал' })
    const end = screen.getByRole('link', { name: 'Читать на securitylab.ru' })
    for (const link of [top, end]) {
      expect(link).toHaveAttribute('href', ARTICLE.url)
      expect(link).toHaveAttribute('target', '_blank')
    }
    expect(
      screen.getByText('Текст и картинки со страницы securitylab.ru; права на них у источника.'),
    ).toBeInTheDocument()
  })

  it('says only the feed text is shown when the site did not give the page', async () => {
    serveArticle({ ...ARTICLE, complete: false })
    renderArticle()

    expect(
      await screen.findByText(
        /Сайт securitylab\.ru не вернул страницу, поэтому показан только текст из ленты/,
      ),
    ).toBeInTheDocument()
  })

  it('says there is no text when the source had only a headline', async () => {
    serveArticle({ ...ARTICLE, blocks: [] })
    renderArticle()

    expect(await screen.findByText('Текста нет')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Оригинал' })).toBeInTheDocument()
  })

  it('does not link to an original address that could run code', async () => {
    serveArticle({ ...ARTICLE, url: 'javascript:alert(1)' })
    renderArticle()

    await screen.findByRole('heading', { level: 1, name: ARTICLE.title })
    expect(screen.queryByRole('link', { name: 'Оригинал' })).toBeNull()
    expect(screen.getByText('Оригинал').closest('a')).not.toHaveAttribute('href')
  })

  it('says the article is not found for an address that is not an article, without asking', async () => {
    const asked = serveArticle()
    renderArticle('abc')

    expect(await screen.findByText('Статья не найдена')).toBeInTheDocument()
    expect(asked).toEqual([])
  })

  it('says the article is not found when the server has none', async () => {
    server.use(
      http.get(apiUrl('/articles/:id'), () =>
        HttpResponse.json({ detail: 'Not found' }, { status: 404 }),
      ),
    )
    renderArticle()

    expect(await screen.findByText('Статья не найдена')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Оригинал' })).toBeNull()
  })

  it('shows another failure as it is', async () => {
    server.use(
      http.get(apiUrl('/articles/:id'), () =>
        HttpResponse.json({ detail: 'Источник не отвечает' }, { status: 502 }),
      ),
    )
    renderArticle()

    expect(await screen.findByRole('alert')).toHaveTextContent('Источник не отвечает')
  })

  it('goes back to the feed when the article was the first page opened', async () => {
    serveArticle()
    const { user } = renderArticle()
    await screen.findByRole('heading', { level: 1, name: ARTICLE.title })

    await user.click(screen.getByRole('button', { name: 'Назад' }))

    expect(screen.getByTestId('location')).toHaveTextContent('/feed')
  })
})
