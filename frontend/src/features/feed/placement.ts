import type { FeedItem, Placement } from '../../lib/api'

/** Where an article stood in the feed, as its card reports it with a mark or a look. */
export const placementIn = (listId: string | null, item: FeedItem): Placement => ({
  listId,
  position: item.position,
  slot: item.slot,
})
