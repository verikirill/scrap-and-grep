import { describe, expect, it } from 'vitest'
import { formatDuration } from './format'

describe('formatDuration', () => {
  it('shows a video length as a player does', () => {
    expect(formatDuration(42_300)).toBe('0:42')
    expect(formatDuration(75_000)).toBe('1:15')
  })

  it('rounds up into the next minute instead of showing sixty seconds', () => {
    expect(formatDuration(59_600)).toBe('1:00')
  })
})
