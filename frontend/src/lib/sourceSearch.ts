import type { Source, SourceKind } from './api'
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
