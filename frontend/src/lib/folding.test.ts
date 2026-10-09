import { describe, expect, it } from 'vitest'
import type { DigestItem } from './api'
import { firstEntries, foldSummary, withFolded } from './folding'

describe('folded sections', () => {
  it('folds a title once and unfolds it without touching the rest', () => {
    expect(withFolded(['Атаки'], 'Уязвимости', true)).toEqual(['Атаки', 'Уязвимости'])
    expect(withFolded(['Атаки', 'Уязвимости'], 'Атаки', true)).toEqual(['Уязвимости', 'Атаки'])
    expect(withFolded(['Атаки', 'Уязвимости'], 'Атаки', false)).toEqual(['Уязвимости'])
  })

  it('keeps the urgent and the reader’s own visible on a folded section', () => {
    const items = [
      { priority: 'high', ours: ['Siemens'] },
      { priority: 'low', ours: [] },
      { priority: 'high' },
    ] as DigestItem[]
    expect(foldSummary(items)).toEqual({ high: 2, ours: 1 })
  })

  it('shows a long section in part and a short one whole', () => {
    expect(firstEntries([1, 2, 3, 4, 5, 6, 7], false)).toHaveLength(7)
    expect(firstEntries([1, 2, 3, 4, 5, 6, 7, 8], false)).toEqual([1, 2, 3, 4, 5])
    expect(firstEntries([1, 2, 3, 4, 5, 6, 7, 8], true)).toHaveLength(8)
  })
})
