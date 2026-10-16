import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { Profile, ProfileSpec } from '../lib/api'
import {
  makeAdaptation,
  makeInterest,
  makeMe,
  makePreview,
  makeProfile,
  makeSpec,
  makeSuggestion,
} from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { ProfilesPage } from './ProfilesPage'

const engineer = makeProfile()
const manager = makeProfile({
  id: 'profile-2',
  spec: makeSpec({ name: 'Руководитель ИБ', audience: 'management' }),
})

type Sent = { method: string; path: string; body?: ProfileSpec }

/** The profiles as the server keeps them: what is saved or deleted is there on the next read. */
function serveProfiles(initial: Profile[] = [engineer, manager]) {
  let profiles = initial
  const sent: Sent[] = []
  server.use(
    http.get(apiUrl('/profiles'), () => HttpResponse.json(profiles)),
    http.post(apiUrl('/profiles'), async ({ request }) => {
      const body = (await request.json()) as ProfileSpec
      sent.push({ method: 'POST', path: '/profiles', body })
      const created = makeProfile({ id: 'profile-3', spec: body })
      profiles = [...profiles, created]
      return HttpResponse.json(created)
    }),
    http.put(apiUrl('/profiles/:id'), async ({ params, request }) => {
      const body = (await request.json()) as ProfileSpec
      sent.push({ method: 'PUT', path: `/profiles/${String(params.id)}`, body })
      const old = profiles.find((profile) => profile.id === params.id) as Profile
      const updated = { ...old, version: old.version + 1, spec: body }
      profiles = profiles.map((profile) => (profile.id === params.id ? updated : profile))
      return HttpResponse.json(updated)
    }),
    http.delete(apiUrl('/profiles/:id'), ({ params }) => {
      sent.push({ method: 'DELETE', path: `/profiles/${String(params.id)}` })
      profiles = profiles.filter((profile) => profile.id !== params.id)
      return new HttpResponse(null, { status: 204 })
    }),
    http.get(apiUrl('/profiles/:id/adaptation'), () =>
      HttpResponse.json(makeAdaptation({ adaptive: false, interests: [], suggestions: [] })),
    ),
    http.post(apiUrl('/selection/preview'), () => HttpResponse.json(makePreview())),
  )
  return sent
}

const nameField = () => screen.getByRole('textbox', { name: /^Название профиля/ })
const unsavedBar = () => screen.queryByRole('region', { name: 'Несохранённые правки' })
const headerSave = () => screen.getAllByRole('button', { name: 'Сохранить' })[0]
const tab = (name: string) => screen.getByRole('button', { name: new RegExp(`${name}$`) })

async function renderPage() {
  const result = renderWithProviders(<ProfilesPage />)
  await waitFor(() => expect(nameField()).toHaveValue('Инженер АСУ ТП'))
  // The preview is the last part of the screen to arrive.
  await screen.findByText(/из 40 кандидатов/)
  return result
}

async function rename(user: UserEvent, name: string) {
  await user.clear(nameField())
  await user.type(nameField(), name)
}

describe('ProfilesPage', () => {
  it('says a team profile follows the team until the reader saves an edit of their own', async () => {
    serveProfiles([makeProfile({ team_id: 'team-1' })])
    server.use(
      http.get(apiUrl('/auth/me'), () =>
        HttpResponse.json(
          makeMe({
            company: {
              company: 'Энергосеть',
              team: 'SOC',
              role: 'member',
              job_title: 'Инженер SOC',
              manager: 'Олег',
            },
          }),
        ),
      ),
    )
    const { user } = await renderPage()

    expect(await screen.findByText('Профиль команды «SOC».')).toBeInTheDocument()
    expect(screen.getByText(/изменения команды приходят сюда сами/)).toBeInTheDocument()
    await rename(user, 'Мой SOC')
    expect(screen.getByText(/перестанет обновляться вместе с командой/)).toBeInTheDocument()
  })

  it('opens the first profile and saves an edit as its new version', async () => {
    const sent = serveProfiles()
    const { user } = await renderPage()
    expect(tab('Инженер АСУ ТП')).toHaveAttribute('aria-current', 'true')
    expect(headerSave()).toBeDisabled()
    expect(unsavedBar()).toBeNull()

    await rename(user, 'Инженер РЗА')

    expect(within(unsavedBar() as HTMLElement).getByText('Правки не сохранены')).toBeInTheDocument()
    await user.click(headerSave())

    await waitFor(() => expect(unsavedBar()).toBeNull())
    expect(headerSave()).toBeDisabled()
    expect(tab('Инженер РЗА')).toHaveAttribute('aria-current', 'true')
    expect(sent).toEqual([
      {
        method: 'PUT',
        path: '/profiles/profile-1',
        body: { ...engineer.spec, name: 'Инженер РЗА' },
      },
    ])
  })

  it('blocks saving what the server would reject and says why', async () => {
    serveProfiles()
    const { user } = await renderPage()

    await rename(user, 'И')

    const bar = unsavedBar() as HTMLElement
    expect(within(bar).getByText('Дайте профилю название.')).toBeInTheDocument()
    expect(within(bar).getByRole('button', { name: 'Сохранить' })).toBeDisabled()
    expect(headerSave()).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Сохранить и собрать' })).toBeDisabled()
  })

  it('takes unsaved edits back', async () => {
    serveProfiles()
    const { user } = await renderPage()
    await rename(user, 'Инженер РЗА')

    await user.click(screen.getByRole('button', { name: 'Отменить правки' }))

    expect(nameField()).toHaveValue('Инженер АСУ ТП')
    await waitFor(() => expect(unsavedBar()).toBeNull())
  })

  it('saves an edit before building an issue of the profile', async () => {
    const sent = serveProfiles()
    const { user } = await renderPage()
    await rename(user, 'Инженер РЗА')

    await user.click(screen.getByRole('button', { name: 'Сохранить и собрать' }))

    await waitFor(() =>
      expect(screen.getByTestId('location')).toHaveTextContent('/?profile=profile-1'),
    )
    expect(sent.map((request) => request.method)).toEqual(['PUT'])
  })

  it('builds an issue of an unchanged profile without saving it', async () => {
    const sent = serveProfiles()
    const { user } = await renderPage()

    await user.click(screen.getByRole('button', { name: 'Собрать выпуск' }))

    expect(screen.getByTestId('location')).toHaveTextContent('/?profile=profile-1')
    expect(sent).toEqual([])
  })

  it('creates a new profile once every interest has a name', async () => {
    const sent = serveProfiles()
    const { user } = await renderPage()

    await user.click(screen.getByRole('button', { name: 'Новый' }))

    expect(nameField()).toHaveValue('Новый профиль')
    expect(screen.getByRole('button', { name: 'Новый' })).toBeDisabled()
    expect(
      within(unsavedBar() as HTMLElement).getByText('У каждого интереса должно быть название.'),
    ).toBeInTheDocument()
    // A profile that is not saved yet has nothing to take back, adapt or delete.
    expect(screen.queryByRole('button', { name: 'Отменить правки' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Удалить профиль' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Подстройка по отметкам' })).toBeNull()
    await user.click(screen.getByRole('button', { name: /^Новый интерес/ }))
    await user.type(screen.getByRole('textbox', { name: /^Название$/ }), 'Подстанции')
    await user.click(headerSave())

    await waitFor(() => expect(tab('Новый профиль')).toHaveAttribute('aria-current', 'true'))
    expect(sent).toEqual([
      {
        method: 'POST',
        path: '/profiles',
        body: {
          name: 'Новый профиль',
          role: '',
          interests: [
            { id: 'interest-1', title: 'Подстанции', description: '', keywords: [], weight: 1 },
          ],
          exclusions: [],
          min_score: 0.5,
          max_items: 20,
          languages: ['ru', 'en'],
          categories: [],
          audience: 'specialist',
        },
      },
    ])
    await screen.findByRole('region', { name: 'Подстройка по отметкам' })
  })

  it('asks before dropping unsaved edits for another profile', async () => {
    serveProfiles()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const { user } = await renderPage()
    await rename(user, 'Инженер РЗА')

    await user.click(tab('Руководитель ИБ'))

    expect(confirm).toHaveBeenLastCalledWith('Несохранённые правки пропадут. Перейти?')
    expect(nameField()).toHaveValue('Инженер РЗА')

    await user.click(tab('Руководитель ИБ'))

    expect(nameField()).toHaveValue('Руководитель ИБ')
    expect(unsavedBar()).toBeNull()
    await screen.findByText(/^За неделю/)
    await screen.findByText(/из 40 кандидатов/)
  })

  it('deletes a profile after confirmation and opens the next one', async () => {
    const sent = serveProfiles()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { user } = await renderPage()

    await user.click(screen.getByRole('button', { name: 'Удалить профиль' }))

    expect(confirm).toHaveBeenCalledWith('Удалить профиль «Инженер АСУ ТП»?')
    await waitFor(() => expect(nameField()).toHaveValue('Руководитель ИБ'))
    expect(screen.queryByRole('button', { name: /Инженер АСУ ТП$/ })).toBeNull()
    // The last profile cannot be deleted.
    expect(screen.queryByRole('button', { name: 'Удалить профиль' })).toBeNull()
    expect(sent).toEqual([{ method: 'DELETE', path: '/profiles/profile-1' }])
    await screen.findByText(/из 40 кандидатов/)
  })

  it('keeps edits in progress when a suggestion is accepted', async () => {
    serveProfiles([engineer])
    const suggestion = makeSuggestion()
    const added = makeInterest({ id: 'interest-7', title: 'ВИЭ-генерация', keywords: ['инвертор'] })
    server.use(
      http.get(apiUrl('/profiles/profile-1/adaptation'), () =>
        HttpResponse.json(makeAdaptation({ suggestions: [suggestion] })),
      ),
      http.post(apiUrl(`/profiles/profile-1/suggestions/${suggestion.id}/accept`), () =>
        HttpResponse.json(
          makeProfile({
            version: 2,
            spec: { ...engineer.spec, interests: [...engineer.spec.interests, added] },
          }),
        ),
      ),
    )
    const { user } = await renderPage()
    await rename(user, 'Инженер РЗА')

    await user.click(
      await screen.findByRole('button', { name: /^Добавить тему «Безопасность ВИЭ-генерации»/ }),
    )

    expect(await screen.findByRole('button', { name: /^ВИЭ-генерация/ })).toBeInTheDocument()
    expect(nameField()).toHaveValue('Инженер РЗА')
    expect(within(unsavedBar() as HTMLElement).getByText('Правки не сохранены')).toBeInTheDocument()
    await screen.findByText(/добавлена в профиль/)
  })

  it('shows why the profiles could not be loaded', async () => {
    server.use(
      http.get(apiUrl('/profiles'), () =>
        HttpResponse.json({ detail: 'База профилей недоступна' }, { status: 503 }),
      ),
    )
    renderWithProviders(<ProfilesPage />)

    expect(await screen.findByRole('alert')).toHaveTextContent('База профилей недоступна')
  })
})
