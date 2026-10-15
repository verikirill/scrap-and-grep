// The personal feed: items with their reasons and score parts, pages of the
// ranked feed and of the saved tab, the count of fresh arrivals, and the taste
// the recommender keeps of the reader.
import type { FeedFresh, FeedItem, FeedPage, FeedReason, Taste, TasteFacet } from '../../lib/api'
import { NEWS, nth, sourceOf } from './catalog'
import { nextArticleId } from './ids'

export function makeFeedReason(overrides: Partial<FeedReason> = {}): FeedReason {
  return { kind: 'interest', text: 'Интерес «Уязвимости АСУ ТП»', ...overrides }
}

function feedItemAt(index: number): FeedItem {
  const news = nth(NEWS, index)
  const source = sourceOf(news)
  return {
    article_id: nextArticleId(),
    url: news.url,
    title: news.title,
    summary: news.summary,
    ...source,
    published_at: news.published_at,
    score: 0.82,
    explore: false,
    reading_minutes: 3,
    has_picture: false,
    seen: false,
    reasons: [
      makeFeedReason(),
      makeFeedReason({ kind: 'source', text: `Вы часто отмечаете «${source.source_name}»` }),
    ],
    // Keys of the score's parts as feed/cardParts.tsx explains them; they add up to the score.
    parts: { interest: 0.46, fresh: 0.18, source: 0.12, learned: 0.06 },
    reactions: [],
    slot: 'ranked',
    position: index + 1,
  }
}

/** The top item of the ranked feed: a story of SecurityLab.ru, source 1. */
export function makeFeedItem(overrides: Partial<FeedItem> = {}): FeedItem {
  return { ...feedItemAt(0), ...overrides }
}

/** `count` items of different stories and sources, at places 1 to count. */
export function makeFeedItems(count: number, overrides: Partial<FeedItem> = {}): FeedItem[] {
  return Array.from({ length: count }, (_, index) => ({ ...feedItemAt(index), ...overrides }))
}

/** The ranked feed in one page: its total is its length. Its `built_at` makes
 * FeedPage ask /feed/fresh; built_at: null keeps that request away. */
export function makeFeedPage(overrides: Partial<FeedPage> = {}): FeedPage {
  const items = overrides.items ?? makeFeedItems(3)
  return {
    items,
    total: items.length,
    limit: 20,
    offset: 0,
    generated_at: '2026-10-14T09:00:00Z',
    snapshot: '6f1d2c3b4a5948e7a6b5c4d3e2f10a9b',
    built_at: '2026-10-14T08:55:00Z',
    ...overrides,
  }
}

/** The saved tab: kept items with no score to explain, and no snapshot. */
export function makeSavedPage(overrides: Partial<FeedPage> = {}): FeedPage {
  const items =
    overrides.items ??
    makeFeedItems(2, { score: 0, reasons: [], parts: {}, reactions: ['save'], slot: 'saved' })
  return makeFeedPage({ snapshot: null, built_at: null, ...overrides, items })
}

export function makeFeedFresh(overrides: Partial<FeedFresh> = {}): FeedFresh {
  return { fresh: 0, ...overrides }
}

export function makeTasteFacet(overrides: Partial<TasteFacet> = {}): TasteFacet {
  return { kind: 'interest', label: 'Уязвимости АСУ ТП', weight: 1, ...overrides }
}

/** A reader with eighteen marks: stated interests, skills from the resume, one
 * learned topic and one shown less often. */
export function makeTaste(overrides: Partial<Taste> = {}): Taste {
  return {
    confidence: 0.62,
    positives: 14,
    negatives: 4,
    facets: [
      makeTasteFacet(),
      makeTasteFacet({ label: 'Атаки на энергетику' }),
      makeTasteFacet({ kind: 'resume', label: 'SCADA', weight: 0.7 }),
      makeTasteFacet({ kind: 'resume', label: 'МЭК 61850', weight: 0.6 }),
      makeTasteFacet({
        kind: 'learned',
        label: 'Фишинг от имени Минэнерго нацелен на подрядчиков сетевых компаний',
        weight: 0.5,
      }),
      makeTasteFacet({
        kind: 'avoid',
        label: 'Курс биткоина обновил исторический максимум',
        weight: 0.4,
      }),
    ],
    sources: [
      { source_id: 1, name: 'SecurityLab.ru', affinity: 0.42 },
      { source_id: 2, name: 'Kaspersky ICS CERT', affinity: 0.31 },
    ],
    ...overrides,
  }
}
