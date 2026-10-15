import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useRef, useState } from 'react'
import { describe, expect, it } from 'vitest'
import { SlidingPill } from './SlidingPill'

function Row({ initial }: { initial: string | null }) {
  const row = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(initial)
  return (
    <div ref={row} data-testid="row">
      {['Все', 'Каналы'].map((name) => (
        <button
          key={name}
          type="button"
          data-active={active === name}
          onClick={() => setActive(name)}
        >
          {name}
        </button>
      ))}
      <SlidingPill container={row} activeKey={active} />
    </div>
  )
}

// The pill is a decoration: hidden from a screen reader, the only such span in the row.
const pill = () => screen.getByTestId('row').querySelector('span[aria-hidden]')

describe('SlidingPill', () => {
  it('draws no highlight while nothing in its row is chosen', () => {
    render(<Row initial={null} />)
    expect(pill()).toBeNull()
  })

  it('highlights the chosen item, and appears with the first choice', async () => {
    const user = userEvent.setup()
    render(<Row initial={null} />)

    await user.click(screen.getByRole('button', { name: 'Каналы' }))

    expect(pill()).not.toBeNull()
  })
})
