import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import type { Profile } from '../lib/api'
import { makeProfile, makeSharedProfile } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { DigestPage } from './DigestPage'
import { SharePage } from './SharePage'

const TOKEN = 'Qw7rT2xKp9'

/**
 * The reader's account on the server: a copy taken by link joins their
 * profiles. The list is answered at once the first time; any later read waits
 * for the test, so the screen can be checked before it comes back.
 */
function serveReader() {
  const shared = makeSharedProfile()
  let profiles: Profile[] = [makeProfile()]
  let reads = 0
  let release = () => {}
  const released = new Promise<void>((resolve) => {
    release = resolve
  })
  server.use(
    http.get(apiUrl('/profiles'), async () => {
      reads += 1
      if (reads > 1) await released
      return HttpResponse.json(profiles)
    }),
    http.get(apiUrl('/digests'), () => HttpResponse.json([])),
    http.get(apiUrl('/digest-schedules'), () => HttpResponse.json([])),
    http.get(apiUrl(`/shared-profiles/${TOKEN}`), () => HttpResponse.json(shared)),
    http.post(apiUrl(`/shared-profiles/${TOKEN}/accept`), () => {
      const copy = makeProfile({
        id: 'profile-2',
        spec: shared.spec,
        icon: shared.icon,
        color: shared.color,
      })
      profiles = [...profiles, copy]
      return HttpResponse.json(copy)
    }),
  )
  return { release, reads: () => reads }
}

describe('SharePage', () => {
  it('opens a profile link over the digest page and lands there with the copy picked', async () => {
    const account = serveReader()
    const { user } = renderWithProviders(
      <Routes>
        <Route path="/share/:token" element={<SharePage />} />
        <Route path="/" element={<DigestPage />} />
      </Routes>,
      { route: `/share/${TOKEN}` },
    )

    const dialog = await screen.findByRole('dialog', { name: 'Защита подстанций' })
    // The digest page is underneath, hidden from assistive tech while the dialog is open.
    expect(screen.getByRole('heading', { name: 'Дайджест', hidden: true })).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Добавить себе' }))

    // The copy is picked at once, before the list of profiles is read again.
    const profiles = await screen.findByRole('radiogroup', { name: 'Профиль читателя' })
    await waitFor(() => expect(account.reads()).toBe(2))
    expect(within(profiles).getByRole('radio', { name: /Защита подстанций/ })).toBeChecked()
    expect(within(profiles).getByRole('radio', { name: /Инженер АСУ ТП/ })).not.toBeChecked()
    expect(screen.getByTestId('location')).toHaveTextContent('/?profile=profile-2')
    expect(screen.queryByRole('dialog')).toBeNull()

    account.release()
    expect(await screen.findByText('Выпусков пока нет')).toBeInTheDocument()
    expect(within(profiles).getByRole('radio', { name: /Защита подстанций/ })).toBeChecked()
  })
})
