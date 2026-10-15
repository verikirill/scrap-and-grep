import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { NotFoundPage } from './NotFoundPage'

/** The page at an unknown address, last of the given history entries. */
function renderAt(entries: string[]) {
  const user = userEvent.setup()
  const result = render(
    <MemoryRouter initialEntries={entries} initialIndex={entries.length - 1}>
      <Routes>
        <Route path="/" element={<p>Дайджест</p>} />
        <Route path="/feed" element={<p>Лента</p>} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </MemoryRouter>,
  )
  return { ...result, user }
}

describe('NotFoundPage', () => {
  it('says there is no such page, under the cat with the magnifier', () => {
    const { container } = renderAt(['/nowhere'])
    expect(screen.getByRole('heading', { level: 1, name: 'Такой страницы нет' })).toBeVisible()
    expect(screen.getByText('404')).toBeInTheDocument()
    // The first thing on the page: loaded at once, and silent for a screen reader.
    const art = container.querySelector('img')
    expect(art).toHaveAttribute('src', '/brand/errors/404.webp')
    expect(art).toHaveAttribute('alt', '')
    expect(art).toHaveAttribute('loading', 'eager')
    expect(art).toHaveAttribute('width', '240')
    expect(art).toHaveAttribute('height', '241')
  })

  it('goes home on «На главную»', async () => {
    const { user } = renderAt(['/feed', '/nowhere'])
    await user.click(screen.getByRole('button', { name: 'На главную' }))
    expect(screen.getByText('Дайджест')).toBeInTheDocument()
  })

  it('goes back to the page it came from on «Назад»', async () => {
    const { user } = renderAt(['/feed', '/nowhere'])
    await user.click(screen.getByRole('button', { name: 'Назад' }))
    expect(screen.getByText('Лента')).toBeInTheDocument()
  })

  it('goes home on «Назад» when the tab opened right here', async () => {
    const { user } = renderAt(['/nowhere'])
    await user.click(screen.getByRole('button', { name: 'Назад' }))
    expect(screen.getByText('Дайджест')).toBeInTheDocument()
  })
})
