import { createEvent, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Company } from '../../lib/company'
import { keys } from '../../lib/queries'
import { CompanyPage } from '../../pages/CompanyPage'
import {
  makeCompany,
  makeInterests,
  makeMe,
  makeMember,
  makeRole,
  makeTeam,
} from '../../test/fixtures'
import { createTestQueryClient, renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { DRAG_TYPE } from './drag'

const ANNA = makeMember({ id: 'm-anna', display_name: 'Анна Ким', role_id: 'role-1' })
const BORIS = makeMember({ id: 'm-boris', display_name: 'Борис Лин', overrides: 2 })
const SOC = makeTeam({ roles: [makeRole()], members: [ANNA, BORIS] })
const NETWORK = makeTeam({ id: 'team-2', name: 'Сети', icon: 'network', color: 'teal' })

function serve(company: Company = makeCompany({ teams: [SOC, NETWORK] })) {
  const sent: { patch?: unknown; move?: unknown; role?: unknown } = {}
  server.use(
    http.get(apiUrl('/company'), () => HttpResponse.json(company)),
    http.post(apiUrl('/company/teams/:id/patch'), async ({ request }) => {
      sent.patch = await request.json()
      return HttpResponse.json({ changed: 1 })
    }),
    http.post(apiUrl('/company/members/move'), async ({ request }) => {
      sent.move = await request.json()
      return HttpResponse.json([{ ...BORIS, team_id: 'team-2' }])
    }),
    http.post(apiUrl('/company/teams/:id/roles'), async ({ request }) => {
      sent.role = await request.json()
      return HttpResponse.json(makeRole({ id: 'role-2', name: 'Инженер' }), { status: 201 })
    }),
  )
  return sent
}

function renderPage() {
  const client = createTestQueryClient()
  client.setQueryData(keys.me, makeMe())
  return renderWithProviders(<CompanyPage />, { route: '/company', client })
}

/** A DataTransfer of jsdom's events: it has none, so a small one stands in. */
function transfer() {
  const data = new Map<string, string>()
  return {
    types: [] as string[],
    dropEffect: 'none',
    effectAllowed: 'all',
    setData(type: string, value: string) {
      data.set(type, value)
      this.types.push(type)
    },
    getData: (type: string) => data.get(type) ?? '',
  }
}

describe('TeamPanel', () => {
  it('shows each role with its people and the personal changes of a member', async () => {
    serve()
    renderPage()

    const roles = await screen.findByRole('list', { name: 'Роли' })
    expect(within(roles).getByText('Аналитик')).toBeInTheDocument()
    expect(within(roles).getByText('1 сотрудник')).toBeInTheDocument()
    // Anna's row names her role; Boris carries his own changes.
    expect(screen.getAllByText('Аналитик')).toHaveLength(2)
    expect(screen.getByText('2 свои правки')).toBeInTheDocument()
  })

  it('sends one change to the people ticked in the list', async () => {
    const sent = serve()
    const { user } = renderPage()

    await user.click(await screen.findByRole('checkbox', { name: 'Выбрать: Борис Лин' }))
    const bar = screen.getByRole('region', { name: 'Выбранные сотрудники' })
    expect(within(bar).getByText('Выбрано: 1')).toBeInTheDocument()
    await user.click(within(bar).getByRole('button', { name: 'Изменить профили' }))

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('radio', { name: 'Выбранные: 1' })).toBeChecked()
    const [first] = makeInterests(2)
    await user.click(within(dialog).getByRole('button', { name: first.title }))
    await user.click(within(dialog).getByRole('radio', { name: 'Брифинг' }))
    await user.click(within(dialog).getByRole('button', { name: 'Применить' }))

    await waitFor(() =>
      expect(sent.patch).toEqual({
        scope: 'people',
        member_ids: ['m-boris'],
        patch: { remove_interests: [first.title], audience: 'management' },
      }),
    )
  })

  it('opens the change on a role from the role card', async () => {
    const sent = serve()
    const { user } = renderPage()

    await user.click(await screen.findByRole('button', { name: 'Изменить профили роли' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('radio', { name: 'Роль' })).toBeChecked()
    await user.click(within(dialog).getByRole('textbox', { name: 'Исключить из выдачи' }))
    await user.keyboard('реклама{Enter}')
    await user.click(within(dialog).getByRole('button', { name: 'Применить' }))

    await waitFor(() =>
      expect(sent.patch).toEqual({
        scope: 'role',
        role_id: 'role-1',
        patch: { add_exclusions: ['реклама'] },
      }),
    )
  })

  it('makes a role from the team profile', async () => {
    const sent = serve()
    const { user } = renderPage()

    await user.click(await screen.findByRole('button', { name: 'Новая роль' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText(/Название роли/), 'Инженер')
    await user.click(within(dialog).getByRole('button', { name: 'Начать с профиля команды' }))
    await user.click(within(dialog).getByRole('radio', { name: 'Брифинг руководителя' }))
    await user.click(within(dialog).getByRole('button', { name: 'Добавить роль' }))

    await waitFor(() => expect(sent.role).toBeDefined())
    const role = sent.role as { name: string; spec: { name: string; audience: string } }
    expect(role.name).toBe('Инженер')
    expect(role.spec.name).toBe('SOC: Инженер')
    expect(role.spec.audience).toBe('management')
  })

  it('moves a dragged member to the team it is dropped on', async () => {
    const sent = serve()
    renderPage()

    const row = (await screen.findByText('Борис Лин')).closest('li') as HTMLElement
    const target = screen.getByRole('button', { name: /^Сети/ })
    const data = transfer()
    const start = createEvent.dragStart(row)
    Object.defineProperty(start, 'dataTransfer', { value: data })
    fireEvent(row, start)
    expect(data.types).toEqual([DRAG_TYPE])
    for (const make of [createEvent.dragOver, createEvent.drop]) {
      const event = make(target)
      Object.defineProperty(event, 'dataTransfer', { value: data })
      fireEvent(target, event)
    }

    await waitFor(() => expect(sent.move).toEqual({ member_ids: ['m-boris'], team_id: 'team-2' }))
    expect(await screen.findByText('Борис Лин теперь в «Сети»')).toBeInTheDocument()
  })
})
