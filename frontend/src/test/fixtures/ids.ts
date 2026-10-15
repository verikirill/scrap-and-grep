// Counters for ids that must differ between objects built in one test file.
// Vitest loads the modules anew for every file, so each file starts from scratch.

/** start + 1, start + 2 and so on: one step per call. */
export function counter(start = 0): () => number {
  let last = start
  return () => {
    last += 1
    return last
  }
}

/** One counter for every builder of an article: a digest entry, a feed item and
 * a search hit built in one test are never taken for the same article. */
export const nextArticleId = counter(100)
