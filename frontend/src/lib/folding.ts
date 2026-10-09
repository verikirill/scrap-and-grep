import type { DigestItem } from './api'

/** The folded titles with this one folded or unfolded; a new list, in its order. */
export function withFolded(titles: readonly string[], title: string, isFolded: boolean): string[] {
  const rest = titles.filter((item) => item !== title)
  return isFolded ? [...rest, title] : rest
}

/** What a folded section still tells: how many entries, how many urgent, how many ours. */
export function foldSummary(items: readonly DigestItem[]): { high: number; ours: number } {
  return {
    high: items.filter((item) => item.priority === 'high').length,
    ours: items.filter((item) => (item.ours ?? []).length > 0).length,
  }
}

// A long section shows its first entries and offers the rest.
export const SHOWN_AT_FIRST = 5
export const LONG_SECTION = 7

/** The entries a section shows before «Ещё N». */
export function firstEntries<T>(items: readonly T[], isAll: boolean): readonly T[] {
  return isAll || items.length <= LONG_SECTION ? items : items.slice(0, SHOWN_AT_FIRST)
}
