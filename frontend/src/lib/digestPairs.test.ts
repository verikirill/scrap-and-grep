import { describe, expect, it } from 'vitest'
import { sameKind, twinOf } from './digestPairs'

const specialist = { id: 'a', profile_id: 'p', audience: 'specialist' as const }

describe('sameKind', () => {
  it('pairs issues of one profile for one audience', () => {
    expect(sameKind(specialist, { ...specialist, id: 'b' })).toBe(true)
  })

  it('keeps the management twin of a build for both audiences apart', () => {
    expect(sameKind(specialist, { ...specialist, id: 'b', audience: 'management' })).toBe(false)
  })

  it('takes an issue without an audience for a specialist one', () => {
    expect(sameKind(specialist, { id: 'b', profile_id: 'p' })).toBe(true)
  })

  it('never pairs an issue with itself or with another profile', () => {
    expect(sameKind(specialist, specialist)).toBe(false)
    expect(sameKind(specialist, { ...specialist, id: 'b', profile_id: 'q' })).toBe(false)
  })
})

describe('twinOf', () => {
  const issue = {
    id: 'a',
    profile_id: 'p',
    audience: 'specialist' as const,
    period_start: '2026-10-02T00:00:00Z',
    period_end: '2026-10-09T00:00:00Z',
    status: 'done' as const,
  }

  it('finds the management issue of the same build', () => {
    const twin = { ...issue, id: 'b', audience: 'management' as const }
    expect(twinOf(issue, [issue, twin])).toBe(twin)
  })

  it('ignores the same audience, another period and an unfinished build', () => {
    const others = [
      { ...issue, id: 'b' },
      { ...issue, id: 'c', audience: 'management' as const, period_start: '2026-10-03T00:00:00Z' },
      { ...issue, id: 'd', audience: 'management' as const, status: 'running' as const },
    ]
    expect(twinOf(issue, [issue, ...others])).toBeNull()
  })
})
