// Articles: a search hit and a page of them, arrivals per day for the chart, and
// an article opened in the reader with its text as blocks.
import type { Article, ArticleRead, Block, Page, Span, TimelinePoint } from '../../lib/api'
import { NEWS, daysBefore, nth, sourceOf } from './catalog'
import { nextArticleId } from './ids'

function articleAt(index: number): Article {
  const news = nth(NEWS, index)
  return {
    id: nextArticleId(),
    url: news.url,
    title: news.title,
    summary: news.summary,
    has_full_text: true,
    ...sourceOf(news),
    tags: [...news.tags],
    published_at: news.published_at,
    match: null,
  }
}

export function makeArticle(overrides: Partial<Article> = {}): Article {
  return { ...articleAt(0), ...overrides }
}

/** `count` articles of different stories and sources, newest first. */
export function makeArticles(count: number, overrides: Partial<Article> = {}): Article[] {
  return Array.from({ length: count }, (_, index) => ({ ...articleAt(index), ...overrides }))
}

/** A page of the search whose total is its length: there is no next page. */
export function makeArticlesPage(overrides: Partial<Page<Article>> = {}): Page<Article> {
  const items = overrides.items ?? makeArticles(3)
  return { items, total: items.length, limit: 30, offset: 0, ...overrides }
}

export function makeTimelinePoint(overrides: Partial<TimelinePoint> = {}): TimelinePoint {
  return { day: '2026-10-14T00:00:00Z', category: 'security', count: 42, ...overrides }
}

/** A point a day for `days` days up to 2026-10-14, with counts that vary. */
export function makeTimeline(
  days: number,
  overrides: Partial<TimelinePoint> = {},
): TimelinePoint[] {
  return Array.from({ length: days }, (_, index) =>
    makeTimelinePoint({
      day: daysBefore(days - 1 - index),
      count: 30 + ((index * 7) % 20),
      ...overrides,
    }),
  )
}

type BlockOf<Type extends Block['type']> = Extract<Block, { type: Type }>

export function makeSpan(overrides: Partial<Span> = {}): Span {
  return { text: 'Siemens выпустила исправленную прошивку.', ...overrides }
}

export function makeParagraphBlock(overrides: Partial<BlockOf<'p'>> = {}): BlockOf<'p'> {
  return {
    type: 'p',
    spans: [
      makeSpan({ text: 'Исследователи нашли в веб-сервере контроллеров ' }),
      makeSpan({ text: 'SIMATIC S7-1500', b: true }),
      makeSpan({ text: ' ошибку, которая позволяет без пароля перезагрузить ПЛК.' }),
    ],
    ...overrides,
  }
}

export function makeHeadingBlock(overrides: Partial<BlockOf<'h'>> = {}): BlockOf<'h'> {
  return { type: 'h', level: 2, text: 'Кого затрагивает уязвимость', ...overrides }
}

export function makeListBlock(overrides: Partial<BlockOf<'list'>> = {}): BlockOf<'list'> {
  return {
    type: 'list',
    ordered: false,
    items: [
      [makeSpan({ text: 'SIMATIC S7-1500 CPU с прошивкой до V3.1.5' })],
      [makeSpan({ text: 'ET 200SP Open Controller' })],
    ],
    ...overrides,
  }
}

export function makeQuoteBlock(overrides: Partial<BlockOf<'quote'>> = {}): BlockOf<'quote'> {
  return {
    type: 'quote',
    spans: [
      makeSpan({
        text: 'До установки обновления ограничьте доступ к веб-серверу контроллера.',
        i: true,
      }),
    ],
    ...overrides,
  }
}

export function makeCodeBlock(overrides: Partial<BlockOf<'code'>> = {}): BlockOf<'code'> {
  return { type: 'code', text: 'nmap -p 102,443 --open 10.20.0.0/24', ...overrides }
}

/** jsdom does not load the picture, so no handler is needed. */
export function makeImageBlock(overrides: Partial<BlockOf<'image'>> = {}): BlockOf<'image'> {
  return {
    type: 'image',
    id: 'img-1',
    alt: 'Контроллеры SIMATIC S7-1500 в шкафу управления',
    ...overrides,
  }
}

export function makeTableBlock(overrides: Partial<BlockOf<'table'>> = {}): BlockOf<'table'> {
  return {
    type: 'table',
    head: ['Модуль', 'Уязвимые версии', 'Исправление'],
    rows: [
      ['CPU 1515-2 PN', 'до V3.1.5', 'V3.1.5'],
      ['CPU 1518-4 PN/DP', 'до V3.1.5', 'V3.1.5'],
    ],
    ...overrides,
  }
}

/** The top story read from its page in full, with a block of every kind. */
export function makeArticleRead(overrides: Partial<ArticleRead> = {}): ArticleRead {
  const news = NEWS[0]
  return {
    id: nextArticleId(),
    url: news.url,
    title: news.title,
    author: 'Алексей Смирнов',
    ...sourceOf(news),
    tags: [...news.tags],
    published_at: news.published_at,
    reading_minutes: 4,
    complete: true,
    blocks: [
      makeParagraphBlock(),
      makeImageBlock(),
      makeHeadingBlock(),
      makeListBlock(),
      makeTableBlock(),
      makeParagraphBlock({
        spans: [makeSpan({ text: 'Проверить, видны ли контроллеры из корпоративной сети:' })],
      }),
      makeCodeBlock(),
      makeQuoteBlock(),
      makeParagraphBlock({
        spans: [
          makeSpan({ text: 'Бюллетень производителя: ' }),
          makeSpan({
            text: 'SSA-482956',
            href: 'https://cert-portal.siemens.com/productcert/html/ssa-482956.html',
          }),
        ],
      }),
    ],
    ...overrides,
  }
}
