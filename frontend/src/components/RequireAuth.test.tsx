import { screen } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { Route, Routes, useLocation } from 'react-router'
import { describe, expect, it } from 'vitest'
import { makeMe } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { RequireAuth } from './RequireAuth'
import type { AuthRedirect } from './RequireAuth'

function SignInPage() {
  const state = useLocation().state as AuthRedirect | null
  return <p>Вход, потом {state?.from}</p>
}

function renderGuarded(route = '/feed?tab=top') {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<SignInPage />} />
      <Route
        path="*"
        element={
          <RequireAuth>
            <p>Лента читателя</p>
          </RequireAuth>
        }
      />
    </Routes>,
    { route },
  )
}

describe('RequireAuth', () => {
  it('says it is checking the session, then shows the page to a signed-in reader', async () => {
    renderGuarded()
    expect(screen.getByRole('status', { name: 'Проверяем вход' })).toBeInTheDocument()
    expect(await screen.findByText('Лента читателя')).toBeInTheDocument()
    expect(screen.queryByRole('status', { name: 'Проверяем вход' })).toBeNull()
  })

  it('sends a visitor without a session to sign in, remembering where they were going', async () => {
    server.use(http.get(apiUrl('/auth/me'), () => HttpResponse.json(null)))
    renderGuarded('/feed?tab=top')

    expect(await screen.findByText('Вход, потом /feed?tab=top')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/login')
    expect(screen.queryByText('Лента читателя')).toBeNull()
  })

  it('shows why the session could not be checked and tries again on request', async () => {
    server.use(
      http.get(
        apiUrl('/auth/me'),
        () => HttpResponse.json({ detail: 'База данных недоступна' }, { status: 503 }),
        { once: true },
      ),
      http.get(apiUrl('/auth/me'), () => HttpResponse.json(makeMe())),
    )
    const { user } = renderGuarded()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Сервис временно недоступен')
    expect(alert).toHaveTextContent('База данных недоступна')
    // The whole screen is the failure: the cat asleep, the service down.
    expect(alert.querySelector('img')).toHaveAttribute('src', '/brand/errors/503.webp')
    expect(screen.queryByText('Лента читателя')).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Повторить попытку' }))

    expect(await screen.findByText('Лента читателя')).toBeInTheDocument()
  })
})
