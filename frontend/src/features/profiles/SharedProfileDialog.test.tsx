import { QueryClient, keepPreviousData } from '@tanstack/react-query'
import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { SharedProfile } from '../../lib/api'
import { makeProfile, makeSharedProfile, makeSpec } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { SharedProfileDialog } from './SharedProfileDialog'

const TOKEN = 'Qw7rT2xKp9'
const sharedUrl = apiUrl(`/shared-profiles/${TOKEN}`)
const acceptUrl = apiUrl(`/shared-profiles/${TOKEN}/accept`)

/** An answer the test lets through when it chooses, to see the screen while it waits. */
function hold() {
  let release = () => {}
  const released = new Promise<void>((resolve) => {
    release = resolve
  })
  return { released, release }
}

const location = () => screen.getByTestId('location').textContent

/** The colleague's profile behind the link, and the copy the server makes of it. */
function serveLink(shared: SharedProfile = makeSharedProfile()) {
  const copy = makeProfile({
    id: 'profile-2',
    spec: shared.spec,
    icon: shared.icon,
    color: shared.color,
  })
  const accepted: string[] = []
  server.use(
    http.get(sharedUrl, () => HttpResponse.json(shared)),
    http.post(acceptUrl, ({ request }) => {
      accepted.push(request.method)
      return HttpResponse.json(copy)
    }),
  )
  return accepted
}

function renderLink(options: { client?: QueryClient } = {}) {
  return renderWithProviders(<SharedProfileDialog token={TOKEN} />, {
    route: `/share/${TOKEN}`,
    ...options,
  })
}

describe('SharedProfileDialog', () => {
  it('shows what the link holds once it has loaded', async () => {
    const answer = hold()
    server.use(
      http.get(sharedUrl, async () => {
        await answer.released
        return HttpResponse.json(makeSharedProfile())
      }),
    )
    renderLink()

    const loading = await screen.findByRole('dialog', { name: 'Профиль по ссылке' })
    expect(loading).toHaveTextContent('Загружаем профиль, которым с вами поделились.')

    answer.release()
    const dialog = await screen.findByRole('dialog', { name: 'Защита подстанций' })
    expect(within(dialog).getByText('Вам прислали профиль')).toBeInTheDocument()
    expect(within(dialog).getByText('Руководитель группы ИБ АСУ ТП')).toBeInTheDocument()
    expect(within(dialog).getByRole('heading', { name: 'Интересы, 2' })).toBeInTheDocument()
    expect(
      within(dialog)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['Уязвимости АСУ ТП', 'Атаки на энергетику'])
    expect(within(dialog).queryByRole('heading', { name: 'Не показывать' })).toBeNull()
    expect(
      within(dialog).getByText('Языки: русский и английский. До 20 публикаций в выпуске.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByText(/Добавится ваша копия/)).toBeInTheDocument()
  })

  it('says when a profile has no role, and lists what it leaves out', async () => {
    serveLink(
      makeSharedProfile({
        spec: makeSpec({
          name: 'Мониторинг подрядчиков',
          role: '',
          exclusions: ['реклама', 'вебинары'],
          languages: ['en', 'de'],
          max_items: 15,
        }),
      }),
    )
    renderLink()

    const dialog = await screen.findByRole('dialog', { name: 'Мониторинг подрядчиков' })
    expect(
      within(dialog).getByText('Роль не описана, профиль задан только интересами.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByRole('heading', { name: 'Не показывать' })).toBeInTheDocument()
    expect(within(dialog).getByText('реклама')).toBeInTheDocument()
    expect(within(dialog).getByText('вебинары')).toBeInTheDocument()
    // A language the app has no name for is shown by its code.
    expect(
      within(dialog).getByText('Языки: английский и de. До 15 публикаций в выпуске.'),
    ).toBeInTheDocument()
  })

  it('takes a copy, says so and opens the digest page with it picked', async () => {
    const accepted = serveLink()
    const { user } = renderLink()

    const dialog = await screen.findByRole('dialog', { name: 'Защита подстанций' })
    await user.click(within(dialog).getByRole('button', { name: 'Добавить себе' }))

    expect(await screen.findByText('Профиль «Защита подстанций» добавлен')).toBeInTheDocument()
    await waitFor(() => expect(location()).toBe('/?profile=profile-2'))
    expect(accepted).toEqual(['POST'])
  })

  it('stays open while the copy is being made, even on Escape', async () => {
    serveLink()
    const answer = hold()
    server.use(
      http.post(acceptUrl, async () => {
        await answer.released
        return HttpResponse.json(makeProfile({ id: 'profile-2' }))
      }),
    )
    const { user } = renderLink()
    const dialog = await screen.findByRole('dialog', { name: 'Защита подстанций' })

    await user.click(within(dialog).getByRole('button', { name: 'Добавить себе' }))
    expect(within(dialog).getByRole('button', { name: 'Добавить себе' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(within(dialog).getByRole('button', { name: 'Отклонить' })).toBeDisabled()
    // The busy button keeps no keys: the reader clicks into the dialog, then presses Escape.
    await user.click(within(dialog).getByText('Вам прислали профиль'))
    await user.keyboard('{Escape}')
    expect(screen.getByRole('dialog', { name: 'Защита подстанций' })).toBeInTheDocument()
    expect(location()).toBe(`/share/${TOKEN}`)

    // The answer names the new profile, and the dialog leaves with it.
    answer.release()
    await waitFor(() => expect(location()).toBe('/?profile=profile-2'))
  })

  it('shows why the copy was refused and lets the reader try again', async () => {
    serveLink()
    server.use(
      http.post(
        acceptUrl,
        () => HttpResponse.json({ detail: 'Ссылка больше не действует' }, { status: 410 }),
        { once: true },
      ),
    )
    const { user } = renderLink()
    const dialog = await screen.findByRole('dialog', { name: 'Защита подстанций' })

    await user.click(within(dialog).getByRole('button', { name: 'Добавить себе' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Ссылка больше не действует')
    expect(location()).toBe(`/share/${TOKEN}`)
    expect(within(dialog).getByRole('button', { name: 'Добавить себе' })).toBeEnabled()
  })

  it('opens the reader’s own profile when they already have it', async () => {
    serveLink(makeSharedProfile({ own_id: 'profile-1' }))
    const { user } = renderLink()

    const dialog = await screen.findByRole('dialog', { name: 'Защита подстанций' })
    expect(within(dialog).getByText('Такой профиль уже есть у вас.')).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Добавить себе' })).toBeNull()
    expect(within(dialog).getByRole('button', { name: 'Закрыть' })).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Открыть профиль' }))

    await waitFor(() => expect(location()).toBe('/?profile=profile-1'))
  })

  it.each([
    [
      'the button',
      (user: UserEvent) => user.click(screen.getByRole('button', { name: 'Отклонить' })),
    ],
    ['Escape', (user: UserEvent) => user.keyboard('{Escape}')],
  ])('leaves for the digest page without a copy by %s', async (_way, decline) => {
    const accepted = serveLink()
    const { user } = renderLink()
    await screen.findByRole('dialog', { name: 'Защита подстанций' })

    await decline(user)

    await waitFor(() => expect(location()).toBe('/'))
    expect(accepted).toEqual([])
  })

  it('says why a link does not open and leads to the digest page', async () => {
    server.use(
      http.get(sharedUrl, () =>
        HttpResponse.json({ detail: 'Владелец закрыл доступ к профилю' }, { status: 404 }),
      ),
    )
    const { user } = renderLink()

    const dialog = await screen.findByRole('dialog', { name: 'Профиль не открылся' })
    expect(within(dialog).getByText('Владелец закрыл доступ к профилю')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Понятно' }))

    await waitFor(() => expect(location()).toBe('/'))
  })

  it('says a mistyped link does not work instead of the server’s check', async () => {
    server.use(
      http.get(sharedUrl, () =>
        HttpResponse.json(
          { detail: "path.token: String should match pattern '^[A-Za-z0-9_-]{16,32}$'" },
          { status: 422 },
        ),
      ),
    )
    renderLink()

    const dialog = await screen.findByRole('dialog', { name: 'Профиль не открылся' })
    expect(within(dialog).getByText(/в ней ошибка/)).toBeInTheDocument()
    expect(within(dialog).queryByText(/pattern/)).toBeNull()
  })

  it('never shows the previous link’s profile while the next one loads', async () => {
    // The app's own client keeps the previous answer on screen while the next loads.
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: Infinity, placeholderData: keepPreviousData },
      },
    })
    const answer = hold()
    serveLink()
    server.use(
      http.get(apiUrl('/shared-profiles/Zt5mN8vLq3'), async () => {
        await answer.released
        return HttpResponse.json(
          makeSharedProfile({ spec: makeSpec({ name: 'Регуляторика ФСТЭК' }) }),
        )
      }),
    )
    const { rerender } = renderLink({ client })
    await screen.findByRole('dialog', { name: 'Защита подстанций' })

    rerender(<SharedProfileDialog token="Zt5mN8vLq3" />)

    expect(await screen.findByRole('dialog', { name: 'Профиль по ссылке' })).toBeInTheDocument()
    expect(screen.queryByText('Защита подстанций')).toBeNull()
    answer.release()
    expect(await screen.findByRole('dialog', { name: 'Регуляторика ФСТЭК' })).toBeInTheDocument()
  })

  it('remembers a copy already taken when the link is opened again', async () => {
    const shared = makeSharedProfile()
    const reread = hold()
    let reads = 0
    let isReread = false
    server.use(
      http.get(sharedUrl, async () => {
        reads += 1
        if (reads === 1) return HttpResponse.json(shared)
        await reread.released
        isReread = true
        return HttpResponse.json({ ...shared, own_id: 'profile-2' })
      }),
      http.post(acceptUrl, () => HttpResponse.json(makeProfile({ id: 'profile-2' }))),
    )
    const { client, unmount, user } = renderLink()
    const dialog = await screen.findByRole('dialog', { name: 'Защита подстанций' })
    await user.click(within(dialog).getByRole('button', { name: 'Добавить себе' }))
    await waitFor(() => expect(location()).toBe('/?profile=profile-2'))
    unmount()

    // Opened again, the link is read anew; before the answer the copy is already known.
    renderLink({ client })
    const again = await screen.findByRole('dialog', { name: 'Защита подстанций' })
    await waitFor(() => expect(reads).toBe(2))
    expect(within(again).getByText('Такой профиль уже есть у вас.')).toBeInTheDocument()
    expect(within(again).getByRole('button', { name: 'Открыть профиль' })).toBeInTheDocument()

    reread.release()
    await waitFor(() => expect(isReread).toBe(true))
  })
})
