import { createEvent, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { TeamInput } from '../../lib/company'
import { matchesMember } from '../../lib/company'
import { keys } from '../../lib/queries'
import { CompanyPage } from '../../pages/CompanyPage'
import { makeCompany, makeMe, makeMember, makeRole, makeTeam } from '../../test/fixtures'
import { createTestQueryClient, renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'

const ANNA = makeMember({
  id: 'm-anna',
  display_name: 'Анна Смирнова',
  email: 'a.smirnova@energo.example',
  job_title: 'ведущий аналитик',
  role_id: 'role-1',
})
const OLEG = makeMember({
  id: 'm-oleg',
  display_name: 'Олег Петров',
  email: 'o.petrov@energo.example',
  job_title: 'начальник отдела',
})
const FEDOR = makeMember({ id: 'm-fedor', display_name: 'Фёдор Ёлкин', team_id: 'team-2' })
const SOC = makeTeam({ roles: [makeRole()], members: [ANNA, OLEG] })
const NETWORK = makeTeam({ id: 'team-2', name: 'Сети', members: [FEDOR] })

function renderPage() {
  const client = createTestQueryClient()
  client.setQueryData(keys.me, makeMe())
  return renderWithProviders(<CompanyPage />, { route: '/company', client })
}

describe('matchesMember', () => {
  it('finds every word in the name, address, position or role, with е for ё', () => {
    expect(matchesMember(ANNA, 'анна аналитик')).toBe(true)
    expect(matchesMember(ANNA, 'SMIRNOVA')).toBe(true)
    expect(matchesMember(ANNA, 'Аналитик', 'Аналитик')).toBe(true)
    expect(matchesMember(FEDOR, 'федор елкин')).toBe(true)
    expect(matchesMember(OLEG, 'анна')).toBe(false)
    expect(matchesMember(OLEG, '   ')).toBe(true)
  })
})

describe('CompanyPage search and look', () => {
  it('narrows the people as one types and counts the matches of every team', async () => {
    server.use(
      http.get(apiUrl('/company'), () => HttpResponse.json(makeCompany({ teams: [SOC, NETWORK] }))),
    )
    const { user } = renderPage()

    const search = await screen.findByRole('searchbox', { name: 'Поиск по сотрудникам' })
    await user.type(search, 'начальник')

    expect(screen.getByText('Олег Петров')).toBeInTheDocument()
    expect(screen.queryByText('Анна Смирнова')).toBeNull()
    const teams = screen.getByRole('navigation', { name: 'Команды' })
    expect(within(teams).getByRole('heading', { name: '2 команды' })).toBeInTheDocument()
    expect(within(teams).getByText('3 сотрудника, в сервисе 0')).toBeInTheDocument()
    expect(within(teams).getByRole('button', { name: /^SOC.*1$/ })).toBeInTheDocument()
    expect(within(teams).getByRole('button', { name: /^Сети.*0$/ })).toBeInTheDocument()

    await user.clear(search)
    await user.type(search, 'никого такого')
    expect(screen.getByText('Никого не нашли по «никого такого»')).toBeInTheDocument()
  })

  it('shows the other teams as places to drop while a person is dragged', async () => {
    server.use(
      http.get(apiUrl('/company'), () => HttpResponse.json(makeCompany({ teams: [SOC, NETWORK] }))),
    )
    renderPage()

    const row = (await screen.findByText('Олег Петров')).closest('li') as HTMLElement
    const data = { setData: () => {}, setDragImage: () => {}, effectAllowed: 'all', types: [] }
    const start = createEvent.dragStart(row)
    Object.defineProperty(start, 'dataTransfer', { value: data })
    fireEvent(row, start)

    expect(await screen.findByText('Отпустите здесь, чтобы перевести')).toBeInTheDocument()
    fireEvent.dragEnd(row)
    await waitFor(() => expect(screen.queryByText('Отпустите здесь, чтобы перевести')).toBeNull())
  })

  it('gives a team an icon, a colour and a picture of its own', async () => {
    let sent: TeamInput | null = null
    let pictured = false
    server.use(
      http.get(apiUrl('/company'), () => HttpResponse.json(makeCompany({ teams: [SOC] }))),
      http.put(apiUrl('/company/teams/:id'), async ({ request }) => {
        sent = (await request.json()) as TeamInput
        return HttpResponse.json(SOC)
      }),
      http.put(apiUrl('/company/teams/:id/picture'), () => {
        pictured = true
        return HttpResponse.json({
          ...SOC,
          picture_url: '/api/v1/company/teams/team-1/picture?v=1',
        })
      }),
    )
    const { user } = renderPage()

    await user.click(await screen.findByRole('button', { name: 'Изменить' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('radio', { name: 'Уязвимости' }))
    await user.click(within(dialog).getByRole('radio', { name: 'Бирюзовый' }))
    const file = new File([new Uint8Array([137, 80, 78, 71])], 'team.png', { type: 'image/png' })
    await user.upload(within(dialog).getByLabelText('Файл картинки команды'), file)
    await waitFor(() => expect(pictured).toBe(true))
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))

    await waitFor(() => expect(sent).not.toBeNull())
    expect(sent).toMatchObject({ icon: 'bug', color: 'teal' })
  })
})
