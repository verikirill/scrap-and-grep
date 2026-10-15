import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  makeAttack,
  makeAttackItem,
  makeItem,
  makeReference,
  makeVulnerabilityItem,
} from '../../test/fixtures'
import { EntryDetails, PriorityChip, VerifiedBadge } from './EntryCard'

/** The card's filled fields as the reader reads them: name, then value. */
function cardFields() {
  const terms = screen.queryAllByRole('term').map((term) => term.textContent)
  const values = screen.queryAllByRole('definition').map((value) => value.textContent)
  return terms.map((term, index) => [term, values[index]])
}

describe('VerifiedBadge', () => {
  it('stamps an entry checked against CISA KEV and the BDU, naming the bases on hover', () => {
    render(<VerifiedBadge item={makeVulnerabilityItem()} />)
    expect(screen.getByTitle('Идентификаторы сверены с CISA KEV и БДУ ФСТЭК')).toHaveTextContent(
      'Сверено',
    )
  })

  it('names only the base the ids were found in', () => {
    render(
      <VerifiedBadge
        item={makeVulnerabilityItem({ references: [makeReference({ kev_added: null })] })}
      />,
    )
    expect(screen.getByTitle('Идентификаторы сверены с БДУ ФСТЭК')).toBeInTheDocument()
  })

  it('stays away from an entry the bases know nothing of', () => {
    const { container, rerender } = render(<VerifiedBadge item={makeItem({ references: [] })} />)
    expect(container).toBeEmptyDOMElement()
    rerender(
      <VerifiedBadge
        item={makeItem({ references: [makeReference({ kev_added: null, bdu_id: '' })] })}
      />,
    )
    expect(screen.queryByText('Сверено')).toBeNull()
  })
})

describe('PriorityChip', () => {
  it('names the dataset’s priority and gives its reason on hover', () => {
    const { rerender } = render(
      <PriorityChip
        item={makeItem({ priority: 'high', priority_reason: 'эксплойт: используется в атаках' })}
      />,
    )
    expect(screen.getByTitle('эксплойт: используется в атаках')).toHaveTextContent(
      'Высокий приоритет',
    )

    rerender(<PriorityChip item={makeItem({ priority: 'medium' })} />)
    expect(screen.getByText('Средний приоритет')).toBeInTheDocument()

    rerender(<PriorityChip item={makeItem({ priority: 'low' })} />)
    expect(screen.getByText('Низкий приоритет')).toBeInTheDocument()
  })

  it('shows nothing for an entry the dataset gives no priority', () => {
    const { container } = render(<PriorityChip item={makeItem({ priority: null })} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('EntryDetails', () => {
  it('lists the fields the article fills and names the silent ones in one line', () => {
    render(
      <EntryDetails
        item={makeVulnerabilityItem({
          fields: [
            {
              key: 'vulnerability.name',
              label: 'Уязвимость',
              value: 'Обход аутентификации в веб-сервере SIMATIC S7-1500',
            },
            { key: 'vulnerability.fix', label: 'Обновление', value: 'нет данных' },
            { key: 'vulnerability.cvss', label: 'CVSS', value: 'нет данных' },
            { key: 'vulnerability.cwe', label: 'CWE', value: 'CWE-287' },
          ],
        })}
      />,
    )

    expect(cardFields()).toEqual([
      ['Уязвимость', 'Обход аутентификации в веб-сервере SIMATIC S7-1500'],
      ['CWE', 'CWE-287'],
    ])
    // Inside a sentence a field name is lowered, an abbreviation is not.
    expect(screen.getByText('Нет в тексте: обновление, CVSS')).toBeInTheDocument()
  })

  it('leaves out the rows the reader’s profile hides, filled or silent', () => {
    render(
      <EntryDetails
        item={makeVulnerabilityItem({
          hidden_fields: ['vulnerability.cvss', 'vulnerability.cvss_words', 'vulnerability.fix'],
        })}
      />,
    )

    const labels = cardFields().map(([label]) => label)
    expect(labels).not.toContain('CVSS')
    expect(labels).not.toContain('Доступ')
    expect(labels).not.toContain('Действия пользователя')
    expect(labels).not.toContain('Обновление')
    expect(labels.slice(0, 3)).toEqual(['Уязвимость', 'Затронуто', 'Временные меры'])
  })

  it('leaves the indicators and techniques to their own block, and only those it shows', () => {
    const { rerender } = render(<EntryDetails item={makeAttackItem()} />)
    const labels = () => cardFields().map(([label]) => label)
    expect(labels()).not.toContain('Индикаторы компрометации')
    expect(labels()).not.toContain('Техники ATT&CK')
    expect(labels()).toContain('Вектор атаки')

    // Without techniques in the data the block has none: the card keeps the field.
    rerender(<EntryDetails item={makeAttackItem({ attack: makeAttack({ techniques: [] }) })} />)
    expect(labels()).not.toContain('Индикаторы компрометации')
    expect(labels()).toContain('Техники ATT&CK')

    rerender(<EntryDetails item={makeAttackItem({ attack: null })} />)
    expect(labels()).toContain('Индикаторы компрометации')
    expect(
      screen.getByText('Нет в тексте: группировка, инструменты, уязвимости'),
    ).toBeInTheDocument()
  })

  it('shows no card for a news entry, which has no fields', () => {
    const { container } = render(<EntryDetails item={makeItem({ kind: 'news', fields: [] })} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows management tags as chips', () => {
    render(<EntryDetails item={makeItem({ tag_labels: ['Энергетика', 'Регуляторы'] })} />)
    expect(screen.getByText('Энергетика')).toBeInTheDocument()
    expect(screen.getByText('Регуляторы')).toBeInTheDocument()
  })

  it('prints the links of a channel post defanged and not as links', () => {
    render(
      <EntryDetails
        item={makeItem({
          links: [
            'https://github.com/acme/s7-poc',
            'https://evil.example:8443/drop.bin',
            'см. в канале',
          ],
        })}
      />,
    )
    const cited = screen.getByText('Ссылки из поста:')
    expect(
      within(cited)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual([
      'https://github[.]com/acme/s7-poc',
      'https://evil[.]example:8443/drop.bin',
      'см. в канале',
    ])
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('names what the check against the article’s text took out', () => {
    render(<EntryDetails item={makeItem({ unsupported: ['CVSS 9.8', 'Версия 3.1.5'] })} />)
    expect(
      screen.getByText('Нет в тексте статьи, убрано проверкой: CVSS 9.8, версия 3.1.5'),
    ).toBeInTheDocument()
  })
})
