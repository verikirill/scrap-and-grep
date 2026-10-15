import { screen, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { makeInvite, makeMe } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { InvitePage } from './InvitePage'

const TOKEN = 'oleg-link-0000000000000000000'
const PASSWORD = 'correct-horse-battery'

function renderPage() {
  return renderWithProviders(<InvitePage />, {
    route: `/invite/${TOKEN}`,
    path: '/invite/:token',
  })
}

describe('InvitePage', () => {
  it('shows who invited the person and what is set up, then lets them in with a password', async () => {
    let sentPassword: unknown = null
    let isSignedIn = false
    server.use(
      http.get(apiUrl(`/auth/invite/${TOKEN}`), () => HttpResponse.json(makeInvite())),
      http.post(apiUrl(`/auth/invite/${TOKEN}`), async ({ request }) => {
        sentPassword = ((await request.json()) as { password: string }).password
        isSignedIn = true
        return HttpResponse.json(makeMe())
      }),
      http.get(apiUrl('/auth/me'), () =>
        HttpResponse.json(isSignedIn ? makeMe({ onboarded_at: null }) : null),
      ),
    )
    const { user } = renderPage()

    expect(await screen.findByText('Здравствуйте, Олег Смирнов')).toBeInTheDocument()
    expect(
      screen.getByText('Анна Петрова приглашает вас в команду «SOC» компании «Энергосеть».'),
    ).toBeInTheDocument()
    expect(screen.getByText('Безопасность АСУ ТП')).toBeInTheDocument()
    expect(screen.getByText(/Выпуски придут карточками/)).toBeInTheDocument()

    const submit = screen.getByRole('button', { name: 'Задать пароль и войти' })
    await user.type(screen.getByLabelText(/Придумайте пароль/), 'short')
    expect(submit).toBeDisabled()
    await user.clear(screen.getByLabelText(/Придумайте пароль/))
    await user.type(screen.getByLabelText(/Придумайте пароль/), PASSWORD)
    await user.click(submit)

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/start'))
    expect(sentPassword).toBe(PASSWORD)
  })

  it('says a used or old link needs a new one and leads to the sign-in page', async () => {
    server.use(
      http.get(apiUrl(`/auth/invite/${TOKEN}`), () =>
        HttpResponse.json(
          {
            detail: 'Ссылка устарела или уже использована. Попросите руководителя прислать новую.',
          },
          { status: 404 },
        ),
      ),
    )
    renderPage()

    expect(await screen.findByText('Приглашение не открылось')).toBeInTheDocument()
    expect(screen.getByText(/Попросите руководителя прислать новую/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ко входу' })).toHaveAttribute('href', '/login')
  })
})
