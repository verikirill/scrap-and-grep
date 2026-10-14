import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { makeDigest, makeMailState } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { MailButton } from './MailButton'

const mailUrl = apiUrl('/digests/digest-1/mail')

/** The mail state the server gives; returns how many times it was asked. */
function answerMailState(state = makeMailState()) {
  const asked = { count: 0 }
  server.use(
    http.get(mailUrl, () => {
      asked.count += 1
      return HttpResponse.json(state)
    }),
  )
  return asked
}

describe('MailButton', () => {
  it('stays away when the server has no mail service', async () => {
    const asked = answerMailState(makeMailState({ available: false }))
    renderWithProviders(<MailButton digest={makeDigest()} />)
    // The state request is answered and nothing appears.
    await waitFor(() => expect(asked.count).toBe(1))
    expect(screen.queryByRole('button', { name: 'На почту' })).toBeNull()
  })

  it('stays away for an issue still being built, without asking the server', () => {
    // No handler: a request would fail the test.
    renderWithProviders(<MailButton digest={makeDigest({ status: 'running' })} />)
    expect(screen.queryByRole('button', { name: 'На почту' })).toBeNull()
  })

  it('sends the issue to the address typed over the reader’s own and says where', async () => {
    answerMailState(makeMailState({ domains: ['example.ru'] }))
    let sent: unknown = null
    server.use(
      http.post(mailUrl, async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({ to: 'soc@example.ru' })
      }),
    )
    const { user } = renderWithProviders(<MailButton digest={makeDigest()} />)

    await user.click(await screen.findByRole('button', { name: 'На почту' }))
    const dialog = await screen.findByRole('dialog', { name: 'Выпуск на почту' })
    const field = within(dialog).getByRole('textbox', { name: /Кому/ })
    expect(field).toHaveValue('analyst@example.ru')
    expect(within(dialog).getByText('только example.ru')).toBeInTheDocument()

    await user.clear(field)
    await user.type(field, 'soc@example.ru')
    await user.click(within(dialog).getByRole('button', { name: 'Отправить' }))

    expect(await screen.findByText('Выпуск отправлен на soc@example.ru')).toBeInTheDocument()
    expect(sent).toEqual({ to: 'soc@example.ru' })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('shows the server’s refusal in the dialog and forgets it once the dialog is closed', async () => {
    answerMailState()
    server.use(
      http.post(mailUrl, () =>
        HttpResponse.json({ detail: 'Адрес вне разрешённых доменов' }, { status: 422 }),
      ),
    )
    const { user } = renderWithProviders(<MailButton digest={makeDigest()} />)

    await user.click(await screen.findByRole('button', { name: 'На почту' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Отправить' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'Адрес вне разрешённых доменов',
    )

    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    await user.click(screen.getByRole('button', { name: 'На почту' }))
    expect(within(await screen.findByRole('dialog')).queryByRole('alert')).toBeNull()
  })
})
