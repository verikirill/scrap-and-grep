import { describe, expect, it } from 'vitest'
import { durationWords, formatDuration, formatPostTime, inSentence, pause } from './format'

describe('formatPostTime', () => {
  // 00:30 on 2 October in Moscow, still 1 October in UTC.
  const now = new Date('2026-10-01T21:30:00Z')

  it('shows only the time for a post of today in Moscow', () => {
    expect(formatPostTime('2026-10-01T21:05:00Z', now)).toBe('00:05')
  })

  it('calls the Moscow day before yesterday even when UTC says today', () => {
    expect(formatPostTime('2026-10-01T20:00:00Z', now)).toBe('вчера, 23:00')
  })

  it('gives the date for anything older', () => {
    expect(formatPostTime('2026-09-29T08:15:00Z', now)).toBe('29 сент., 11:15')
  })
})

describe('formatDuration', () => {
  it('shows a video length as a player does', () => {
    expect(formatDuration(42_300)).toBe('0:42')
    expect(formatDuration(75_000)).toBe('1:15')
  })

  it('rounds up into the next minute instead of showing sixty seconds', () => {
    expect(formatDuration(59_600)).toBe('1:00')
  })
})

describe('inSentence', () => {
  it('lowers a field name but keeps an abbreviation', () => {
    expect(inSentence('Дата атаки')).toBe('дата атаки')
    expect(inSentence('Техники ATT&CK')).toBe('техники ATT&CK')
    expect(inSentence('CVSS')).toBe('CVSS')
    expect(inSentence('CWE')).toBe('CWE')
    expect(inSentence('')).toBe('')
  })
})

describe('pause', () => {
  it('names a pause in hours, then in days', () => {
    expect(pause(0.4)).toBe('меньше часа')
    expect(pause(6.2)).toBe('6 ч')
    expect(pause(47)).toBe('47 ч')
    expect(pause(72)).toBe('3 дн.')
  })
})

describe('durationWords', () => {
  it('reads minutes under an hour and a half, hours above, whole hours past ten', () => {
    expect([52, 91, 120, 600].map(durationWords)).toEqual(['52 мин', '1,5 ч', '2 ч', '10 ч'])
  })
})
