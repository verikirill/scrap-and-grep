import { fireEvent, screen, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { API_BASE } from '../../lib/api'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { SourceAvatar } from './SourceAvatar'

describe('SourceAvatar', () => {
  it('shows the source’s picture in its current version', async () => {
    server.use(http.get(apiUrl('/sources/avatars'), () => HttpResponse.json({ 7: 'a1b2' })))
    const { container } = renderWithProviders(<SourceAvatar sourceId={7} name="Хабр" />)

    await waitFor(() =>
      expect(container.querySelector('img')).toHaveAttribute(
        'src',
        `${API_BASE}/sources/7/avatar?v=a1b2`,
      ),
    )
  })

  it('draws the initials until the picture loads and when it fails', async () => {
    server.use(http.get(apiUrl('/sources/avatars'), () => HttpResponse.json({ 7: 'a1b2' })))
    const { container } = renderWithProviders(
      <SourceAvatar sourceId={7} name="Kaspersky ICS CERT" />,
    )
    expect(screen.getByText('KI')).toBeInTheDocument()

    await waitFor(() => expect(container.querySelector('img')).not.toBeNull())
    fireEvent.error(container.querySelector('img')!)

    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('KI')).toBeInTheDocument()
  })

  it('draws the initials of a source without a picture', async () => {
    let asked = 0
    server.use(
      http.get(apiUrl('/sources/avatars'), () => {
        asked += 1
        return HttpResponse.json({ 8: 'c3d4' })
      }),
    )
    const { container } = renderWithProviders(<SourceAvatar sourceId={7} name="«Хакер»" />)
    await waitFor(() => expect(asked).toBe(1))
    expect(container.querySelector('img')).toBeNull()
    // Quotes are not letters: «Хакер» is Х.
    expect(screen.getByText('Х')).toBeInTheDocument()
  })
})
