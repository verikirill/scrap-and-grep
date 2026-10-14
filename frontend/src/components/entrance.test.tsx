import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { EntranceContext, newEntrance, useEntranceDelay } from './entrance'

function Delay({ name }: { name: string }) {
  const delay = useEntranceDelay()
  return <p>{`${name}: ${delay === null ? 'none' : delay.toFixed(2)}`}</p>
}

describe('useEntranceDelay', () => {
  afterEach(() => vi.restoreAllMocks())

  it('gives no rise outside a page, as in a dialog', () => {
    render(<Delay name="dialog" />)
    expect(screen.getByText('dialog: none')).toBeInTheDocument()
  })

  it('lines cards up on a fresh page, one step apart, up to eight steps', () => {
    const entrance = newEntrance()
    const names = Array.from({ length: 10 }, (_, index) => `card ${index}`)
    render(
      <EntranceContext value={entrance}>
        {names.map((name) => (
          <Delay key={name} name={name} />
        ))}
      </EntranceContext>,
    )
    expect(screen.getByText('card 0: 0.00')).toBeInTheDocument()
    expect(screen.getByText('card 1: 0.06')).toBeInTheDocument()
    expect(screen.getByText('card 2: 0.12')).toBeInTheDocument()
    expect(screen.getByText('card 8: 0.48')).toBeInTheDocument()
    expect(screen.getByText('card 9: 0.48')).toBeInTheDocument()
  })

  it('lets a card that came later with its data rise at once', () => {
    const now = vi.spyOn(performance, 'now').mockReturnValue(1000)
    const entrance = newEntrance()
    const { rerender } = render(
      <EntranceContext value={entrance}>
        <Delay name="first" />
      </EntranceContext>,
    )
    now.mockReturnValue(1801)
    rerender(
      <EntranceContext value={entrance}>
        <Delay name="first" />
        <Delay name="late" />
      </EntranceContext>,
    )
    expect(screen.getByText('first: 0.00')).toBeInTheDocument()
    expect(screen.getByText('late: 0.00')).toBeInTheDocument()
  })
})
