import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makeItem, makeReference, makeVulnerabilityItem } from '../../test/fixtures'
import { CveTimeline } from './CveTimeline'

/** The steps of the line as the reader reads them: date, then what happened. */
function steps() {
  return screen.getAllByRole('listitem').map((step) => step.textContent)
}

describe('CveTimeline', () => {
  it('draws a vulnerability’s life oldest first, with the news last', () => {
    render(<CveTimeline item={makeVulnerabilityItem({ published_at: '2026-10-13T08:00:00Z' })} />)

    expect(screen.getByText('CVE-2026-31842')).toBeInTheDocument()
    expect(steps()).toEqual([
      '08.10.2026Опубликована в NVD',
      '10.10.2026В каталоге CISA KEV',
      '11.10.2026Публичный эксплойт',
      '13.10.2026Новость в выпуске',
      '31.10.2026Срок CISA',
    ])
  })

  it('follows the best-dated of the entry’s vulnerabilities', () => {
    render(
      <CveTimeline
        item={makeItem({
          published_at: '2026-10-13T08:00:00Z',
          references: [
            makeReference({
              id: 'CVE-2026-1111',
              kev_added: null,
              kev_due: null,
              exploit_published: null,
            }),
            makeReference({ id: 'CVE-2026-2222', kev_due: null }),
          ],
        })}
      />,
    )
    expect(screen.getByText('CVE-2026-2222')).toBeInTheDocument()
    expect(steps()).toHaveLength(4)
  })

  it('draws one dated event and the news as a line of two', () => {
    render(
      <CveTimeline
        item={makeItem({
          published_at: '2026-10-13T23:30:00Z',
          references: [
            makeReference({
              nvd_published: '2018-01-03',
              kev_added: null,
              kev_due: null,
              exploit_published: null,
            }),
          ],
        })}
      />,
    )
    // Years matter: a flaw can be eight years old by the time it makes the news.
    expect(steps()).toEqual(['03.01.2018Опубликована в NVD', '13.10.2026Новость в выпуске'])
  })

  it('draws nothing for an entry the bases do not date', () => {
    const { container, rerender } = render(<CveTimeline item={makeItem({ references: [] })} />)
    expect(container).toBeEmptyDOMElement()

    rerender(
      <CveTimeline
        item={makeItem({
          references: [
            makeReference({
              nvd_published: null,
              kev_added: null,
              kev_due: null,
              exploit_published: null,
            }),
          ],
        })}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
