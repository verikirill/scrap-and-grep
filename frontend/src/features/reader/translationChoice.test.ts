import { describe, expect, it } from 'vitest'

import { readPrefersOriginal, writePrefersOriginal } from './translationChoice'

function memoryStore() {
  const values = new Map<string, string>()
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => void values.set(key, value),
  }
}

const refusing = {
  getItem: (): string | null => {
    throw new DOMException('denied', 'SecurityError')
  },
  setItem: () => {
    throw new DOMException('full', 'QuotaExceededError')
  },
}

describe('the reader’s choice of the original over the translation', () => {
  it('starts with the translation and keeps the last choice', () => {
    const store = memoryStore()
    expect(readPrefersOriginal(store)).toBe(false)
    writePrefersOriginal(true, store)
    expect(readPrefersOriginal(store)).toBe(true)
    writePrefersOriginal(false, store)
    expect(readPrefersOriginal(store)).toBe(false)
  })

  it('shows the translation when storage is missing or refuses, and does not throw', () => {
    expect(readPrefersOriginal(null)).toBe(false)
    expect(readPrefersOriginal(refusing)).toBe(false)
    expect(() => writePrefersOriginal(true, refusing)).not.toThrow()
    expect(() => writePrefersOriginal(true, null)).not.toThrow()
  })
})
