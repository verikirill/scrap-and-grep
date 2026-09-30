import { describe, expect, it } from 'vitest'
import type { PreviewItem } from './api'
import { diffPreview } from './diff'
import { plural } from './format'

function item(id: number, score: number, selected = true): PreviewItem {
  return {
    article_id: id,
    url: `https://example.org/${id}`,
    title: `Публикация ${id}`,
    source_name: 'Источник',
    published_at: '2026-09-29T10:00:00Z',
    score,
    interest_id: 'ics',
    interest_title: 'АСУ ТП',
    lexical_hit: true,
    selected,
    reject_reason: selected ? null : 'low_score',
  }
}

describe('diffPreview', () => {
  it('marks new, moved and dropped articles against the saved profile', () => {
    const saved = [item(1, 0.9), item(2, 0.6), item(3, 0.7), item(4, 0.3, false)]
    const draft = [item(1, 0.9), item(2, 0.8), item(4, 0.75), item(3, 0.4, false)]

    const { rows, dropped } = diffPreview(saved, draft)

    expect(rows.map((row) => [row.article_id, row.movement])).toEqual([
      [1, 'same'],
      [2, 'up'],
      [4, 'new'],
    ])
    expect(rows[1].delta).toBeCloseTo(0.2)
    expect(dropped.map((entry) => entry.article_id)).toEqual([3])
  })

  it('shows the draft without marks while the saved preview is loading', () => {
    const { rows, dropped } = diffPreview(null, [item(1, 0.9), item(2, 0.2, false)])

    expect(rows.map((row) => row.movement)).toEqual(['same'])
    expect(dropped).toEqual([])
  })
})

describe('plural', () => {
  it('picks the Russian plural form, including the 11-14 exception', () => {
    const forms: [string, string, string] = ['статья', 'статьи', 'статей']

    expect([1, 2, 5, 11, 12, 21, 22, 25, 111].map((n) => plural(n, forms))).toEqual([
      'статья',
      'статьи',
      'статей',
      'статей',
      'статей',
      'статья',
      'статьи',
      'статей',
      'статей',
    ])
  })
})
