import { screen, waitFor } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
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

/** The sections of the app as the sidebar lists them: the tour shows them in this order. */
const SECTIONS = ['Дайджест', 'Для вас', 'Интересы', 'Каналы', 'Источники', 'Сравнение', 'Аккаунт']

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

async function renderOnboarding() {
  const view = renderWithProviders(<OnboardingPage />, { route: '/start' })
  // The name arrives with the account: under a full run that may take a while.
  await screen.findByRole('heading', { level: 1, name: /Здравствуйте, / }, { timeout: 5000 })
  return view
}

const location = () => screen.getByTestId('location').textContent
/** The step the stepper marks as the current one. */
const currentStep = () => screen.getByRole('button', { current: 'step' }).getAttribute('aria-label')
const heading = () => screen.getByRole('heading', { level: 1 })
const toSetup = (user: UserEvent) =>
  user.click(screen.getByRole('button', { name: 'Сразу к настройке' }))

describe('OnboardingPage', () => {
  it('walks through every section in the order of the sidebar before the setup', async () => {
    serveNewReader()
    const { user } = await renderOnboarding()

    expect(heading()).toHaveTextContent('Здравствуйте, Анна Петрова')
    expect(currentStep()).toBe('Шаг 1: Знакомство')
    await user.click(screen.getByRole('button', { name: 'Начать знакомство' }))

    const seen: string[] = []
    for (const [index, name] of SECTIONS.entries()) {
      expect(currentStep()).toBe(`Шаг ${index + 2}: ${name}`)
      expect(screen.getByText(`Раздел «${name}»`)).toBeInTheDocument()
      seen.push(name)
      await user.click(screen.getByRole('button', { name: 'Далее' }))
    }

    expect(seen).toEqual(SECTIONS)
    expect(currentStep()).toBe('Шаг 9: Профиль')
    expect(heading()).toHaveTextContent('Первый профиль интересов')
    // No step ahead until there is a profile to build the digest for.
    expect(screen.queryByRole('button', { name: 'Далее' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Шаг 10: Первый выпуск' })).toBeDisabled()
  })

  it('tells what each section really offers', async () => {
    serveNewReader()
    const { user } = await renderOnboarding()
    await user.click(screen.getByRole('button', { name: 'Начать знакомство' }))

    expect(screen.getByText('Специалисту: матрица риска и план на смену')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Далее' }))
    expect(screen.getByText(/Вид «Посты» показывает ленту/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Шаг 8: Аккаунт' }))
    expect(screen.getByText(/Ключ MCP открывает ИИ-ассистенту/)).toBeInTheDocument()
    // The picture shows the nine ready avatars.
    expect(document.querySelectorAll('img[src^="/brand/avatars/"]')).toHaveLength(9)
  })

  it('goes back and forth with the buttons and the stepper', async () => {
    serveNewReader()
    const { user } = await renderOnboarding()

    await user.click(screen.getByRole('button', { name: 'Начать знакомство' }))
    await user.click(screen.getByRole('button', { name: 'Далее' }))
    expect(currentStep()).toBe('Шаг 3: Для вас')

    await user.click(screen.getByRole('button', { name: 'Назад' }))
    expect(currentStep()).toBe('Шаг 2: Дайджест')
    await user.click(screen.getByRole('button', { name: 'Назад' }))
    expect(currentStep()).toBe('Шаг 1: Знакомство')
    // The greeting has nothing behind it.
    expect(screen.queryByRole('button', { name: 'Назад' })).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Шаг 6: Источники' }))
    expect(heading()).toHaveTextContent('Откуда берутся новости')
  })

  it('moves the focus to the heading of each new step', async () => {
    serveNewReader()
    const { user } = await renderOnboarding()
    // The first screen keeps the focus where the reader left it.
    expect(heading()).not.toHaveFocus()

    await user.click(screen.getByRole('button', { name: 'Начать знакомство' }))

    await waitFor(() => expect(heading()).toHaveFocus())
    expect(heading()).toHaveTextContent('Выпуск под вашу задачу')
  })

  describe('keyboard', () => {
    it('steps with the arrows and goes on with Enter', async () => {
      serveNewReader()
      const { user } = await renderOnboarding()

      await user.keyboard('{ArrowRight}')
      expect(currentStep()).toBe('Шаг 2: Дайджест')
      await user.keyboard('{Enter}')
      expect(currentStep()).toBe('Шаг 3: Для вас')
      await user.keyboard('{ArrowLeft}')
      expect(currentStep()).toBe('Шаг 2: Дайджест')
      await user.keyboard('{ArrowLeft}{ArrowLeft}')
      expect(currentStep()).toBe('Шаг 1: Знакомство')
    })

    it('leaves Enter on a button and the arrows of a radio group to them', async () => {
      serveNewReader()
      server.use(http.get(apiUrl('/resume'), () => HttpResponse.json(makeResume())))
      const { user } = await renderOnboarding()
      await toSetup(user)

      const resume = screen.getByRole('radio', { name: /По резюме/ })
      resume.focus()
      await user.keyboard('{ArrowRight}')
      expect(screen.getByRole('radio', { name: /Готовый шаблон/ })).toBeChecked()
      await user.keyboard('{ArrowLeft}')
      expect(currentStep()).toBe('Шаг 9: Профиль')

      screen.getByRole('button', { name: 'Назад' }).focus()
      await user.keyboard('{Enter}')
      // Enter pressed the button, once: one step back, not one back and one ahead.
      expect(currentStep()).toBe('Шаг 8: Аккаунт')
    })

    it('skips the introduction with Escape and marks it done', async () => {
      const sent = serveNewReader()
      const { user } = await renderOnboarding()
      await user.keyboard('{ArrowRight}{ArrowRight}')

      await user.keyboard('{Escape}')

      await waitFor(() => expect(location()).toBe('/'))
      expect(sent.marks).toBe(1)
    })
  })

  it.each([
    ['the greeting', 0],
    ['a section', 4],
    ['the profile', 8],
  ])('marks it done when skipped from %s, so it is not offered again', async (_, steps) => {
    const sent = serveNewReader()
    const { user } = await renderOnboarding()
    for (let index = 0; index < steps; index += 1) await user.keyboard('{ArrowRight}')

    await user.click(screen.getByRole('button', { name: 'Пропустить' }))

    await waitFor(() => expect(location()).toBe('/'))
    expect(sent.marks).toBe(1)
  })

  it('takes a new reader from the greeting through a template to the first digest', async () => {
    const sent = serveNewReader()
    const { user } = await renderOnboarding()

    await toSetup(user)
    expect(heading()).toHaveTextContent('Первый профиль интересов')
    await user.click(screen.getByRole('radio', { name: /Готовый шаблон/ }))
    const take = await screen.findByRole('button', { name: 'Взять этот шаблон' })
    expect(take).toBeDisabled()
    await user.click(screen.getByRole('radio', { name: /Руководитель ИТ-инфраструктуры/ }))
    await user.click(take)

    expect(await screen.findByRole('heading', { name: 'Первый выпуск' })).toBeInTheDocument()
    expect(currentStep()).toBe('Шаг 10: Первый выпуск')
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

  it('keeps the profile when the reader steps back from the digest and on again', async () => {
    const sent = serveNewReader({ profiles: [makeProfile()] })
    const { user } = await renderOnboarding()
    await toSetup(user)
    await user.click(screen.getByRole('button', { name: 'Продолжить с ним' }))

    await user.click(await screen.findByRole('button', { name: 'Назад' }))
    expect(currentStep()).toBe('Шаг 9: Профиль')
    await user.click(screen.getByRole('button', { name: 'Далее' }))

    expect(heading()).toHaveTextContent('Первый выпуск')
    expect(screen.getByText('Инженер АСУ ТП')).toBeInTheDocument()
    expect(sent.profiles).toEqual([])
  })

  it('builds the first profile from the resume the reader uploaded before', async () => {
    const sent = serveNewReader()
    const suggestion = makeSpec({ name: 'По резюме: защита АСУ ТП', interests: makeInterests(2) })
    server.use(http.get(apiUrl('/resume'), () => HttpResponse.json(makeResume({ suggestion }))))
    const { user } = await renderOnboarding()

    await toSetup(user)
    await user.click(screen.getByRole('radio', { name: /По резюме/ }))
    await user.click(await screen.findByRole('button', { name: 'Создать профиль' }))

    expect(await screen.findByRole('heading', { name: 'Первый выпуск' })).toBeInTheDocument()
    expect(screen.getByText('По резюме: защита АСУ ТП')).toBeInTheDocument()
    expect(sent.profiles.map((spec) => spec.name)).toEqual(['По резюме: защита АСУ ТП'])
  })

  it('hands the manual way over to the profile editor, marked done', async () => {
    const sent = serveNewReader()
    const { user } = await renderOnboarding()

    await toSetup(user)
    await user.click(screen.getByRole('radio', { name: /Вручную/ }))
    await user.click(await screen.findByRole('button', { name: 'Открыть редактор' }))

    await waitFor(() => expect(location()).toBe('/profiles'))
    expect(sent.marks).toBe(1)
  })

  describe('taken again from the account page', () => {
    it('goes on with a profile the reader already has and leaves the mark alone', async () => {
      const sent = serveNewReader({ me: makeMe(), profiles: [makeProfile()] })
      const { user } = await renderOnboarding()

      await toSetup(user)
      expect(screen.getByText('У вас уже есть профиль «Инженер АСУ ТП».')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Продолжить с ним' }))
      await user.click(await screen.findByRole('button', { name: 'Позже, открыть ленту' }))

      await waitFor(() => expect(location()).toBe('/feed'))
      expect(sent.marks).toBe(0)
      expect(sent.profiles).toEqual([])
    })

    it('is left with «Пропустить» or Escape without touching the mark', async () => {
      const sent = serveNewReader({ me: makeMe() })
      const { user } = await renderOnboarding()

      await user.keyboard('{ArrowRight}{Escape}')

      await waitFor(() => expect(location()).toBe('/'))
      expect(sent.marks).toBe(0)
    })
  })

  it('keeps the reader on the last step with the reason when the digest is refused', async () => {
    const sent = serveNewReader({ profiles: [makeProfile()] })
    server.use(
      http.post(apiUrl('/digests'), () =>
        HttpResponse.json({ detail: 'Сборка уже идёт' }, { status: 409 }),
      ),
    )
    const { user } = await renderOnboarding()

    await toSetup(user)
    await user.click(screen.getByRole('button', { name: 'Продолжить с ним' }))
    await user.click(await screen.findByRole('button', { name: 'Собрать выпуск' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Сборка уже идёт')
    await user.click(screen.getByRole('button', { name: 'Собрать выпуск' }))

    expect(location()).toBe('/start')
    // Marked once, before the first attempt: a retry does not mark again.
    await waitFor(() => expect(sent.marks).toBe(1))
  })
})
