import { describe, expect, it } from 'vitest'

import { readOpen, writeOpen } from './remembered'

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

describe('a folded block is remembered', () => {
  it('opens by its default until the reader folds it, then stays folded', () => {
    const store = memoryStore()
    expect(readOpen('source-health', true, store)).toBe(true)
    writeOpen('source-health', false, store)
    expect(readOpen('source-health', true, store)).toBe(false)
    writeOpen('source-health', true, store)
    expect(readOpen('source-health', false, store)).toBe(true)
  })

  it('keeps each block apart', () => {
    const store = memoryStore()
    writeOpen('digest-plan', false, store)
    expect(readOpen('digest-numbers', true, store)).toBe(true)
  })

  it('falls back to the default when storage is missing or refuses', () => {
    expect(readOpen('taste', true, null)).toBe(true)
    expect(readOpen('taste', false, refusing)).toBe(false)
    expect(() => writeOpen('taste', false, refusing)).not.toThrow()
  })
})
