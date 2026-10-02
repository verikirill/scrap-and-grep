import type { FetchMethod, Source, SourceCategory, SourceKind } from './api'
import { CATEGORY_LABELS } from './format'

/** Words a source of each kind is also found by. */
const KIND_WORDS: Record<SourceKind, string> = {
  rss: 'rss atom лента',
  telegram: 'telegram телеграм канал',
  page: 'страница сайт без ленты',
  wordpress: 'wordpress api',
  pt_trending: 'positive technologies трендовые уязвимости',
}

/** What a source is, in a word, where it is not a plain feed. */
export const KIND_LABELS: Partial<Record<SourceKind, string>> = {
  page: 'Страница',
  wordpress: 'WordPress API',
  pt_trending: 'Страница',
}

/** The fetch ladder's steps above a plain request, as a reader would name them. */
const FETCH_LABELS: Record<Exclude<FetchMethod, 'plain'>, string> = {
  browser_headers: 'Заголовки браузера',
  impersonate: 'Отпечаток Chrome',
  browser: 'Браузер',
  solver: 'FlareSolverr',
}

/**
 * How a site that refuses a bot is read: the step of the ladder and its
 * reason, or null for a source a plain request reads.
 */
export function readVia(
  source: Pick<Source, 'fetch_method' | 'fetch_note' | 'fetch_via_proxy'>,
): { label: string; note: string | null } | null {
  const method = source.fetch_method
  const step = method && method !== 'plain' ? FETCH_LABELS[method] : null
  const label = [step, source.fetch_via_proxy ? 'через прокси' : null].filter(Boolean).join(', ')
  return label ? { label, note: source.fetch_note ?? null } : null
}

/** A source behind protection: read above a plain request or through a proxy. */
export const isProtected = (source: Source): boolean => readVia(source) !== null

function normalize(text: string): string {
  return text.toLowerCase().replaceAll('ё', 'е')
}

/** The words of a query; "@true_secator" is looked for as "true_secator". */
export function queryWords(query: string): string[] {
  return normalize(query)
    .split(/\s+/)
    .map((word) => word.replace(/^@/, ''))
    .filter(Boolean)
}

/**
 * Whether the source answers the query: every word of it is found in the
 * name, the addresses, the category or the kind. "@true_secator" finds the
 * channel, "t.me" all channels, "бду" the BDU feeds.
 */
export function matchesSource(source: Source, query: string): boolean {
  const words = queryWords(query)
  if (words.length === 0) return true
  const haystack = normalize(
    [
      source.name,
      source.slug,
      source.feed_url,
      source.site_url ?? '',
      CATEGORY_LABELS[source.category],
      KIND_WORDS[source.kind],
    ].join(' '),
  )
  return words.every((word) => haystack.includes(word))
}

export const CATEGORY_ORDER: SourceCategory[] = ['security', 'ics', 'energy', 'it', 'regulator']

/** How the list is split: by topic, or by where the news comes from. */
export type SourceGrouping = 'category' | 'kind'
/** By name, or by how many articles a source has brought, either way. */
export type SourceOrder = 'name' | 'most' | 'least'

export type SourceGroup = { key: string; label: string; sources: Source[] }

// The PT page is a site too: only Telegram channels stand apart.
const KIND_GROUPS: { key: string; label: string; kinds: SourceKind[] }[] = [
  { key: 'web', label: 'Сайты', kinds: ['rss', 'page', 'wordpress', 'pt_trending'] },
  { key: 'telegram', label: 'Telegram-каналы', kinds: ['telegram'] },
]

export function sortSources(sources: Source[], order: SourceOrder): Source[] {
  const byName = (a: Source, b: Source) => a.name.localeCompare(b.name, 'ru')
  if (order === 'name') return [...sources].sort(byName)
  const sign = order === 'most' ? -1 : 1
  return [...sources].sort((a, b) => sign * (a.articles - b.articles) || byName(a, b))
}

/** The sources in their groups, each group in the order asked; empty groups left out. */
export function groupSources(
  sources: Source[],
  grouping: SourceGrouping,
  order: SourceOrder,
): SourceGroup[] {
  const sorted = sortSources(sources, order)
  const groups =
    grouping === 'kind'
      ? KIND_GROUPS.map(({ key, label, kinds }) => ({
          key,
          label,
          sources: sorted.filter((source) => kinds.includes(source.kind)),
        }))
      : CATEGORY_ORDER.map((category) => ({
          key: category,
          label: CATEGORY_LABELS[category],
          sources: sorted.filter((source) => source.category === category),
        }))
  return groups.filter((group) => group.sources.length > 0)
}
