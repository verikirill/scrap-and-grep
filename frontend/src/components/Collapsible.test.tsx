import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Collapsible } from './Collapsible'

function Block({ defaultOpen }: { defaultOpen?: boolean }) {
  return (
    <Collapsible
      storageKey="health"
      title="Здоровье источников"
      head={<h2>Источники за сутки</h2>}
      defaultOpen={defaultOpen}
    >
      <p>Три источника молчат</p>
    </Collapsible>
  )
}

describe('Collapsible', () => {
  it('folds its body under the head and names the action for a screen reader', async () => {
    const user = userEvent.setup()
    render(<Block />)
    const button = screen.getByRole('button', { name: 'Свернуть: Здоровье источников' })
    expect(button).toHaveAttribute('aria-expanded', 'true')
    const body = document.getElementById(button.getAttribute('aria-controls') ?? '')
    expect(body).toHaveTextContent('Три источника молчат')

    await user.click(button)

    expect(screen.getByRole('heading', { name: 'Источники за сутки' })).toBeInTheDocument()
    expect(screen.queryByText('Три источника молчат')).toBeNull()
    expect(screen.getByRole('button', { name: 'Развернуть: Здоровье источников' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })

  it('stays as the reader left it on the next visit', async () => {
    const user = userEvent.setup()
    const first = render(<Block />)
    await user.click(screen.getByRole('button', { name: /^Свернуть/ }))
    first.unmount()

    render(<Block />)

    expect(screen.getByRole('button', { name: /^Развернуть/ })).toBeInTheDocument()
    expect(screen.queryByText('Три источника молчат')).toBeNull()
  })

  it('starts folded when asked to, until the reader opens it', async () => {
    const user = userEvent.setup()
    const first = render(<Block defaultOpen={false} />)
    expect(screen.queryByText('Три источника молчат')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Развернуть: Здоровье источников' }))
    expect(screen.getByText('Три источника молчат')).toBeInTheDocument()
    first.unmount()

    render(<Block defaultOpen={false} />)

    expect(screen.getByText('Три источника молчат')).toBeInTheDocument()
  })
})
