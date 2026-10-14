import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, delay, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Profile } from '../../lib/api'
import { colorOf } from '../../lib/profileLook'
import { useProfiles } from '../../lib/queries'
import { makeProfile } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { ProfileLookPicker } from './ProfileLook'

type Look = { icon: string | null; color: string | null }
const lookUrl = apiUrl('/profiles/profile-1/look')

/** The picker over the profile in the cached list, as the profiles page shows it. */
function StoredPicker() {
  const profiles = useProfiles()
  const stored = profiles.data?.find((profile) => profile.id === 'profile-1')
  return stored ? <ProfileLookPicker profile={stored} /> : null
}

/**
 * The profile on the server; looks are kept in the order they arrive. The
 * first one may be slow, as behind a busy replica.
 */
function serveProfile(initial: Profile, { firstDelayMs = 0 } = {}) {
  let profile = initial
  const arrived: Look[] = []
  let started = 0
  server.use(
    http.get(apiUrl('/profiles'), () => HttpResponse.json([profile])),
    http.patch(lookUrl, async ({ request }) => {
      const look = (await request.json()) as Look
      started += 1
      if (started === 1 && firstDelayMs > 0) await delay(firstDelayMs)
      arrived.push(look)
      profile = { ...profile, ...look }
      return HttpResponse.json(profile)
    }),
  )
  return arrived
}

async function openPicker(user: ReturnType<typeof renderWithProviders>['user']) {
  await user.click(await screen.findByRole('button', { name: 'Значок и цвет профиля' }))
  return screen.findByRole('radiogroup', { name: 'Значок профиля' })
}

describe('ProfileLookPicker', () => {
  it('picks an icon and keeps the colour the profile has', async () => {
    const arrived = serveProfile(makeProfile({ icon: null, color: 'teal' }))
    const { user } = renderWithProviders(<StoredPicker />)
    const icons = await openPicker(user)
    expect(within(icons).queryByRole('radio', { checked: true })).toBeNull()
    expect(screen.getByRole('radio', { name: 'Бирюзовый' })).toBeChecked()

    await user.click(within(icons).getByRole('radio', { name: 'Энергетика' }))

    expect(within(icons).getByRole('radio', { name: 'Энергетика' })).toBeChecked()
    await waitFor(() => expect(arrived).toEqual([{ icon: 'energy', color: 'teal' }]))
  })

  it('sends quick picks in the order they were made, each with the other’s latest half', async () => {
    const arrived = serveProfile(makeProfile(), { firstDelayMs: 500 })
    const { user } = renderWithProviders(<StoredPicker />)
    const icons = await openPicker(user)

    await user.click(within(icons).getByRole('radio', { name: 'Энергетика' }))
    await user.click(screen.getByRole('radio', { name: 'Красный' }))

    // Both show at once, before the server has answered either.
    expect(within(icons).getByRole('radio', { name: 'Энергетика' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Красный' })).toBeChecked()
    await waitFor(() => expect(arrived).toHaveLength(2))
    expect(arrived).toEqual([
      { icon: 'energy', color: null },
      { icon: 'energy', color: 'red' },
    ])
    expect(screen.getByRole('radio', { name: 'Красный' })).toBeChecked()
  })

  it('puts the look back when the server refuses it', async () => {
    server.use(
      // The list is read once; after the refusal it cannot be read again, so
      // only the client's own rollback can restore the look.
      http.get(apiUrl('/profiles'), () => HttpResponse.json([makeProfile({ icon: 'shield' })]), {
        once: true,
      }),
      http.get(apiUrl('/profiles'), () =>
        HttpResponse.json({ detail: 'Нет связи' }, { status: 503 }),
      ),
      http.patch(lookUrl, () => HttpResponse.json({ detail: 'Нет связи' }, { status: 503 })),
    )
    const { user } = renderWithProviders(<StoredPicker />)
    const icons = await openPicker(user)

    await user.click(within(icons).getByRole('radio', { name: 'Энергетика' }))

    await waitFor(() => expect(within(icons).getByRole('radio', { name: 'Защита' })).toBeChecked())
    expect(within(icons).getByRole('radio', { name: 'Энергетика' })).not.toBeChecked()
  })

  it('starts a colour of one’s own and sends a typed code when the picker closes', async () => {
    const arrived = serveProfile(makeProfile({ icon: 'shield', color: 'blue' }))
    const { user } = renderWithProviders(<StoredPicker />)
    await openPicker(user)

    await user.click(screen.getByRole('radio', { name: 'Свой цвет' }))

    // jsdom has no palette styles: the picker starts from its fallback colour.
    const start = colorOf(200, 48)
    await waitFor(() => expect(arrived).toEqual([{ icon: 'shield', color: start }]))
    expect(screen.getByRole('radio', { name: 'Свой цвет' })).toBeChecked()
    const code = await screen.findByRole('textbox', { name: 'Код цвета' })
    expect(code).toHaveValue(start)
    expect(screen.getByRole('slider', { name: 'Оттенок' })).toHaveValue('200')

    await user.clear(code)
    await user.type(code, '336699')
    expect(code).toHaveValue('#336699')
    expect(arrived).toHaveLength(1)
    await user.keyboard('{Escape}')

    await waitFor(() => expect(arrived).toHaveLength(2))
    expect(arrived[1]).toEqual({ icon: 'shield', color: '#336699' })
  })

  it('sends a typed colour once the hand stops, and marks a code that is not one', async () => {
    const arrived = serveProfile(makeProfile({ icon: 'shield', color: '#3366aa' }))
    const { user } = renderWithProviders(<StoredPicker />)
    await openPicker(user)
    const code = screen.getByRole('textbox', { name: 'Код цвета' })

    await user.clear(code)
    await user.type(code, '33669')
    expect(code).toHaveAttribute('aria-invalid', 'true')
    await user.type(code, '9')
    expect(code).toHaveAttribute('aria-invalid', 'false')
    // Typing on: nothing is sent until 0,4 s of quiet.
    expect(arrived).toEqual([])

    await waitFor(() => expect(arrived).toEqual([{ icon: 'shield', color: '#336699' }]))
  })
})
