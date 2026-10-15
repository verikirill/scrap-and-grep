import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { keys } from '../../lib/queries'
import { CompanyPage } from '../../pages/CompanyPage'
import {
  makeCompany,
  makeInterests,
  makeMe,
  makeMember,
  makeRole,
  makeSpec,
  makeTeam,
} from '../../test/fixtures'
import { createTestQueryClient, renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'

const BORIS = makeMember({
  id: 'm-boris',
  display_name: 'Борис Лин',
  overrides: 2,
  status: 'expired',
  invite_path: null,
})
const VERA = makeMember({
  id: 'm-vera',
  display_name: 'Вера Ким',
  status: 'active',
  invite_path: null,
  last_login_at: '2026-10-16T08:00:00Z',
})
const SOC = makeTeam({ roles: [makeRole()], members: [BORIS, VERA] })
const NETWORK = makeTeam({
  id: 'team-2',
  name: 'Сети',
  roles: [makeRole({ id: 'role-9', name: 'Инженер сетей' })],
})

type Call = { method: string; path: string; body?: unknown }

function serve() {
  const calls: Call[] = []
  const record = async (method: string, path: string, request: Request) => {
    const text = await request.text()
    calls.push({ method, path, body: text ? JSON.parse(text) : undefined })
  }
  server.use(
    http.get(apiUrl('/company'), () => HttpResponse.json(makeCompany({ teams: [SOC, NETWORK] }))),
    http.patch(apiUrl('/company/members/:id'), async ({ request, params }) => {
      await record('PATCH', `/members/${String(params.id)}`, request)
      return HttpResponse.json(BORIS)
    }),
    http.post(apiUrl('/company/members/:id/invite'), async ({ request, params }) => {
      await record('POST', `/members/${String(params.id)}/invite`, request)
      return HttpResponse.json({
        ...BORIS,
        status: 'invited',
        invite_path: '/invite/renewed-000000000000000000000',
      })
    }),
    http.delete(apiUrl('/company/members/:id/overrides'), async ({ request, params }) => {
      await record('DELETE', `/members/${String(params.id)}/overrides`, request)
      return HttpResponse.json({ ...BORIS, overrides: 0 })
    }),
    http.delete(apiUrl('/company/members/:id'), async ({ request, params }) => {
      await record('DELETE', `/members/${String(params.id)}`, request)
      return new HttpResponse(null, { status: 204 })
    }),
    http.post(apiUrl('/company/teams/:id/roles/draft'), async ({ request }) => {
      await record('POST', '/roles/draft', request)
      return HttpResponse.json({
        spec: makeSpec({ name: 'SOC: Руководитель', interests: makeInterests(2) }),
        icon: 'shield',
        drafted_by: 'taxonomy',
      })
    }),
    http.post(apiUrl('/company/teams/:id/roles'), async ({ request }) => {
      await record('POST', '/roles', request)
      return HttpResponse.json(makeRole({ id: 'role-3', name: 'Руководитель' }), { status: 201 })
    }),
    http.put(apiUrl('/company/teams/:id/roles/:role'), async ({ request }) => {
      await record('PUT', '/roles/role-1', request)
      return HttpResponse.json(makeRole())
    }),
    http.delete(apiUrl('/company/teams/:id/roles/:role'), async ({ request }) => {
      await record('DELETE', '/roles/role-1', request)
      return new HttpResponse(null, { status: 204 })
    }),
    http.delete(apiUrl('/company/teams/:id'), async ({ request, params }) => {
      await record('DELETE', `/teams/${String(params.id)}`, request)
      return new HttpResponse(null, { status: 204 })
    }),
    http.patch(apiUrl('/company'), async ({ request }) => {
      await record('PATCH', '/company', request)
      return HttpResponse.json(makeCompany({ name: 'Энергосеть-2', teams: [SOC, NETWORK] }))
    }),
  )
  return calls
}

function renderPage(route = '/company') {
  const client = createTestQueryClient()
  client.setQueryData(keys.me, makeMe())
  return renderWithProviders(<CompanyPage />, { route, client })
}

const memberDialog = async (name: string) => {
  return screen.findByRole('dialog', { name })
}

describe('MemberList', () => {
  it('moves a person to another team with its role and a new position', async () => {
    const calls = serve()
    const { user } = renderPage()

    await user.click(await screen.findByRole('button', { name: 'Изменить: Борис Лин' }))
    const dialog = await memberDialog('Борис Лин')
    await user.clear(within(dialog).getByLabelText(/^Должность/))
    await user.type(within(dialog).getByLabelText(/^Должность/), 'инженер сетей')
    await user.click(within(dialog).getByRole('button', { name: /Команда: SOC/ }))
    await user.click(await screen.findByRole('option', { name: 'Сети' }))
    await user.click(within(dialog).getByRole('button', { name: /Роль в команде: По должности/ }))
    await user.click(await screen.findByRole('option', { name: 'Инженер сетей' }))
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))

    await waitFor(() =>
      expect(calls).toContainEqual({
        method: 'PATCH',
        path: '/members/m-boris',
        body: { job_title: 'инженер сетей', team_id: 'team-2', role_id: 'role-9' },
      }),
    )
  })

  it('drops the personal changes, renews an old link and copies it, and removes the account', async () => {
    const calls = serve()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { user } = renderPage()

    await user.click(await screen.findByRole('button', { name: 'Изменить: Борис Лин' }))
    let dialog = await memberDialog('Борис Лин')
    await user.click(within(dialog).getByRole('button', { name: 'Сбросить личные правки (2)' }))
    await user.click(within(dialog).getByRole('button', { name: 'Новая ссылка' }))
    await waitFor(async () =>
      expect(await navigator.clipboard.readText()).toBe(
        `${window.location.origin}/invite/renewed-000000000000000000000`,
      ),
    )
    dialog = await memberDialog('Борис Лин')
    await user.click(within(dialog).getByRole('button', { name: 'Удалить аккаунт' }))

    await waitFor(() =>
      expect(calls.map((call) => `${call.method} ${call.path}`)).toEqual([
        'DELETE /members/m-boris/overrides',
        'POST /members/m-boris/invite',
        'DELETE /members/m-boris',
      ]),
    )
    expect(confirm).toHaveBeenCalled()
    confirm.mockRestore()
  })

  it('names who came in and whose link expired', async () => {
    serve()
    renderPage()

    expect(await screen.findByText('Ссылка устарела')).toBeInTheDocument()
    expect(screen.getByText('В сервисе')).toHaveAttribute(
      'title',
      expect.stringContaining('Последний вход'),
    )
    expect(screen.getByText('2 свои правки')).toBeInTheDocument()
  })
})

describe('Roles', () => {
  it('drafts a new role from its description and adds a topic of the manager', async () => {
    const calls = serve()
    const { user } = renderPage()

    await user.click(await screen.findByRole('button', { name: 'Новая роль' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText(/Название роли/), 'Руководитель')
    await user.type(within(dialog).getByLabelText(/Чем роль отличается/), 'Читает о рисках')
    await user.click(within(dialog).getByRole('button', { name: 'Подобрать темы' }))
    expect(
      await within(dialog).findByText('Подобран по справочнику направлений'),
    ).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Добавить тему' }))
    await user.type(within(dialog).getByLabelText('Тема'), 'Штрафы регуляторов')
    await user.click(within(dialog).getByRole('textbox', { name: 'Ключевые слова' }))
    await user.keyboard('ФСТЭК{Enter}')
    await user.click(within(dialog).getByRole('button', { name: 'Добавить' }))
    await user.click(within(dialog).getByRole('button', { name: 'Добавить роль' }))

    await waitFor(() => expect(calls.some((call) => call.path === '/roles')).toBe(true))
    const sent = calls.find((call) => call.path === '/roles')?.body as {
      name: string
      description: string
      spec: { interests: { title: string; keywords: string[] }[] }
    }
    expect(calls[0]).toEqual({
      method: 'POST',
      path: '/roles/draft',
      body: { name: 'Руководитель', description: 'Читает о рисках' },
    })
    expect(sent.name).toBe('Руководитель')
    expect(sent.spec.interests.at(-1)).toMatchObject({
      title: 'Штрафы регуляторов',
      keywords: ['ФСТЭК'],
    })
  })

  it('renames a role and deletes it after asking', async () => {
    const calls = serve()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { user } = renderPage()

    await user.click(await screen.findByRole('button', { name: 'Изменить роль «Аналитик»' }))
    const dialog = await screen.findByRole('dialog')
    await user.clear(within(dialog).getByLabelText(/Название роли/))
    await user.type(within(dialog).getByLabelText(/Название роли/), 'Аналитик угроз')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(calls.some((call) => call.method === 'PUT')).toBe(true))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    await user.click(screen.getByRole('button', { name: 'Удалить роль «Аналитик»' }))

    await waitFor(() =>
      expect(calls.some((call) => call.path === '/roles/role-1' && call.method === 'DELETE')).toBe(
        true,
      ),
    )
    expect((calls.find((call) => call.method === 'PUT')?.body as { name: string }).name).toBe(
      'Аналитик угроз',
    )
    confirm.mockRestore()
  })
})

describe('Company and teams', () => {
  it('renames the company and deletes an empty team', async () => {
    const calls = serve()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { user } = renderPage('/company?team=team-2')

    await user.click(await screen.findByRole('button', { name: 'О компании' }))
    const dialog = await screen.findByRole('dialog')
    await user.clear(within(dialog).getByLabelText('Название компании'))
    await user.type(within(dialog).getByLabelText('Название компании'), 'Энергосеть-2')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    await user.click(await screen.findByRole('button', { name: 'Удалить' }))

    await waitFor(() =>
      expect(calls.map((call) => `${call.method} ${call.path}`)).toEqual([
        'PATCH /company',
        'DELETE /teams/team-2',
      ]),
    )
    expect(calls[0].body).toEqual({
      name: 'Энергосеть-2',
      about: 'Распределение электроэнергии в трёх регионах.',
    })
    confirm.mockRestore()
  })

  it('says the space did not load and tries again', async () => {
    server.use(
      http.get(apiUrl('/company'), () => HttpResponse.json({ detail: 'нет' }, { status: 500 })),
    )
    renderPage()

    expect(await screen.findByText('Пространство не загрузилось')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeInTheDocument()
  })
})
