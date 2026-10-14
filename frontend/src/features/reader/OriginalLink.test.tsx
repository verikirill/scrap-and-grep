import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { OriginalLink } from './OriginalLink'

const TITLE = 'Уязвимость в SIMATIC S7-1500'

describe('OriginalLink', () => {
  it('opens the article on its site in a new tab', () => {
    render(<OriginalLink url="https://www.securitylab.ru/news/1.php" title={TITLE} />)

    const link = screen.getByRole('link', { name: `«${TITLE}» на сайте источника` })
    expect(link).toHaveAttribute('href', 'https://www.securitylab.ru/news/1.php')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('does not link to an address that could run code', () => {
    render(<OriginalLink url="javascript:alert(1)" title={TITLE} />)

    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.getByLabelText(`«${TITLE}» на сайте источника`)).not.toHaveAttribute('href')
  })

  it('counts an opening by a click or by the middle button, not by the menu button', () => {
    const onOpen = vi.fn()
    render(
      <OriginalLink url="https://www.securitylab.ru/news/1.php" title={TITLE} onOpen={onOpen} />,
    )
    const link = screen.getByRole('link')

    fireEvent(link, new MouseEvent('auxclick', { bubbles: true, button: 2 }))
    expect(onOpen).not.toHaveBeenCalled()
    fireEvent(link, new MouseEvent('auxclick', { bubbles: true, button: 1 }))
    expect(onOpen).toHaveBeenCalledTimes(1)
    fireEvent.click(link)
    expect(onOpen).toHaveBeenCalledTimes(2)
  })
})
