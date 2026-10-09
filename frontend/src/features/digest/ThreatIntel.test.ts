import { describe, expect, it } from 'vitest'
import { indicatorKind } from './ThreatIntel'

describe('indicatorKind', () => {
  it('reads the kind through the defanged form an article prints', () => {
    expect(indicatorKind('185.12.44[.]7')).toBe('IP')
    expect(indicatorKind('hxxps://evil[.]example/drop')).toBe('URL')
    expect(indicatorKind('evil[.]example')).toBe('Домен')
    expect(indicatorKind('a'.repeat(64))).toBe('SHA-256')
    expect(indicatorKind('B'.repeat(40))).toBe('SHA-1')
    expect(indicatorKind('c'.repeat(32))).toBe('MD5')
  })
})
