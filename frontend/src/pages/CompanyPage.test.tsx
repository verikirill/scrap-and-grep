import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Company, PersonInput, TeamInput } from '../lib/company'
import { keys } from '../lib/queries'
import {
  makeCompany,
  makeInterests,
  makeMe,
  makeMember,
  makeSpec,
  makeTeam,
} from '../test/fixtures'
import { createTestQueryClient, renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { CompanyPage } from './CompanyPage'

/** The space as the server keeps it: what a request changes, the next read returns. */
function serveCompany(initial: Company | null) {
  let stored = initial
  const sent: { team?: TeamInput; people?: PersonInput[]; company?: unknown } = {}
  server.use(
    http.get(apiUrl('/company'), () => HttpResponse.json(stored)),
    http.post(apiUrl('/company'), async ({ request }) => {
      sent.company = await request.json()
      stored = makeCompany({ ...(sent.company as object), teams: [] })
      return HttpResponse.json(stored, { status: 201 })
    }),
    http.post(apiUrl('/company/teams/draft'), () =>
      HttpResponse.json({
        spec: makeSpec({
          name: 'SOC',
          role: 'Команда SOC ведёт мониторинг.',
          interests: makeInterests(2),
          systems: ['MaxPatrol SIEM', 'Kaspersky EDR'],
        }),
        icon: 'shield',
        drafted_by: 'qwen3.6',
      }),
    ),
    http.post(apiUrl('/company/teams'), async ({ request }) => {
      sent.team = (await request.json()) as TeamInput
      const team = makeTeam({ id: 'team-new', name: sent.team.name, spec: sent.team.spec })
      stored = { ...(stored ?? makeCompany()), teams: [...(stored?.teams ?? []), team] }
      return HttpResponse.json(team, { status: 201 })
    }),
    http.post(apiUrl('/company/teams/:id/members'), async ({ request }) => {
      sent.people = ((await request.json()) as { people: PersonInput[] }).people
      return HttpResponse.json(
        {
          created: sent.people.map((person, index) =>
            makeMember({
              id: `member-${index + 10}`,
              display_name: person.name,
              email: person.email,
              invite_path: `/invite/new-link-${index}-000000000000000000`,
            }),
          ),
          skipped: [{ email: 'taken@energo.example', reason: 'С этой почтой уже есть аккаунт.' }],
        },
        { status: 201 },
      )
    }),
  )
  return sent
}

function renderPage(client = createTestQueryClient()) {
  client.setQueryData(keys.me, makeMe())
  return renderWithProviders(<CompanyPage />, { route: '/company', client })
}

describe('CompanyPage', () => {
  it('makes a space from the first screen and then asks for the first team', async () => {
    const sent = serveCompany(null)
    const { user } = renderPage()

    await user.type(await screen.findByLabelText('Название компании'), 'Энергосеть')
    await user.click(screen.getByRole('button', { name: 'Создать пространство' }))

    expect(await screen.findByText('Добавьте первую команду')).toBeInTheDocument()
    expect(sent.company).toEqual({ name: 'Энергосеть', about: '' })
  })

  it('drafts a team profile from the description and saves what the manager kept', async () => {
    const sent = serveCompany(makeCompany())
    const { user } = renderPage()

    // The header's button; the empty space offers the same one.
    await user.click((await screen.findAllByRole('button', { name: 'Новая команда' }))[0])
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Название'), 'SOC')
    await user.type(
      within(dialog).getByLabelText(/Чем занимается команда/),
      'Мониторинг в MaxPatrol SIEM',
    )
    expect(within(dialog).getByRole('button', { name: 'Создать команду' })).toBeDisabled()
    await user.click(within(dialog).getByRole('button', { name: 'Подобрать интересы' }))

    expect(await within(dialog).findByText('Подобран моделью по описанию')).toBeInTheDocument()
    // The product the model found joins the manager's list.
    expect(within(dialog).getByText('Kaspersky EDR')).toBeInTheDocument()
    const [first, second] = makeInterests(2)
    await user.click(within(dialog).getByRole('button', { name: `Убрать тему «${first.title}»` }))
    await user.click(within(dialog).getByRole('button', { name: 'Создать команду' }))

    await waitFor(() => expect(sent.team).toBeDefined())
    expect(sent.team?.spec.interests.map((interest) => interest.title)).toEqual([second.title])
    expect(sent.team?.systems).toEqual(['MaxPatrol SIEM', 'Kaspersky EDR'])
    expect(sent.team?.spec.role).toBe('Команда SOC ведёт мониторинг.')
    expect(await screen.findByRole('heading', { name: 'SOC' })).toBeInTheDocument()
  })

  it('shows who came in and copies the links of those still invited', async () => {
    serveCompany(
      makeCompany({
        teams: [
          makeTeam({
            members: [
              makeMember(),
              makeMember({
                id: 'member-2',
                display_name: 'Вера Ким',
                invite_path: '/invite/vera-link-000000000000000000000',
              }),
              makeMember({
                id: 'member-3',
                display_name: 'Лев Орлов',
                job_title: 'Начальник SOC',
                audience: 'management',
                status: 'active',
                invite_path: null,
              }),
            ],
          }),
        ],
      }),
    )
    const { user } = renderPage()

    expect(await screen.findByText('В сервисе')).toBeInTheDocument()
    expect(screen.getAllByText('Ждёт входа')).toHaveLength(2)
    expect(screen.getByText('брифинг')).toBeInTheDocument()
    expect(screen.getByText('3 сотрудника, 2 ждут входа')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Скопировать приглашение для Вера Ким' }))
    expect(await navigator.clipboard.readText()).toBe(
      `${window.location.origin}/invite/vera-link-000000000000000000000`,
    )
    await user.click(screen.getByRole('button', { name: 'Скопировать 2 приглашения' }))
    expect(await navigator.clipboard.readText()).toBe(
      [
        `Олег Смирнов: ${window.location.origin}/invite/oleg-link-0000000000000000000`,
        `Вера Ким: ${window.location.origin}/invite/vera-link-000000000000000000000`,
      ].join('\n'),
    )
  })

  it('reads a pasted list before adding anyone, then hands out the links', async () => {
    const sent = serveCompany(makeCompany({ teams: [makeTeam()] }))
    const { user } = renderPage()

    await user.click(await screen.findByRole('button', { name: 'Добавить сотрудников' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByLabelText(/Список сотрудников/))
    await user.paste(
      [
        'Анна Смирнова, anna@energo.example, ведущий инженер',
        'Пётр без почты',
        'Борис\tboris@energo.example\tначальник отдела',
      ].join('\n'),
    )

    expect(within(dialog).getByText('Нет почты')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Добавить 2 сотрудников' }))

    expect(await within(dialog).findByText('Аккаунты готовы: 2')).toBeInTheDocument()
    expect(sent.people).toEqual([
      { name: 'Анна Смирнова', email: 'anna@energo.example', job_title: 'ведущий инженер' },
      { name: 'Борис', email: 'boris@energo.example', job_title: 'начальник отдела' },
    ])
    expect(within(dialog).getByText('С этой почтой уже есть аккаунт.')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Скопировать все приглашения' }))
    expect(await navigator.clipboard.readText()).toContain(
      `Анна Смирнова: ${window.location.origin}/invite/new-link-0-`,
    )
  })
})
