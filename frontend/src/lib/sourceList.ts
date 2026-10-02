import type { Source, SourceCategory, SourceKind } from './api'
import { CATEGORY_LABELS } from './format'

/** Words a source of each kind is also found by. */
const KIND_WORDS: Record<SourceKind, string> = {
  rss: 'rss atom лента',
  telegram: 'telegram телеграм канал',
  pt_trending: 'positive technologies трендовые уязвимости',
}

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
  { key: 'web', label: 'Сайты', kinds: ['rss', 'pt_trending'] },
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
