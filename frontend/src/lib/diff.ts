import type { PreviewItem } from './api'

export type Movement = 'new' | 'up' | 'down' | 'same'

export interface PreviewRow extends PreviewItem {
  movement: Movement
  /** Score change against the saved profile; 0 for articles that were not there. */
  delta: number
}

export interface PreviewDiff {
  rows: PreviewRow[]
  /** Articles the saved profile selects and the draft no longer does. */
  dropped: PreviewItem[]
}

const NOTICEABLE = 0.03

/**
 * Compare what a draft profile selects with what the saved one selects.
 * `baseline` is null while the saved profile's preview is still loading; the
 * draft is then shown without movement marks rather than all flagged as new.
 */
export function diffPreview(baseline: PreviewItem[] | null, draft: PreviewItem[]): PreviewDiff {
  const selected = draft.filter((item) => item.selected)
  if (baseline === null) {
    return { rows: selected.map((item) => ({ ...item, movement: 'same', delta: 0 })), dropped: [] }
  }
  const before = new Map(
    baseline.filter((item) => item.selected).map((item) => [item.article_id, item]),
  )
  const rows = selected.map((item): PreviewRow => {
    const previous = before.get(item.article_id)
    if (!previous) return { ...item, movement: 'new', delta: 0 }
    const delta = item.score - previous.score
    const movement = delta > NOTICEABLE ? 'up' : delta < -NOTICEABLE ? 'down' : 'same'
    return { ...item, movement, delta }
  })
  const kept = new Set(selected.map((item) => item.article_id))
  const dropped = [...before.values()].filter((item) => !kept.has(item.article_id))
  return { rows, dropped }
}
