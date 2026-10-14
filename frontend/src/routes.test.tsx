import { afterEach, describe, expect, it, vi } from 'vitest'

const PAGES = [
  'FeedPage',
  'ProfilesPage',
  'SourcesPage',
  'ComparePage',
  'ChannelsPage',
  'AccountPage',
  'WelcomePage',
  'SharePage',
  'AnalyticsPage',
  'ArticlePage',
]

// The pages' code as the browser fetches it: a test sees which pages were
// asked for, and can make one fail to arrive.
const loaded: string[] = []
const failing = new Set<string>()

/** The routes module as a fresh page load has it: no page fetched yet. */
async function freshRoutes() {
  vi.resetModules()
  loaded.length = 0
  failing.clear()
  for (const name of PAGES) {
    vi.doMock(`./pages/${name}`, () => {
      loaded.push(name)
      if (failing.has(name)) throw new Error(`Failed to fetch dynamically imported module: ${name}`)
      return { [name]: () => null }
    })
  }
  return import('./routes')
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('prefetchRoute', () => {
  it('fetches the code of a section the pointer rests on', async () => {
    const { prefetchRoute } = await freshRoutes()
    prefetchRoute('/sources')
    await vi.waitFor(() => expect(loaded).toEqual(['SourcesPage']))
  })

  it('passes over the digest section, whose page comes with the app', async () => {
    const { prefetchRoute } = await freshRoutes()
    // The sidebar asks for every section it shows, the digest one included.
    expect(() => prefetchRoute('/')).not.toThrow()
    prefetchRoute('/feed')
    await vi.waitFor(() => expect(loaded).toEqual(['FeedPage']))
  })

  it('asks again for a page whose code failed to arrive', async () => {
    const { prefetchRoute } = await freshRoutes()
    failing.add('FeedPage')
    prefetchRoute('/feed')
    await vi.waitFor(() => expect(loaded).toEqual(['FeedPage']))

    // The network is back: the next hover fetches the page again.
    failing.clear()
    await vi.waitFor(() => {
      prefetchRoute('/feed')
      expect(loaded).toEqual(['FeedPage', 'FeedPage'])
    })
  })
})

describe('prefetchAllRoutes', () => {
  it('fetches every page once the browser is idle, waiting four seconds at most', async () => {
    const { prefetchAllRoutes } = await freshRoutes()
    let whenIdle: (() => void) | undefined
    let asked: IdleRequestOptions | undefined
    vi.stubGlobal('requestIdleCallback', (run: () => void, options?: IdleRequestOptions) => {
      whenIdle = run
      asked = options
      return 1
    })
    prefetchAllRoutes()
    expect(asked).toEqual({ timeout: 4000 })
    expect(loaded).toEqual([])

    whenIdle?.()

    await vi.waitFor(() => expect([...loaded].sort()).toEqual([...PAGES].sort()))
  })

  it('fetches every page a moment and a half after start where the browser cannot tell when it is idle', async () => {
    const { prefetchAllRoutes } = await freshRoutes()
    vi.useFakeTimers()
    prefetchAllRoutes()

    vi.advanceTimersByTime(1499)
    expect(loaded).toEqual([])
    vi.advanceTimersByTime(1)

    await vi.waitFor(() => expect([...loaded].sort()).toEqual([...PAGES].sort()))
  })
})
