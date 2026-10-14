import { fireEvent, screen } from '@testing-library/react'
import { Link } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/render'
import { useConfirmLeave } from './useConfirmLeave'

const MESSAGE = 'Изменения профиля не сохранены. Уйти?'

function Editor({ isDirty }: { isDirty: boolean }) {
  useConfirmLeave(isDirty, MESSAGE)
  return (
    <nav>
      <Link to="/feed">Лента</Link>
      <Link to="/profiles">Этот же профиль</Link>
      <a href="/feed" target="_blank">
        Лента в новой вкладке
      </a>
      <a href="https://example.org/post">Статья на сайте</a>
    </nav>
  )
}

function renderEditor(isDirty: boolean) {
  return renderWithProviders(<Editor isDirty={isDirty} />, { route: '/profiles' })
}

const location = () => screen.getByTestId('location')

describe('useConfirmLeave', () => {
  it('asks before a link to another page leaves unsaved work, and stays on «Отмена»', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { user } = renderEditor(true)

    await user.click(screen.getByRole('link', { name: 'Лента' }))

    expect(confirm).toHaveBeenCalledWith(MESSAGE)
    expect(location()).toHaveTextContent('/profiles')
  })

  it('leaves when the reader agrees', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { user } = renderEditor(true)

    await user.click(screen.getByRole('link', { name: 'Лента' }))

    expect(location()).toHaveTextContent('/feed')
  })

  it('does not ask with nothing unsaved', async () => {
    const confirm = vi.spyOn(window, 'confirm')
    const { user } = renderEditor(false)

    await user.click(screen.getByRole('link', { name: 'Лента' }))

    expect(location()).toHaveTextContent('/feed')
    expect(confirm).not.toHaveBeenCalled()
  })

  it('does not ask for a link that leaves the work open', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    // The browser's address, which the hook compares a link with, is the editor's.
    window.history.pushState(null, '', '/profiles')
    const { user } = renderEditor(true)
    // A click jsdom would follow is stopped before it navigates the test page.
    const stopNavigation = (event: MouseEvent) => event.preventDefault()
    document.addEventListener('click', stopNavigation)

    try {
      await user.click(screen.getByRole('link', { name: 'Этот же профиль' }))
      await user.click(screen.getByRole('link', { name: 'Лента в новой вкладке' }))
      await user.click(screen.getByRole('link', { name: 'Статья на сайте' }))
      await user.keyboard('{Control>}')
      await user.click(screen.getByRole('link', { name: 'Лента' }))
      await user.keyboard('{/Control}')
      fireEvent.click(screen.getByRole('link', { name: 'Лента' }), { button: 1 })
    } finally {
      document.removeEventListener('click', stopNavigation)
      window.history.pushState(null, '', '/')
    }

    expect(confirm).not.toHaveBeenCalled()
  })

  it('asks the browser to confirm closing the tab only while work is unsaved', () => {
    const { rerender } = renderEditor(true)
    const dirty = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(dirty)
    expect(dirty.defaultPrevented).toBe(true)

    rerender(<Editor isDirty={false} />)
    const clean = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(clean)
    expect(clean.defaultPrevented).toBe(false)
  })
})
