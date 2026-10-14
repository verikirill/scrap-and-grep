import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from './sheet'

function Taste({ side }: { side?: 'right' | 'bottom' }) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <button type="button">Из чего собрана лента</button>
      </SheetTrigger>
      <SheetContent side={side}>
        <SheetHeader>
          <SheetTitle>Вкус ленты</SheetTitle>
          <SheetDescription>Что вы отмечали</SheetDescription>
        </SheetHeader>
        <p>Темы и источники</p>
      </SheetContent>
    </Sheet>
  )
}

describe('Sheet', () => {
  it('opens from its trigger as a dialog named by its title, closed by its cross', async () => {
    const user = userEvent.setup()
    render(<Taste />)

    await user.click(screen.getByRole('button', { name: 'Из чего собрана лента' }))

    const dialog = await screen.findByRole('dialog', { name: 'Вкус ленты' })
    expect(within(dialog).getByText('Темы и источники')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Закрыть' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('follows an open state held outside', async () => {
    function Outside() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            Настройки канала
          </button>
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetContent side="bottom">
              <SheetTitle>Канал @radar</SheetTitle>
            </SheetContent>
          </Sheet>
        </>
      )
    }
    const user = userEvent.setup()
    render(<Outside />)
    expect(screen.queryByRole('dialog')).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Настройки канала' }))
    expect(await screen.findByRole('dialog', { name: 'Канал @radar' })).toBeInTheDocument()

    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })
})
