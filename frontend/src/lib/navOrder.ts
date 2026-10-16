/**
 * The menu in the reader's order. Sections the reader placed come first, as
 * placed; a section they have not placed yet (a new one, or one a new role
 * opened) follows in the app's own order.
 */
export function inReaderOrder<T extends { to: string }>(items: T[], order: string[]): T[] {
  const place = new Map(order.map((to, index) => [to, index]))
  const placed = items
    .filter((item) => place.has(item.to))
    .sort((a, b) => (place.get(a.to) ?? 0) - (place.get(b.to) ?? 0))
  return [...placed, ...items.filter((item) => !place.has(item.to))]
}

/** The paths with one moved a step up (-1) or down (1); at the edge nothing moves. */
export function movedBy(paths: string[], path: string, step: -1 | 1): string[] {
  const from = paths.indexOf(path)
  const to = from + step
  if (from < 0 || to < 0 || to >= paths.length) return paths
  const next = [...paths]
  next.splice(from, 1)
  next.splice(to, 0, path)
  return next
}
