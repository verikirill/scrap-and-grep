import { describe, expect, it } from 'vitest'
import type { DigestItem, VulnerabilityReference } from './api'
import { cvssOf, exposureBand, riskCells, severityBand, timelineOf } from './risk'

const reference = (extra: Partial<VulnerabilityReference> = {}): VulnerabilityReference => ({
  id: 'CVE-2026-1001',
  kev_added: null,
  kev_due: null,
  kev_ransomware: false,
  bdu_id: '',
  bdu_cvss: '',
  bdu_in_attacks: false,
  nvd_cvss: '',
  nvd_exploitation: '',
  epss: null,
  exploits: [],
  ...extra,
})

const entry = (extra: Partial<DigestItem> = {}): DigestItem =>
  ({
    kind: 'vulnerability',
    score: 0.6,
    published_at: '2026-10-05T09:00:00Z',
    ours: [],
    references: [],
    vulnerability: { ids: ['CVE-2026-1001'], name: '', cvss_score: '', exploit: 'unknown' },
    ...extra,
  }) as DigestItem

describe('the risk matrix', () => {
  it('takes the highest score the card and the bases give, in either decimal mark', () => {
    const item = entry({
      vulnerability: { ids: [], name: '', cvss_score: '7,5', exploit: 'unknown' },
      references: [reference({ nvd_cvss: '9.8' })],
    })
    expect(cvssOf(item)).toBe(9.8)
  })

  it('makes an exploited flaw critical whatever its score', () => {
    expect(severityBand(entry({ references: [reference({ kev_added: '2026-10-01' })] }))).toBe(2)
    expect(severityBand(entry({ references: [reference({ nvd_cvss: '7.2' })] }))).toBe(1)
    expect(severityBand(entry())).toBe(0)
  })

  it('puts the reader’s own systems on the top row', () => {
    expect(exposureBand(entry({ ours: ['Siemens S7-1500'], score: 0.4 }))).toBe(2)
    expect(exposureBand(entry({ score: 0.9 }))).toBe(1)
    expect(exposureBand(entry({ score: 0.5 }))).toBe(0)
  })

  it('places only vulnerabilities, each in one cell', () => {
    const cells = riskCells([
      {
        position: 1,
        item: entry({ ours: ['Siemens'], references: [reference({ nvd_cvss: '9.8' })] }),
      },
      { position: 2, item: entry({ kind: 'attack' }) },
    ])
    expect(cells[2][2].map((placed) => placed.position)).toEqual([1])
    expect(cells.flat(2)).toHaveLength(1)
  })
})

describe('the timeline', () => {
  it('orders the dated events, an exploit before NVD included', () => {
    const item = entry({
      references: [
        reference({
          nvd_published: '2018-07-19',
          exploit_published: '2018-04-30',
          kev_added: '2021-11-03',
          kev_due: '2022-05-03',
        }),
      ],
    })
    expect(timelineOf(item).map((event) => event.date)).toEqual([
      '2018-04-30',
      '2018-07-19',
      '2021-11-03',
      '2022-05-03',
      '2026-10-05',
    ])
  })

  it('draws nothing from the news date alone', () => {
    expect(timelineOf(entry({ references: [reference()] }))).toEqual([])
  })
})
