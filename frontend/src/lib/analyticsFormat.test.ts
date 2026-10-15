import { describe, expect, it } from 'vitest'
import { formatDay, formatPercent, formatPoints } from './analyticsFormat'

describe('formatPoints', () => {
  it('signs a change in percentage points, to a tenth', () => {
    expect(formatPoints(0.03)).toBe('+3 п. п.')
    expect(formatPoints(-0.0123)).toBe('−1,2 п. п.')
  })

  it('shows a change that rounds to nothing without a sign', () => {
    expect(formatPoints(0.0004)).toBe('0 п. п.')
    expect(formatPoints(-0.0004)).toBe('0 п. п.')
  })
})

describe('formatPercent', () => {
  it('keeps one decimal at most', () => {
    expect(formatPercent(0.15)).toBe('15\u00a0%')
    expect(formatPercent(0.03333)).toBe('3,3\u00a0%')
  })
})

describe('formatDay', () => {
  it('names the UTC day the server counted, whatever the reader’s clock', () => {
    // 23:30 UTC is already the next day in Moscow, where the tests run.
    expect(formatDay('2026-10-13T23:30:00Z')).toBe('13 окт.')
  })
})
