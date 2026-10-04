/**
 * Whether a block is open, kept per browser: a reader who folds a block finds
 * it folded on the next visit. Storage may be missing or refuse (a private
 * window, blocked site data); then the block opens as it would by default and
 * a fold lasts for the visit only.
 */
const PREFIX = 'radar-open:'

type Store = Pick<Storage, 'getItem' | 'setItem'>

function browserStore(): Store | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export function readOpen(
  key: string,
  fallback: boolean,
  store: Store | null = browserStore(),
): boolean {
  try {
    const value = store?.getItem(PREFIX + key)
    if (value === '1') return true
    if (value === '0') return false
    return fallback
  } catch {
    return fallback
  }
}

export function writeOpen(key: string, isOpen: boolean, store: Store | null = browserStore()) {
  try {
    store?.setItem(PREFIX + key, isOpen ? '1' : '0')
  } catch {
    // Not kept: the block stays as it is until the page is left.
  }
}
