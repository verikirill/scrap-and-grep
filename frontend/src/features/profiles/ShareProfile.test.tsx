import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Profile } from '../../lib/api'
import { useProfiles } from '../../lib/queries'
import { makeProfile } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { ShareProfileButton } from './ShareProfile'

const TOKEN = 'Qw7rT2xKp9'
const LINK = `http://localhost:3000/share/${TOKEN}`
const shareUrl = apiUrl('/profiles/profile-1/share')

/** The share button over the profile in the cached list, as the profiles page shows it. */
function ShareStoredProfile() {
  const profiles = useProfiles()
  const stored = profiles.data?.find((profile) => profile.id === 'profile-1')
  return stored ? <ShareProfileButton profile={stored} /> : null
}

/** The profile on the server: its link opens and closes; what was asked is kept in order. */
function serveProfile(initial: Profile) {
  let profile = initial
  const asked: string[] = []
  server.use(
    http.get(apiUrl('/profiles'), () => HttpResponse.json([profile])),
    http.post(shareUrl, () => {
      asked.push('open')
      profile = { ...profile, share_token: TOKEN }
      return HttpResponse.json(profile)
    }),
    http.delete(shareUrl, () => {
      asked.push('close')
      profile = { ...profile, share_token: null }
      return HttpResponse.json(profile)
    }),
  )
  return asked
}

async function openDialog(user: ReturnType<typeof renderWithProviders>['user']) {
  await user.click(await screen.findByRole('button', { name: 'Поделиться' }))
  return screen.findByRole('dialog', { name: 'Поделиться профилем' })
}

afterEach(() => {
  Reflect.deleteProperty(navigator, 'share')
})

describe('ShareProfileButton', () => {
  it('makes a link to the profile and shows it ready to copy', async () => {
    const asked = serveProfile(makeProfile())
    const { user } = renderWithProviders(<ShareStoredProfile />)

    const dialog = await openDialog(user)
    expect(within(dialog).getByText('Инженер АСУ ТП')).toBeInTheDocument()
    // A profile without an icon shows its first letter.
    expect(within(dialog).getByText('И')).toBeInTheDocument()
    expect(within(dialog).queryByRole('textbox', { name: 'Ссылка на профиль' })).toBeNull()

    await user.click(within(dialog).getByRole('button', { name: 'Создать ссылку' }))

    expect(await within(dialog).findByRole('textbox', { name: 'Ссылка на профиль' })).toHaveValue(
      LINK,
    )
    expect(within(dialog).getByRole('button', { name: 'Копировать' })).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Закрыть доступ' })).toBeInTheDocument()
    // Without a system share sheet there is nothing to send the link through.
    expect(within(dialog).queryByRole('button', { name: 'Отправить' })).toBeNull()
    expect(asked).toEqual(['open'])
  })

  it('copies the link and says so for a moment', async () => {
    serveProfile(makeProfile({ share_token: TOKEN }))
    const { user } = renderWithProviders(<ShareStoredProfile />)
    const dialog = await openDialog(user)

    // The moment is two seconds of the test's clock. user-event waits on timers
    // of its own and would never return under a fake clock: a plain click here.
    vi.useFakeTimers()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Копировать' }))

    await vi.waitFor(() => screen.getByText('Ссылка скопирована'))
    expect(within(dialog).getByRole('button', { name: 'Скопировано' })).toBeInTheDocument()
    vi.advanceTimersByTime(2000)
    await vi.waitFor(() => within(dialog).getByRole('button', { name: 'Копировать' }))
    // The clipboard stub reads its contents through timers: real ones again.
    vi.useRealTimers()
    expect(await navigator.clipboard.readText()).toBe(LINK)
  })

  it('selects the link for the reader to copy when the clipboard refuses', async () => {
    serveProfile(makeProfile({ share_token: TOKEN }))
    const { user } = renderWithProviders(<ShareStoredProfile />)
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(
      new DOMException('Write permission denied.', 'NotAllowedError'),
    )
    const dialog = await openDialog(user)
    const field = within(dialog).getByRole('textbox', { name: 'Ссылка на профиль' })

    await user.click(within(dialog).getByRole('button', { name: 'Копировать' }))

    expect(await screen.findByText('Ссылка выделена, скопируйте её')).toBeInTheDocument()
    expect(field).toHaveProperty('selectionStart', 0)
    expect(field).toHaveProperty('selectionEnd', LINK.length)
    expect(within(dialog).getByRole('button', { name: 'Копировать' })).toBeInTheDocument()
  })

  it('closes the link and offers to make a new one', async () => {
    const asked = serveProfile(makeProfile({ share_token: TOKEN }))
    const { user } = renderWithProviders(<ShareStoredProfile />)
    const dialog = await openDialog(user)

    await user.click(within(dialog).getByRole('button', { name: 'Закрыть доступ' }))

    expect(await within(dialog).findByRole('button', { name: 'Создать ссылку' })).toBeEnabled()
    expect(within(dialog).queryByRole('textbox', { name: 'Ссылка на профиль' })).toBeNull()
    expect(asked).toEqual(['close'])
  })

  it('hands the link to the system share sheet, and a sheet closed unused is no error', async () => {
    const share = vi
      .fn<(data: ShareData) => Promise<void>>()
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new DOMException('Share canceled', 'AbortError'))
    Object.defineProperty(navigator, 'share', { configurable: true, value: share })
    serveProfile(makeProfile({ share_token: TOKEN }))
    const { user } = renderWithProviders(<ShareStoredProfile />)
    const dialog = await openDialog(user)

    await user.click(within(dialog).getByRole('button', { name: 'Отправить' }))
    expect(share).toHaveBeenCalledWith({
      title: 'Инженер АСУ ТП',
      text: 'Профиль интересов в Scrap&Grep',
      url: LINK,
    })

    await user.click(within(dialog).getByRole('button', { name: 'Отправить' }))
    await waitFor(() => expect(share).toHaveBeenCalledTimes(2))
    await expect(share.mock.results[1].value).rejects.toThrow('Share canceled')
    expect(within(dialog).queryByRole('alert')).toBeNull()
  })

  it('shows why the link was not made and forgets it when the dialog opens again', async () => {
    serveProfile(makeProfile())
    server.use(
      http.post(shareUrl, () => HttpResponse.json({ detail: 'Профиль удалён' }, { status: 404 })),
    )
    const { user } = renderWithProviders(<ShareStoredProfile />)
    const dialog = await openDialog(user)

    await user.click(within(dialog).getByRole('button', { name: 'Создать ссылку' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Профиль удалён')

    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    const again = await openDialog(user)
    expect(within(again).queryByRole('alert')).toBeNull()
    expect(within(again).getByRole('button', { name: 'Создать ссылку' })).toBeEnabled()
  })
})
