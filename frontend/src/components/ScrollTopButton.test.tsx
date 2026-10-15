import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { hasReducedMotionListener } from 'motion-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setMediaQueries } from '../test/browser'
import { ScrollTopButton } from './ScrollTopButton'

function scrollTo(y: number) {
  act(() => {
    window.scrollY = y
    fireEvent.scroll(window)
  })
}

describe('ScrollTopButton', () => {
  beforeEach(() => {
    // motion reads the reduced-motion setting once per module; let it read
    // what this test chose.
    hasReducedMotionListener.current = false
  })
  afterEach(() => {
    window.scrollY = 0
  })

  it('appears once the reader is past a screen of text and hides back at the top', async () => {
    render(<ScrollTopButton />)
    expect(screen.queryByRole('button', { name: 'Наверх' })).toBeNull()

    scrollTo(500)
    // A sentinel: the frame that reads the scroll has run when 701 shows it.
    await new Promise((resolve) => requestAnimationFrame(resolve))
    expect(screen.queryByRole('button', { name: 'Наверх' })).toBeNull()

    scrollTo(701)
    expect(await screen.findByRole('button', { name: 'Наверх' })).toBeInTheDocument()

    scrollTo(0)
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Наверх' })).toBeNull())
  })

  it('shows at once on a page opened far down', () => {
    window.scrollY = 2000
    render(<ScrollTopButton />)
    expect(screen.getByRole('button', { name: 'Наверх' })).toBeInTheDocument()
  })

  it('takes the page to its top smoothly', async () => {
    const scroll = vi.spyOn(window, 'scrollTo')
    window.scrollY = 2000
    const user = userEvent.setup()
    render(<ScrollTopButton />)

    await user.click(screen.getByRole('button', { name: 'Наверх' }))

    expect(scroll).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
  })

  it('jumps without the smooth ride for a reader who turned motion down', async () => {
    setMediaQueries({ '(prefers-reduced-motion)': true })
    const scroll = vi.spyOn(window, 'scrollTo')
    window.scrollY = 2000
    const user = userEvent.setup()
    render(<ScrollTopButton />)

    await user.click(screen.getByRole('button', { name: 'Наверх' }))

    expect(scroll).toHaveBeenCalledWith({ top: 0, behavior: 'auto' })
  })
})
