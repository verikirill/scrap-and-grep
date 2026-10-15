import { describe, expect, it } from 'vitest'
import { CARD_FIELD_GROUPS, withHidden } from './cardFields'

describe('withHidden', () => {
  it('keeps the hidden rows in the order of the card, whatever order they were hidden in', () => {
    const first = withHidden([], 'vulnerability.cwe', true)
    const second = withHidden(first, 'attack.group', true)

    expect(withHidden(second, 'vulnerability.fix', true)).toEqual([
      'attack.group',
      'vulnerability.fix',
      'vulnerability.cwe',
    ])
  })

  it('shows a row again and hides a row once however often it is hidden', () => {
    expect(withHidden(['attack.group'], 'attack.group', true)).toEqual(['attack.group'])
    expect(withHidden(['attack.group', 'attack.tools'], 'attack.group', false)).toEqual([
      'attack.tools',
    ])
  })

  it('drops a key no card has, as one saved by an older page', () => {
    const stale = ['attack.colour'] as unknown as Parameters<typeof withHidden>[0]
    expect(withHidden(stale, 'attack.date', true)).toEqual(['attack.date'])
  })
})

describe('CARD_FIELD_GROUPS', () => {
  it('names every row once within its kind', () => {
    for (const group of CARD_FIELD_GROUPS) {
      const keys = group.fields.map((field) => field.key)
      expect(new Set(keys).size).toBe(keys.length)
      expect(keys.every((key) => key.startsWith(`${group.kind}.`))).toBe(true)
    }
  })
})
