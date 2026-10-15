import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './dialog'

function Mail({
  showCloseButton,
  onOpenChange,
}: {
  showCloseButton?: boolean
  onOpenChange?: (open: boolean) => void
}) {
  const [open, setOpen] = useState(true)
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        onOpenChange?.(next)
      }}
    >
      <DialogContent showCloseButton={showCloseButton}>
        <DialogHeader>
          <DialogTitle>Отправить выпуск</DialogTitle>
          <DialogDescription>Письмо уйдёт на указанный адрес.</DialogDescription>
        </DialogHeader>
        <button type="button" onClick={() => setOpen(false)}>
          Отмена
        </button>
      </DialogContent>
    </Dialog>
  )
}

describe('Dialog', () => {
  it('is a dialog named by its title, closed by its cross', async () => {
    const onOpenChange = vi.fn()
    const user = userEvent.setup()
    render(<Mail onOpenChange={onOpenChange} />)
    const dialog = await screen.findByRole('dialog', { name: 'Отправить выпуск' })
    expect(dialog).toHaveTextContent('Письмо уйдёт на указанный адрес.')

    await user.click(screen.getByRole('button', { name: 'Закрыть' }))

    expect(onOpenChange).toHaveBeenCalledWith(false)
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('closes on Escape', async () => {
    const user = userEvent.setup()
    render(<Mail />)
    await screen.findByRole('dialog', { name: 'Отправить выпуск' })
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('leaves the cross out when the dialog has its own way out', async () => {
    render(<Mail showCloseButton={false} />)
    await screen.findByRole('dialog', { name: 'Отправить выпуск' })
    expect(screen.queryByRole('button', { name: 'Закрыть' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Отмена' })).toBeInTheDocument()
  })
})
