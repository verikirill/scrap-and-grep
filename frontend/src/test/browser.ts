// What jsdom lacks and the app uses: media queries, resize and intersection
// observers, scrolling and server-sent events. Each fake is small and can be
// steered from a test: a media query matched, a card scrolled into view, a
// progress event received.

type Listener = (event: { matches: boolean; media: string }) => void

const queries = new Map<string, boolean>()
const mediaListeners = new Map<string, Set<Listener>>()

/** Make media queries match (true) or not; listeners of a changed query hear of it. */
export function setMediaQueries(next: Record<string, boolean>): void {
  for (const [media, matches] of Object.entries(next)) {
    const changed = queries.get(media) !== matches
    queries.set(media, matches)
    if (changed)
      for (const listener of mediaListeners.get(media) ?? []) listener({ matches, media })
  }
}

function matchMedia(media: string): MediaQueryList {
  const listeners = mediaListeners.get(media) ?? new Set<Listener>()
  mediaListeners.set(media, listeners)
  return {
    media,
    get matches() {
      return queries.get(media) ?? false
    },
    onchange: null,
    addEventListener: (_type: string, listener: Listener) => listeners.add(listener),
    removeEventListener: (_type: string, listener: Listener) => listeners.delete(listener),
    addListener: (listener: Listener) => listeners.add(listener),
    removeListener: (listener: Listener) => listeners.delete(listener),
    dispatchEvent: () => false,
  } as unknown as MediaQueryList
}

class FakeResizeObserver implements ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

/** Every IntersectionObserver the app made, to report what is on screen. */
export const intersectionObservers: FakeIntersectionObserver[] = []

export class FakeIntersectionObserver implements IntersectionObserver {
  readonly root = null
  readonly rootMargin = '0px'
  readonly scrollMargin = '0px'
  readonly thresholds: ReadonlyArray<number>
  readonly elements = new Set<Element>()
  private readonly callback: IntersectionObserverCallback

  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    this.callback = callback
    const threshold = options?.threshold ?? 0
    this.thresholds = Array.isArray(threshold) ? threshold : [threshold]
    intersectionObservers.push(this)
  }

  observe(element: Element): void {
    this.elements.add(element)
  }

  unobserve(element: Element): void {
    this.elements.delete(element)
  }

  disconnect(): void {
    this.elements.clear()
  }

  takeRecords(): IntersectionObserverEntry[] {
    return []
  }

  /** Report the element as this share on screen (0..1). */
  report(element: Element, ratio: number): void {
    if (!this.elements.has(element)) return
    const height = 100
    const entry = {
      target: element,
      intersectionRatio: ratio,
      isIntersecting: ratio > 0,
      intersectionRect: { height: height * ratio } as DOMRectReadOnly,
      rootBounds: { height: 1000 } as DOMRectReadOnly,
      boundingClientRect: { height } as DOMRectReadOnly,
      time: performance.now(),
    } as IntersectionObserverEntry
    this.callback([entry], this)
  }
}

/** Put an element on screen (or take it off) for every observer watching it. */
export function setVisible(element: Element, ratio = 1): void {
  for (const observer of intersectionObservers) observer.report(element, ratio)
}

/** Every EventSource the app opened, newest last. */
export const eventSources: FakeEventSource[] = []

export class FakeEventSource extends EventTarget {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSED = 2
  readonly url: string
  readyState = FakeEventSource.OPEN
  onerror: ((event: Event) => void) | null = null

  constructor(url: string | URL) {
    super()
    this.url = String(url)
    eventSources.push(this)
  }

  /** Deliver a named server-sent event with a JSON payload. */
  emit(type: string, data: unknown): void {
    this.dispatchEvent(new MessageEvent(type, { data: JSON.stringify(data) }))
  }

  fail(): void {
    this.onerror?.(new Event('error'))
  }

  close(): void {
    this.readyState = FakeEventSource.CLOSED
  }
}

/** Install the fakes on jsdom's window. Called once from the setup file. */
export function installBrowserFakes(): void {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: matchMedia,
  })
  Object.defineProperty(globalThis, 'ResizeObserver', {
    configurable: true,
    writable: true,
    value: FakeResizeObserver,
  })
  Object.defineProperty(globalThis, 'IntersectionObserver', {
    configurable: true,
    writable: true,
    value: FakeIntersectionObserver,
  })
  Object.defineProperty(globalThis, 'EventSource', {
    configurable: true,
    writable: true,
    value: FakeEventSource,
  })
  // jsdom answers confirm() and prompt() with undefined, silently: a test would
  // take the "cancel" branch without knowing. A test that needs them says so:
  // vi.spyOn(window, 'confirm').mockReturnValue(true)
  window.confirm = () => {
    throw new Error("window.confirm was called: stub it, vi.spyOn(window, 'confirm')")
  }
  window.prompt = () => {
    throw new Error("window.prompt was called: stub it, vi.spyOn(window, 'prompt')")
  }
  // jsdom prints "Not implemented" for these; the app calls them on navigation.
  window.scrollTo = () => {}
  Element.prototype.scrollIntoView = function scrollIntoView() {}
  // React Aria's tab indicator (SharedElementTransition) and disclosures ask an
  // element for its running animations. Element.animate stays undefined on
  // purpose: motion would take it as Web Animations support and use it.
  Element.prototype.getAnimations = function getAnimations() {
    return []
  }
  // ProseMirror (the post editor) maps a click to a text position through
  // these; without layout there is no position, and it keeps the selection.
  document.elementFromPoint = () => null
  Range.prototype.getClientRects = function getClientRects() {
    return Object.assign([], { item: () => null }) as unknown as DOMRectList
  }
  Range.prototype.getBoundingClientRect = function getBoundingClientRect() {
    return new DOMRect()
  }
}

/**
 * Forget what the previous test set: media queries and event streams. The
 * observers stay: lib/impressions.ts makes one per module and keeps it.
 */
export function resetBrowserFakes(): void {
  queries.clear()
  mediaListeners.clear()
  eventSources.length = 0
}
