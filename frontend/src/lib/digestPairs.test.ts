import { describe, expect, it } from 'vitest'
import { sameKind } from './digestPairs'

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
