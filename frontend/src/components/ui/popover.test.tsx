import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { Popover, PopoverContent, PopoverTrigger } from './popover'

function Schedule() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <p>{open ? 'открыто' : 'закрыто'}</p>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button type="button">Расписание</button>
        </PopoverTrigger>
        <PopoverContent align="end">
          <p>Каждый день в 09:00</p>
          <button type="button" onClick={() => setOpen(false)}>
            Готово
          </button>
        </PopoverContent>
      </Popover>
    </>
  )
}

describe('Popover', () => {
  it('opens from its trigger and reports the state it keeps outside', async () => {
    const user = userEvent.setup()
    render(<Schedule />)
    expect(screen.queryByText('Каждый день в 09:00')).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Расписание' }))

    expect(await screen.findByRole('dialog')).toHaveTextContent('Каждый день в 09:00')
    expect(screen.getByText('открыто')).toBeInTheDocument()
  })

  it('closes on Escape and from inside', async () => {
    const user = userEvent.setup()
    render(<Schedule />)
    await user.click(screen.getByRole('button', { name: 'Расписание' }))
    await screen.findByRole('dialog')
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(screen.getByText('закрыто')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Расписание' }))
    await user.click(await screen.findByRole('button', { name: 'Готово' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })
})
