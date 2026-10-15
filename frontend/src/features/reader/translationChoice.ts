/**
 * Whether the reader last chose the original of a foreign article over its
 * translation, kept per browser: the next English article opens the same way.
 * Storage may be missing or refuse (a private window, blocked site data);
 * then the translation is shown, and a choice lasts until the page is left.
 */
const KEY = 'radar-reader-original'

type Store = Pick<Storage, 'getItem' | 'setItem'>

function browserStore(): Store | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export function readPrefersOriginal(store: Store | null = browserStore()): boolean {
  try {
    return store?.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export function writePrefersOriginal(
  prefersOriginal: boolean,
  store: Store | null = browserStore(),
) {
  try {
    store?.setItem(KEY, prefersOriginal ? '1' : '0')
  } catch {
    // Not kept: the choice holds for this article only.
  }
}
