import { createContext, useContext, useState } from 'react'

/**
 * The order cards rise in on a fresh page, as the comparison shows its
 * blocks: each card that mounts while the page is fresh takes the next place
 * in line, and a card that comes later with its data rises at once.
 */
export type Entrance = { start: number; next: () => number }

export const EntranceContext = createContext<Entrance | null>(null)

// How long a page counts as fresh, and the gap between two cards.
const FRESH_MS = 800
const STEP_S = 0.06
const MAX_STEPS = 8

export function newEntrance(): Entrance {
  let count = 0
  return { start: performance.now(), next: () => count++ }
}

/** The delay of a card's rise; null outside a page (a dialog), where nothing rises. */
export function useEntranceDelay(): number | null {
  const entrance = useContext(EntranceContext)
  const [delay] = useState(() => {
    if (!entrance) return null
    if (performance.now() - entrance.start > FRESH_MS) return 0
    return Math.min(entrance.next(), MAX_STEPS) * STEP_S
  })
  return delay
}
