import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { makeAttack } from '../../test/fixtures'
import { IndicatorsBlock, SocExport } from './ThreatIntel'

describe('IndicatorsBlock', () => {
  it('stays away from an entry with neither indicators nor techniques', () => {
    const { container, rerender } = render(<IndicatorsBlock attack={null} />)
    expect(container).toBeEmptyDOMElement()

    rerender(<IndicatorsBlock attack={makeAttack({ indicators: [], techniques: [] })} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('leaves out the indicators or the techniques the reader’s profile hides', () => {
    const attack = makeAttack()
    const { container, rerender } = render(
      <IndicatorsBlock attack={attack} hidden={['attack.indicators']} />,
    )
    expect(screen.getByRole('button', { name: /^2 техники ATT&CK$/ })).toBeInTheDocument()

    rerender(<IndicatorsBlock attack={attack} hidden={['attack.techniques']} />)
    expect(screen.getByRole('button', { name: /^3 индикатора компрометации$/ })).toBeInTheDocument()

    rerender(
      <IndicatorsBlock attack={attack} hidden={['attack.indicators', 'attack.techniques']} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('counts what it holds in its head and lists the indicators by kind once opened', async () => {
    const user = userEvent.setup()
    const attack = makeAttack()
    render(<IndicatorsBlock attack={attack} />)
    const head = screen.getByRole('button', {
      name: /^3 индикатора компрометации\s*·\s*2 техники ATT&CK$/,
    })
    expect(head).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('185.244.25[.]17')).toBeNull()

    await user.click(head)

    expect(head).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Значения обезврежены: [.] вместо точки')).toBeInTheDocument()
    const rows = within(screen.getByRole('list')).getAllByRole('listitem')
    // The kind, then the value as the article printed it: still defanged.
    expect(rows.map((row) => row.textContent)).toEqual([
      'IP185.244.25[.]17',
      'Доменminenergo-docs[.]ru',
      `SHA-256${attack.indicators[2]}`,
    ])

    await user.click(head)
    await waitFor(() => expect(screen.queryByText('185.244.25[.]17')).toBeNull())
  })

  it('copies one indicator or all of them, one per line', async () => {
    const user = userEvent.setup()
    const attack = makeAttack()
    render(<IndicatorsBlock attack={attack} />)
    await user.click(screen.getByRole('button', { name: /индикатора компрометации/ }))

    await user.click(screen.getByRole('button', { name: 'Скопировать minenergo-docs[.]ru' }))
    expect(await navigator.clipboard.readText()).toBe('minenergo-docs[.]ru')

    await user.click(screen.getByRole('button', { name: 'Скопировать все индикаторы' }))
    expect(await navigator.clipboard.readText()).toBe(
      ['185.244.25[.]17', 'minenergo-docs[.]ru', attack.indicators[2]].join('\n'),
    )
  })

  it('leaves the value on screen to select when the browser refuses the clipboard', async () => {
    const user = userEvent.setup()
    render(<IndicatorsBlock attack={makeAttack()} />)
    await user.click(screen.getByRole('button', { name: /индикатора компрометации/ }))
    const writeText = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockRejectedValue(new DOMException('Write permission denied.', 'NotAllowedError'))

    await user.click(screen.getByRole('button', { name: 'Скопировать 185.244.25[.]17' }))

    await waitFor(() => expect(writeText).toHaveBeenCalledWith('185.244.25[.]17'))
    expect(screen.getByText('185.244.25[.]17')).toBeInTheDocument()
  })

  it('links each technique to its page in MITRE ATT&CK, a sub-technique included', async () => {
    const user = userEvent.setup()
    render(
      <IndicatorsBlock
        attack={makeAttack({
          indicators: [],
          techniques: [
            { id: 'T1566.001', name: 'Spearphishing Attachment' },
            { id: 'T1059', name: '' },
          ],
        })}
      />,
    )
    // No indicators: the head counts the techniques alone.
    await user.click(screen.getByRole('button', { name: '2 техники ATT&CK' }))

    expect(screen.queryByText('Значения обезврежены: [.] вместо точки')).toBeNull()
    const named = screen.getByRole('link', { name: /^T1566\.001\s*Spearphishing Attachment$/ })
    expect(named).toHaveAttribute('href', 'https://attack.mitre.org/techniques/T1566/001/')
    expect(named).toHaveAttribute('target', '_blank')
    expect(named).toHaveAttribute('rel', expect.stringContaining('noopener'))
    // A technique the article gave without a name is named by its id.
    const bare = screen.getByRole('link', { name: 'T1059' })
    expect(bare).toHaveAttribute('href', 'https://attack.mitre.org/techniques/T1059/')
    expect(bare).toHaveAttribute('title', 'T1059')
  })

  it('names a single indicator and technique in the singular', () => {
    render(
      <IndicatorsBlock
        attack={makeAttack({
          indicators: ['185.244.25[.]17'],
          techniques: [{ id: 'T1133', name: 'External Remote Services' }],
        })}
      />,
    )
    expect(
      screen.getByRole('button', {
        name: /^1 индикатор компрометации\s*·\s*1 техника ATT&CK$/,
      }),
    ).toBeInTheDocument()
  })
})

describe('SocExport', () => {
  // A download link would make jsdom navigate, which it cannot do.
  const keepPage = (event: MouseEvent) => {
    if ((event.target as Element).closest('a[download]')) event.preventDefault()
  }
  beforeEach(() => document.addEventListener('click', keepPage, true))
  afterEach(() => document.removeEventListener('click', keepPage, true))

  it('offers the issue for a SOC in three formats and closes on a choice', async () => {
    const user = userEvent.setup()
    render(<SocExport digestId="digest-7" />)

    await user.click(screen.getByRole('button', { name: 'Для SOC' }))
    const popover = await screen.findByRole('dialog')
    const formats = within(popover).getAllByRole('link')
    expect(formats.map((link) => link.getAttribute('href'))).toEqual([
      '/api/v1/digests/digest-7/export.stix.json',
      '/api/v1/digests/digest-7/export.misp.json',
      '/api/v1/digests/digest-7/export.csv',
    ])
    for (const link of formats) expect(link).toHaveAttribute('download')
    expect(formats[0]).toHaveAccessibleName(/^STIX 2\.1/)
    expect(formats[1]).toHaveAccessibleName(/^MISP/)
    expect(formats[2]).toHaveAccessibleName(/^CSV/)

    await user.click(formats[1])

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })
})
