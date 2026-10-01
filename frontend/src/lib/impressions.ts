import { useCallback, useRef } from 'react'
import { api } from './api'
import type { ListSlot, Placement, SeenItem } from './api'

export type SeenContext = 'feed' | 'digest'

// Half of the card on screen for most of a second: read or at least scanned,
// not flicked past.
const VISIBLE_SHARE = 0.5
const VISIBLE_MS = 800
const FLUSH_MS = 4000
const BATCH = 60
const NO_LIST = ''

// Per context, then per list (a feed snapshot or a digest): what to send.
const queued: Record<SeenContext, Map<string, Map<number, SeenItem>>> = {
  feed: new Map(),
  digest: new Map(),
}
// Reported once per page load: a second look says nothing new.
const reported: Record<SeenContext, Set<number>> = { feed: new Set(), digest: new Set() }
let queuedCount = 0
let timer: number | undefined

function flush(): void {
  window.clearTimeout(timer)
  timer = undefined
  queuedCount = 0
  for (const context of ['feed', 'digest'] as const) {
    for (const [listId, byArticle] of queued[context]) {
      const items = [...byArticle.values()]
      for (let start = 0; start < items.length; start += BATCH) {
        // An impression is a hint, not a record: a lost batch is not retried.
        void api
          .recordImpressions(items.slice(start, start + BATCH), context, listId || null)
          .catch(() => undefined)
      }
    }
    queued[context].clear()
  }
}

function seen(articleId: number, context: SeenContext, placement: Placement | undefined): void {
  if (reported[context].has(articleId)) return
  reported[context].add(articleId)
  const listId = placement?.listId ?? NO_LIST
  const list = queued[context].get(listId) ?? new Map<number, SeenItem>()
  queued[context].set(listId, list)
  list.set(articleId, {
    article_id: articleId,
    position: placement?.position ?? 0,
    slot: placement?.slot ?? (context === 'digest' ? 'digest' : 'ranked'),
  })
  queuedCount += 1
  if (queuedCount >= BATCH) flush()
  else timer ??= window.setTimeout(flush, FLUSH_MS)
}

if (typeof document !== 'undefined') {
  // Leaving the page sends what is left; the request outlives the page.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'hidden') return
    // A card on screen when the tab was left has not been looked at long enough.
    for (const item of watched.values()) {
      if (item.wait !== undefined) window.clearTimeout(item.wait)
      item.wait = undefined
    }
    flush()
  })
}

type Watch = {
  articleId: number
  context: SeenContext
  placement?: Placement
  since?: number
  wait?: number
}
const watched = new Map<Element, Watch>()
let observer: IntersectionObserver | null = null

function observe(element: Element, watch: Watch): void {
  observer ??= new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const item = watched.get(entry.target)
        if (!item) continue
        // A card taller than two screens never shows half of itself: half the
        // screen filled by it counts as well.
        const screen = entry.rootBounds?.height ?? window.innerHeight
        const isVisible =
          entry.intersectionRatio >= VISIBLE_SHARE ||
          entry.intersectionRect.height >= screen * VISIBLE_SHARE
        if (isVisible) {
          item.wait ??= window.setTimeout(() => {
            seen(item.articleId, item.context, item.placement)
            observer?.unobserve(entry.target)
            watched.delete(entry.target)
          }, VISIBLE_MS)
        } else if (item.wait !== undefined) {
          window.clearTimeout(item.wait)
          item.wait = undefined
        }
      }
    },
    { threshold: [0, VISIBLE_SHARE] },
  )
  watched.set(element, watch)
  observer.observe(element)
}

function forget(element: Element): void {
  const item = watched.get(element)
  if (item?.wait !== undefined) window.clearTimeout(item.wait)
  watched.delete(element)
  observer?.unobserve(element)
}

/**
 * A ref for a card: the article counts as seen once it has been on screen.
 * A card the reader has marked is not watched: the mark says more. React
 * calls the ref with null on unmount, which stops the watch.
 */
export function useSeen(
  articleId: number,
  context: SeenContext,
  isWatched = true,
  placement?: Placement,
) {
  const node = useRef<Element | null>(null)
  // The placement arrives as a new object on every render; the watch is
  // renewed only when what it says changes.
  const listId = placement?.listId ?? null
  const position = placement?.position ?? 0
  const slot: ListSlot | undefined = placement?.slot
  return useCallback(
    (element: Element | null) => {
      if (node.current && node.current !== element) forget(node.current)
      node.current = element
      if (element && isWatched && !reported[context].has(articleId)) {
        const where = slot ? { listId, position, slot } : undefined
        observe(element, { articleId, context, placement: where })
      }
    },
    [articleId, context, isWatched, listId, position, slot],
  )
}
