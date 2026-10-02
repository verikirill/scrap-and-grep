import { describe, expect, it } from 'vitest'
import { initials } from './sourceLook'

describe('initials', () => {
  it('takes the first letters of the first two words, punctuation aside', () => {
    expect(initials('Хабр: информационная безопасность')).toBe('ХИ')
    expect(initials('@true_secator')).toBe('TS')
    expect(initials('Хакер')).toBe('Х')
  })

  it('draws a question mark for a name without letters', () => {
    expect(initials('...')).toBe('?')
  })
})
