import { screen, waitFor } from '@testing-library/react'
import { HttpResponse, delay, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Settings } from '../../lib/api'
import { useMe } from '../../lib/queries'
import { makeMe, makeSettings } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { FeedViewSetting } from './FeedViewSetting'

/** The setting as the account page shows it: drawn from the cached account. */
function Setting() {
  const me = useMe().data
  return me ? <FeedViewSetting me={me} /> : null
}

describe('FeedViewSetting', () => {
  it('switches the look at once and keeps it with the account', async () => {
    let saved: Partial<Settings> | null = null
    let me = makeMe({ feed_view: 'cards' })
    server.use(
      http.get(apiUrl('/auth/me'), () => HttpResponse.json(me)),
      http.patch(apiUrl('/auth/me/settings'), async ({ request }) => {
        saved = (await request.json()) as Partial<Settings>
        // The look is on screen before the server answers.
        await delay(50)
        me = { ...me, ...saved }
        return HttpResponse.json(makeSettings(saved))
      }),
    )
    const { user } = renderWithProviders(<Setting />)

    expect(await screen.findByRole('radio', { name: /Карточки/ })).toBeChecked()
    await user.click(screen.getByRole('radio', { name: /Как в Telegram/ }))

    expect(screen.getByRole('radio', { name: /Как в Telegram/ })).toBeChecked()
    await waitFor(() => expect(saved).toEqual({ feed_view: 'telegram' }))
  })

  it('puts the look back and says why when the server refuses it', async () => {
    server.use(
      // The account is read once; after the refusal the server is down for it
      // too, so only the rollback can bring the old look back.
      http.get(apiUrl('/auth/me'), () => HttpResponse.json(makeMe({ feed_view: 'cards' })), {
        once: true,
      }),
      http.get(apiUrl('/auth/me'), () => new HttpResponse(null, { status: 503 })),
      http.patch(apiUrl('/auth/me/settings'), () =>
        HttpResponse.json({ detail: 'Настройки сейчас не сохраняются' }, { status: 503 }),
      ),
    )
    const { user } = renderWithProviders(<Setting />)

    await user.click(await screen.findByRole('radio', { name: /Как в Telegram/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Настройки сейчас не сохраняются')
    expect(screen.getByRole('radio', { name: /Карточки/ })).toBeChecked()
  })
})
