import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { makeItem, makeVulnerability, makeVulnerabilityItem } from '../../test/fixtures'
import { RiskMatrix } from './RiskMatrix'

const HINT = /Номер в клетке - запись выпуска/

const entries = [
  { position: 1, item: makeVulnerabilityItem({ ours: ['SIMATIC'] }) },
  { position: 2, item: makeItem({ headline: 'Новости рынка', kind: 'news' }) },
  {
    position: 3,
    item: makeItem({
      headline: 'XSS в портале поддержки',
      kind: 'vulnerability',
      score: 0.5,
      vulnerability: makeVulnerability({ cvss_score: '5.4', exploit: 'none' }),
    }),
  },
]

describe('RiskMatrix', () => {
  it('shows nothing for an issue without vulnerabilities', () => {
    const { container } = render(<RiskMatrix entries={[entries[1]]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('places only the vulnerabilities, each by its number', () => {
    render(<RiskMatrix entries={entries} />)
    expect(screen.getByRole('heading', { name: 'Матрица риска' })).toBeInTheDocument()
    expect(screen.getByText(/^2 уязвимости/)).toBeInTheDocument()
    expect(
      screen
        .getAllByRole('button', { name: /^Открыть запись/ })
        .map((button) => button.textContent),
    ).toEqual(['1', '3'])
    expect(screen.queryByRole('button', { name: /Новости рынка/ })).toBeNull()
  })

  it('names the entry under the pointer or the focus below the grid', async () => {
    const user = userEvent.setup()
    render(<RiskMatrix entries={entries} />)
    expect(screen.getByText(HINT)).toBeInTheDocument()

    await user.hover(
      screen.getByRole('button', { name: 'Открыть запись 3: XSS в портале поддержки' }),
    )
    expect(await screen.findByText('XSS в портале поддержки')).toBeInTheDocument()
    expect(screen.queryByText(HINT)).toBeNull()

    await user.unhover(
      screen.getByRole('button', { name: 'Открыть запись 3: XSS в портале поддержки' }),
    )
    expect(await screen.findByText(HINT)).toBeInTheDocument()

    await user.tab()
    expect(
      await screen.findByText('Уязвимость SIMATIC S7-1500 используется в атаках'),
    ).toBeInTheDocument()
  })

  it('scrolls to the entry whose number is pressed', async () => {
    const user = userEvent.setup()
    const entry = document.createElement('article')
    entry.id = 'entry-3'
    // jsdom has no scrolling or Web Animations: the jump is observed on the entry.
    const scrollIntoView = vi.fn()
    Object.assign(entry, { scrollIntoView, animate: vi.fn() })
    document.body.append(entry)
    render(<RiskMatrix entries={entries} />)

    await user.click(
      screen.getByRole('button', { name: 'Открыть запись 3: XSS в портале поддержки' }),
    )

    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' })
    entry.remove()
  })
})
