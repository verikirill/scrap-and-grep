import { screen, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Me, Profile, ProfileSpec } from '../lib/api'
import {
  makeInterests,
  makeMe,
  makeProfile,
  makeProfileTemplate,
  makeResume,
  makeSpec,
  makeSummary,
} from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { OnboardingPage } from './OnboardingPage'

const TEMPLATES = [
  makeProfileTemplate(),
  makeProfileTemplate({
    spec: makeSpec({ name: 'Руководитель ИТ-инфраструктуры', interests: makeInterests(2) }),
    icon: 'servers',
    color: 'blue',
  }),
]

/** The server as a new reader meets it: no profiles yet, not introduced yet. */
function serveNewReader({ me = makeMe({ onboarded_at: null }), profiles = [] as Profile[] } = {}) {
  const sent = {
    marks: 0,
    profiles: [] as ProfileSpec[],
    looks: [] as unknown[],
    digests: [] as unknown[],
  }
  let current: Me = me
  server.use(
    http.get(apiUrl('/auth/me'), () => HttpResponse.json(current)),
    http.get(apiUrl('/profiles'), () => HttpResponse.json(profiles)),
    http.get(apiUrl('/profile-templates'), () => HttpResponse.json(TEMPLATES)),
    http.post(apiUrl('/auth/me/onboarded'), () => {
      sent.marks += 1
      current = { ...current, onboarded_at: current.onboarded_at ?? '2026-10-15T09:00:00Z' }
      return HttpResponse.json({ onboarded_at: current.onboarded_at })
    }),
    http.post(apiUrl('/profiles'), async ({ request }) => {
      const spec = (await request.json()) as ProfileSpec
      sent.profiles.push(spec)
      return HttpResponse.json(makeProfile({ id: 'profile-new', spec }), { status: 201 })
    }),
    http.patch(apiUrl('/profiles/profile-new/look'), async ({ request }) => {
      const look = (await request.json()) as Pick<Profile, 'icon' | 'color'>
      sent.looks.push(look)
      return HttpResponse.json(makeProfile({ id: 'profile-new', spec: sent.profiles[0], ...look }))
    }),
    http.post(apiUrl('/digests'), async ({ request }) => {
      sent.digests.push(await request.json())
      return HttpResponse.json(makeSummary({ id: 'digest-new', status: 'queued' }))
    }),
  )
  return sent
}

function renderOnboarding() {
  return renderWithProviders(<OnboardingPage />, { route: '/start' })
}

const location = () => screen.getByTestId('location').textContent

describe('OnboardingPage', () => {
  it('takes a new reader from the greeting through a template to the first digest', async () => {
    const sent = serveNewReader()
    const { user } = renderOnboarding()

    expect(
      // The name arrives with the account: under a full run that may take a while.
      await screen.findByRole(
        'heading',
        { level: 1, name: 'Здравствуйте, Анна Петрова' },
        { timeout: 5000 },
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(/Шаг 1 из 3/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Начать' }))

    expect(screen.getByRole('heading', { name: 'Первый профиль интересов' })).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: /Готовый шаблон/ }))
    const take = await screen.findByRole('button', { name: 'Взять этот шаблон' })
    expect(take).toBeDisabled()
    await user.click(screen.getByRole('radio', { name: /Руководитель ИТ-инфраструктуры/ }))
    await user.click(take)

    expect(await screen.findByRole('heading', { name: 'Первый выпуск' })).toBeInTheDocument()
    // The period follows the profile's audience: a specialist reads the last day.
    expect(screen.getByText(/за последние сутки/)).toBeInTheDocument()
    expect(sent.profiles).toEqual([TEMPLATES[1].spec])
    expect(sent.looks).toEqual([{ icon: 'servers', color: 'blue' }])
    // Nothing is marked yet: the reader may still close the tab and come back to it.
    expect(sent.marks).toBe(0)

    await user.click(screen.getByRole('button', { name: 'Собрать выпуск' }))

    await waitFor(() => expect(location()).toBe('/digests/digest-new'))
    expect(sent.digests).toEqual([{ profile_id: 'profile-new', period_days: 1 }])
    expect(sent.marks).toBe(1)
  })

  it('builds the first profile from the resume the reader uploaded before', async () => {
    const sent = serveNewReader()
    const suggestion = makeSpec({ name: 'По резюме: защита АСУ ТП', interests: makeInterests(2) })
    server.use(http.get(apiUrl('/resume'), () => HttpResponse.json(makeResume({ suggestion }))))
    const { user } = renderOnboarding()

    await user.click(await screen.findByRole('button', { name: 'Начать' }))
    await user.click(screen.getByRole('radio', { name: /По резюме/ }))
    await user.click(await screen.findByRole('button', { name: 'Создать профиль' }))

    expect(await screen.findByRole('heading', { name: 'Первый выпуск' })).toBeInTheDocument()
    expect(screen.getByText('По резюме: защита АСУ ТП')).toBeInTheDocument()
    expect(sent.profiles.map((spec) => spec.name)).toEqual(['По резюме: защита АСУ ТП'])
  })

  it('marks it done when skipped, so it is not offered again', async () => {
    const sent = serveNewReader()
    const { user } = renderOnboarding()

    await user.click(await screen.findByRole('button', { name: 'Пропустить' }))

    await waitFor(() => expect(location()).toBe('/'))
    expect(sent.marks).toBe(1)
  })

  it('hands the manual way over to the profile editor, marked done', async () => {
    const sent = serveNewReader()
    const { user } = renderOnboarding()

    await user.click(await screen.findByRole('button', { name: 'Начать' }))
    await user.click(screen.getByRole('radio', { name: /Вручную/ }))
    await user.click(await screen.findByRole('button', { name: 'Открыть редактор' }))

    await waitFor(() => expect(location()).toBe('/profiles'))
    expect(sent.marks).toBe(1)
  })

  it('goes on with a profile the reader already has, taken again on demand', async () => {
    const sent = serveNewReader({ me: makeMe(), profiles: [makeProfile()] })
    const { user } = renderOnboarding()

    await user.click(await screen.findByRole('button', { name: 'Начать' }))
    expect(screen.getByText('У вас уже есть профиль «Инженер АСУ ТП».')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Продолжить с ним' }))
    await user.click(await screen.findByRole('button', { name: 'Позже, открыть ленту' }))

    await waitFor(() => expect(location()).toBe('/feed'))
    // Already introduced: taking it again does not touch the mark.
    expect(sent.marks).toBe(0)
    expect(sent.profiles).toEqual([])
  })

  it('keeps the reader on the last step with the reason when the digest is refused', async () => {
    const sent = serveNewReader({ profiles: [makeProfile()] })
    server.use(
      http.post(apiUrl('/digests'), () =>
        HttpResponse.json({ detail: 'Сборка уже идёт' }, { status: 409 }),
      ),
    )
    const { user } = renderOnboarding()

    await user.click(await screen.findByRole('button', { name: 'Начать' }))
    await user.click(screen.getByRole('button', { name: 'Продолжить с ним' }))
    await user.click(await screen.findByRole('button', { name: 'Собрать выпуск' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Сборка уже идёт')
    await user.click(screen.getByRole('button', { name: 'Собрать выпуск' }))

    expect(location()).toBe('/start')
    // Marked once, before the first attempt: a retry does not mark again.
    await waitFor(() => expect(sent.marks).toBe(1))
  })
})
