import { screen, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { ArticleRead, ArticleTranslation } from '../lib/api'
import { makeArticleRead, makeArticleTranslation, makeEnglishArticleRead } from '../test/fixtures'
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

  it('shows a server failure in the server’s words, over the whole page', async () => {
    server.use(
      http.get(apiUrl('/articles/:id'), () =>
        HttpResponse.json({ detail: 'Источник не отвечает' }, { status: 502 }),
      ),
    )
    renderArticle()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Источник не отвечает')
    expect(screen.getByRole('heading', { level: 1, name: 'Статья не открылась' })).toBeVisible()
    expect(alert.querySelector('img')).toHaveAttribute('src', '/brand/errors/503.webp')
  })

  it('goes back to the feed when the article was the first page opened', async () => {
    serveArticle()
    const { user } = renderArticle()
    await screen.findByRole('heading', { level: 1, name: ARTICLE.title })

    await user.click(screen.getByRole('button', { name: 'Назад' }))

    expect(screen.getByTestId('location')).toHaveTextContent('/feed')
  })
})

const ENGLISH = makeEnglishArticleRead({ id: 502 })
const TRANSLATION = makeArticleTranslation({ id: 502 })
const TRANSLATED_TITLE = TRANSLATION.title ?? ''
const CHOICE_KEY = 'radar-reader-original'

/** The translation the API gives, or its answer to come; what it was asked. */
function serveTranslation(answer: ArticleTranslation | Promise<ArticleTranslation> = TRANSLATION) {
  const asked: string[] = []
  server.use(
    http.get(apiUrl('/articles/:id/translation'), async ({ params, request }) => {
      asked.push(`${String(params.id)}${new URL(request.url).search}`)
      return HttpResponse.json(await answer)
    }),
  )
  return asked
}

describe('ArticlePage in translation', () => {
  it('shows an English article in Russian, with a quiet line saying so', async () => {
    serveArticle(ENGLISH)
    const asked = serveTranslation()
    renderArticle(ENGLISH.id)

    const heading = await screen.findByRole('heading', { level: 1, name: TRANSLATED_TITLE })
    expect(heading).toHaveFocus()
    expect(heading.closest('article')).toHaveAttribute('lang', 'ru')
    expect(screen.getByText('Переведено с английского')).toBeInTheDocument()
    expect(screen.getByText(/Производитель выпустил прошивку/)).toBeInTheDocument()
    expect(screen.queryByText(/The vendor released/)).toBeNull()
    expect(screen.getByRole('button', { name: 'Показать оригинал' })).toBeInTheDocument()
    expect(asked).toEqual(['502?to=ru'])
  })

  it('switches to the original and back, and keeps the choice for the next article', async () => {
    serveArticle(ENGLISH)
    const asked = serveTranslation()
    const { user } = renderArticle(ENGLISH.id)
    await screen.findByRole('heading', { level: 1, name: TRANSLATED_TITLE })

    await user.click(screen.getByRole('button', { name: 'Показать оригинал' }))

    const original = screen.getByRole('heading', { level: 1, name: ENGLISH.title })
    expect(original.closest('article')).toHaveAttribute('lang', 'en')
    expect(screen.getByText('Оригинал на английском')).toBeInTheDocument()
    expect(screen.getByText(/The vendor released firmware/)).toBeInTheDocument()
    expect(localStorage.getItem(CHOICE_KEY)).toBe('1')

    await user.click(screen.getByRole('button', { name: 'Показать перевод' }))

    expect(screen.getByRole('heading', { level: 1, name: TRANSLATED_TITLE })).toBeVisible()
    expect(localStorage.getItem(CHOICE_KEY)).toBe('0')
    // The translation was kept: switching back asks the API nothing.
    expect(asked).toHaveLength(1)
  })

  it('opens the original first when the reader chose it last time, and translates on request', async () => {
    localStorage.setItem(CHOICE_KEY, '1')
    serveArticle(ENGLISH)
    const asked = serveTranslation()
    const { user } = renderArticle(ENGLISH.id)

    expect(await screen.findByRole('heading', { level: 1, name: ENGLISH.title })).toHaveFocus()
    expect(asked).toEqual([])

    await user.click(screen.getByRole('button', { name: 'Показать перевод' }))

    expect(await screen.findByRole('heading', { level: 1, name: TRANSLATED_TITLE })).toBeVisible()
    expect(asked).toHaveLength(1)
  })

  it('shows the shape of the text while the model translates it', async () => {
    let answer: (value: ArticleTranslation) => void = () => {}
    serveArticle(ENGLISH)
    serveTranslation(new Promise<ArticleTranslation>((resolve) => (answer = resolve)))
    renderArticle(ENGLISH.id)

    const loading = await screen.findByRole('status', { name: 'Переводим статью' })
    expect(loading).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByText('Переводим с английского')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 1 })).toBeNull()
    expect(screen.queryByText(/The vendor released/)).toBeNull()
    expect(screen.getByText(ENGLISH.source_name)).toBeInTheDocument()

    answer(TRANSLATION)

    const heading = await screen.findByRole('heading', { level: 1, name: TRANSLATED_TITLE })
    await waitFor(() => expect(heading).toHaveFocus())
    expect(screen.queryByRole('status', { name: 'Переводим статью' })).toBeNull()
  })

  it('shows the original with the reason when the article cannot be translated now', async () => {
    const reason = 'Модель сейчас не смогла перевести статью. Попробуйте открыть её позже.'
    serveArticle(ENGLISH)
    serveTranslation(
      makeArticleTranslation({
        id: 502,
        status: 'unavailable',
        title: null,
        blocks: null,
        reason,
      }),
    )
    renderArticle(ENGLISH.id)

    expect(await screen.findByText(`${reason} Показан оригинал.`)).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: ENGLISH.title })).toBeVisible()
    expect(screen.getByText(/The vendor released firmware/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Показать оригинал' })).toBeNull()
  })

  it('shows the original when the translation request fails', async () => {
    serveArticle(ENGLISH)
    server.use(
      http.get(apiUrl('/articles/:id/translation'), () =>
        HttpResponse.json({ detail: 'Сервер недоступен' }, { status: 502 }),
      ),
    )
    renderArticle(ENGLISH.id)

    expect(
      await screen.findByText('Перевод сейчас недоступен. Показан оригинал.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: ENGLISH.title })).toBeVisible()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('says a Chinese article was translated from Chinese', async () => {
    const chinese = makeEnglishArticleRead({
      id: 503,
      title: '西门子修复 S7-1500 漏洞',
      language: 'ru',
      text_language: 'zh',
    })
    serveArticle(chinese)
    serveTranslation(makeArticleTranslation({ id: 503, source_language: 'zh' }))
    const { user } = renderArticle(chinese.id)

    expect(await screen.findByText('Переведено с китайского')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Показать оригинал' }))
    expect(screen.getByText('Оригинал на китайском')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: chinese.title })).toBeVisible()
  })

  it.each([
    [1, 'Переведено с китайского, 1 фрагмент оставлен в оригинале'],
    [3, 'Переведено с китайского, 3 фрагмента оставлены в оригинале'],
    [5, 'Переведено с китайского, 5 фрагментов оставлены в оригинале'],
    [21, 'Переведено с китайского, 21 фрагмент оставлен в оригинале'],
  ])('says how many fragments the model left in the original: %i', async (kept, note) => {
    const chinese = makeEnglishArticleRead({
      id: 504,
      title: '西门子修复漏洞',
      text_language: 'zh',
    })
    serveArticle(chinese)
    serveTranslation(
      makeArticleTranslation({ id: 504, source_language: 'zh', kept_original: kept }),
    )
    renderArticle(chinese.id)

    expect(await screen.findByText(note)).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: TRANSLATED_TITLE })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Показать оригинал' })).toBeInTheDocument()
  })

  it('leaves a Russian article as it is and asks for no translation', async () => {
    serveArticle()
    const asked = serveTranslation()
    renderArticle()

    await screen.findByRole('heading', { level: 1, name: ARTICLE.title })
    expect(screen.queryByText(/Переведено|Переводим|Оригинал на/)).toBeNull()
    expect(screen.queryByRole('button', { name: /Показать/ })).toBeNull()
    expect(asked).toEqual([])
  })

  it('keeps the original without a note when the API finds nothing to translate', async () => {
    serveArticle(ENGLISH)
    serveTranslation(
      makeArticleTranslation({ id: 502, status: 'original', title: null, blocks: null }),
    )
    renderArticle(ENGLISH.id)

    expect(await screen.findByRole('heading', { level: 1, name: ENGLISH.title })).toBeVisible()
    await waitFor(() => expect(screen.queryByText('Переводим с английского')).toBeNull())
    expect(screen.queryByRole('button', { name: /Показать/ })).toBeNull()
  })
})
