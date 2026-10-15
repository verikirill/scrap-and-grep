import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { Adaptation, Profile } from '../../lib/api'
import {
  makeAdaptation,
  makeInterest,
  makeInterestLearning,
  makeProfile,
  makeSpec,
  makeSuggestion,
} from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { AdaptationPanel } from './AdaptationPanel'

const adaptationUrl = apiUrl('/profiles/profile-1/adaptation')

/** The adaptation as the server keeps it: a switch sent is there on the next read. */
function serveAdaptation(
  initial: Adaptation,
  { onSwitch }: { onSwitch?: () => Promise<void> } = {},
) {
  let current = initial
  const switched: unknown[] = []
  server.use(
    http.get(adaptationUrl, () => HttpResponse.json(current)),
    http.patch(adaptationUrl, async ({ request }) => {
      const body = (await request.json()) as { adaptive: boolean }
      switched.push(body)
      await onSwitch?.()
      current = { ...current, adaptive: body.adaptive }
      return HttpResponse.json(current)
    }),
  )
  return switched
}

function renderPanel() {
  return renderWithProviders(
    <AdaptationPanel profile={makeProfile({ adaptive: true })} onApplied={vi.fn()} />,
  )
}

const panel = () => screen.getByRole('region', { name: 'Подстройка по отметкам' })
const suggestions = () => screen.queryByRole('list', { name: 'Предложения для профиля' })

describe('AdaptationPanel switch', () => {
  it('turns adapting off and on again', async () => {
    const switched = serveAdaptation(makeAdaptation())
    const { user } = renderPanel()
    await screen.findByRole('list', { name: 'Предложения для профиля' })
    const toggle = screen.getByRole('switch', { name: 'Подстройка по отметкам' })
    expect(toggle).toBeChecked()
    expect(toggle).toHaveAccessibleDescription(/^Отметки по темам профиля/)

    await user.click(toggle)

    await waitFor(() => expect(toggle).not.toBeChecked())
    expect(toggle).toHaveAccessibleDescription(
      'Выключено. Лента и выпуски используют профиль без изменений.',
    )
    expect(suggestions()).toBeNull()

    await user.click(toggle)

    await waitFor(() => expect(toggle).toBeChecked())
    expect(suggestions()).toBeInTheDocument()
    expect(switched).toEqual([{ adaptive: false }, { adaptive: true }])
  })

  it('leaves the switch as it was and says why when the server refuses', async () => {
    server.use(
      http.get(adaptationUrl, () => HttpResponse.json(makeAdaptation())),
      http.patch(adaptationUrl, () =>
        HttpResponse.json({ detail: 'Подстройка временно недоступна' }, { status: 503 }),
      ),
    )
    const { user } = renderPanel()
    await screen.findByRole('list', { name: 'Предложения для профиля' })
    const toggle = screen.getByRole('switch', { name: 'Подстройка по отметкам' })

    await user.click(toggle)

    expect(await within(panel()).findByRole('alert')).toHaveTextContent(
      'Подстройка временно недоступна',
    )
    expect(toggle).toBeChecked()
    expect(suggestions()).toBeInTheDocument()
  })

  it('ignores a click while the last one is on its way', async () => {
    let release = () => {}
    const answer = new Promise<void>((resolve) => {
      release = resolve
    })
    const switched = serveAdaptation(makeAdaptation(), { onSwitch: () => answer })
    const { user } = renderPanel()
    await screen.findByRole('list', { name: 'Предложения для профиля' })
    const toggle = screen.getByRole('switch', { name: 'Подстройка по отметкам' })

    await user.click(toggle)
    await waitFor(() => expect(switched).toHaveLength(1))
    await user.click(toggle)
    release()

    await waitFor(() => expect(toggle).not.toBeChecked())
    expect(switched).toEqual([{ adaptive: false }])
  })
})

describe('AdaptationPanel learning', () => {
  it('shows on request how each interest was weighed, and folds it again', async () => {
    serveAdaptation(
      makeAdaptation({
        interests: [
          // Liked: the weight went up and the focus moved.
          makeInterestLearning(),
          // Disliked a little: down, the focus barely moved.
          makeInterestLearning({
            interest_id: 'interest-2',
            title: 'Атаки на энергетику',
            weight: 0.94,
            factor: 0.94,
            drift: 0.004,
            positives: 0,
            negatives: 1.25,
            skipped: 0,
          }),
          makeInterestLearning({
            interest_id: 'interest-3',
            title: 'Требования регуляторов',
            weight: 1,
            factor: 1,
            drift: 0,
            positives: 0,
            negatives: 0,
            skipped: 0,
          }),
        ],
      }),
    )
    const { user } = renderPanel()
    const details = await screen.findByRole('button', { name: 'Как подстроены интересы' })
    expect(details).toHaveAttribute('aria-expanded', 'false')

    await user.click(details)

    expect(details).toHaveAttribute('aria-expanded', 'true')
    const region = document.getElementById(details.getAttribute('aria-controls') ?? '')
    const [liked, disliked, untouched] = within(region as HTMLElement).getAllByRole('listitem')
    expect(liked).toHaveTextContent('Уязвимости АСУ ТП1.00 → 1.06')
    expect(
      within(liked).getByText(
        '«больше такого» 9 · «меньше такого» 2 · пропущено 14 · фокус сдвинут к понравившемуся на 12%',
      ),
    ).toBeInTheDocument()
    expect(disliked).toHaveTextContent('Атаки на энергетику1.00 → 0.94')
    expect(within(disliked).getByText('«меньше такого» 1,3')).toBeInTheDocument()
    expect(untouched).toHaveTextContent('Требования регуляторов1.00')
    expect(untouched).not.toHaveTextContent('→')
    expect(within(untouched).getByText('отметок пока нет')).toBeInTheDocument()

    await user.click(details)

    expect(details).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Атаки на энергетику')).toBeNull()
  })
})

/** Suggestions as the server keeps them: a decided one is gone on the next read. */
function serveSuggestions(
  initial: Adaptation,
  { onDecide }: { onDecide?: () => Promise<void> } = {},
) {
  let current = initial
  const decided: string[] = []
  const accepted = makeProfile({
    version: 2,
    spec: makeSpec({
      interests: [makeInterest(), makeInterest({ id: 'interest-9', title: 'ВИЭ' })],
    }),
  })
  const decide = (verb: 'accept' | 'dismiss') =>
    http.post(apiUrl(`/profiles/profile-1/suggestions/:id/${verb}`), async ({ params }) => {
      decided.push(`${verb} ${String(params.id)}`)
      await onDecide?.()
      current = {
        ...current,
        suggestions: current.suggestions.filter((item) => item.id !== params.id),
      }
      return verb === 'accept'
        ? HttpResponse.json(accepted)
        : new HttpResponse(null, { status: 204 })
    })
  server.use(
    http.get(adaptationUrl, () => HttpResponse.json(current)),
    decide('accept'),
    decide('dismiss'),
  )
  return { decided, accepted }
}

function renderWithApplied() {
  const applied: Profile[] = []
  const result = renderWithProviders(
    <AdaptationPanel
      profile={makeProfile({ adaptive: true })}
      onApplied={(profile) => applied.push(profile)}
    />,
  )
  return { ...result, applied }
}

const topic = makeSuggestion()
const exclusion = makeSuggestion({
  kind: 'exclusion',
  source: 'dislikes',
  title: 'криптовалюты',
  description: '',
  keywords: [],
})

describe('AdaptationPanel suggestions', () => {
  it('shows a new topic with its keywords and the article behind it, and an exclusion', async () => {
    serveSuggestions(makeAdaptation({ suggestions: [topic, exclusion] }))
    renderWithApplied()

    const list = await screen.findByRole('list', { name: 'Предложения для профиля' })
    // The cards themselves; their keywords and articles are lists of their own.
    const [first, second] = Array.from(list.children) as HTMLElement[]
    expect(first).toHaveTextContent('Новая тема · по вашим отметкам')
    expect(within(first).getByText('инвертор')).toBeInTheDocument()
    expect(within(first).getByRole('link', { name: topic.articles[0].title })).toHaveAttribute(
      'href',
      topic.articles[0].url,
    )
    expect(second).toHaveTextContent('Не показывать · по скрытым публикациям')
    expect(second).toHaveTextContent(
      'Публикации с этим словом не попадут в ленту и выпуски по этому профилю.',
    )
  })

  it('adds a suggested topic to the profile, says so and returns the focus to the panel', async () => {
    const { decided, accepted } = serveSuggestions(makeAdaptation({ suggestions: [topic] }))
    const { user, applied } = renderWithApplied()

    await user.click(
      await screen.findByRole('button', {
        name: 'Добавить тему «Безопасность ВИЭ-генерации» в профиль',
      }),
    )

    expect(
      await screen.findByText('Тема «Безопасность ВИЭ-генерации» добавлена в профиль'),
    ).toBeInTheDocument()
    expect(decided).toEqual([`accept ${topic.id}`])
    expect(applied).toEqual([accepted])
    await waitFor(() => expect(suggestions()).toBeNull())
    expect(screen.getByRole('heading', { name: 'Подстройка по отметкам' })).toHaveFocus()
  })

  it('excludes a word the reader hid and says it will not be shown', async () => {
    const { decided } = serveSuggestions(makeAdaptation({ suggestions: [exclusion] }))
    const { user } = renderWithApplied()

    await user.click(await screen.findByRole('button', { name: 'Исключить «криптовалюты»' }))

    expect(await screen.findByText('«криптовалюты» больше не покажем')).toBeInTheDocument()
    expect(decided).toEqual([`accept ${exclusion.id}`])
  })

  it('turns a suggestion down without changing the profile', async () => {
    const { decided } = serveSuggestions(makeAdaptation({ suggestions: [topic, exclusion] }))
    const { user, applied } = renderWithApplied()

    await user.click(
      await screen.findByRole('button', { name: 'Отклонить: «Безопасность ВИЭ-генерации»' }),
    )

    await waitFor(() =>
      expect(
        screen.queryByRole('button', { name: 'Отклонить: «Безопасность ВИЭ-генерации»' }),
      ).toBeNull(),
    )
    expect(screen.getByRole('button', { name: 'Исключить «криптовалюты»' })).toBeEnabled()
    expect(decided).toEqual([`dismiss ${topic.id}`])
    expect(applied).toEqual([])
    expect(screen.queryByText(/добавлена в профиль/)).toBeNull()
  })

  it('decides one suggestion at a time', async () => {
    let release = () => {}
    const answer = new Promise<void>((resolve) => {
      release = resolve
    })
    const { decided } = serveSuggestions(makeAdaptation({ suggestions: [topic, exclusion] }), {
      onDecide: () => answer,
    })
    const { user } = renderWithApplied()
    await user.click(
      await screen.findByRole('button', {
        name: 'Добавить тему «Безопасность ВИЭ-генерации» в профиль',
      }),
    )

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Исключить «криптовалюты»' })).toBeDisabled(),
    )
    expect(screen.getByRole('button', { name: 'Отклонить: «криптовалюты»' })).toBeDisabled()
    expect(
      screen.getByRole('button', { name: 'Отклонить: «Безопасность ВИЭ-генерации»' }),
    ).toBeDisabled()
    release()

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Исключить «криптовалюты»' })).toBeEnabled(),
    )
    expect(decided).toEqual([`accept ${topic.id}`])
  })
})

describe('AdaptationPanel reset', () => {
  it('forgets what the profile learned only after the reader confirms', async () => {
    const resets: string[] = []
    server.use(
      http.get(adaptationUrl, () => HttpResponse.json(makeAdaptation({ suggestions: [] }))),
      http.post(`${adaptationUrl}/reset`, () => {
        resets.push('reset')
        return HttpResponse.json(
          makeAdaptation({
            suggestions: [],
            interests: [
              makeInterestLearning({
                weight: 1,
                factor: 1,
                drift: 0,
                positives: 0,
                negatives: 0,
                skipped: 0,
              }),
            ],
          }),
        )
      }),
    )
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const { user } = renderPanel()
    await user.click(await screen.findByRole('button', { name: 'Как подстроены интересы' }))
    const reset = screen.getByRole('button', { name: 'Сбросить обучение' })

    await user.click(reset)
    expect(confirm).toHaveBeenLastCalledWith(
      'Сбросить результаты адаптации профиля по вашим отметкам?',
    )
    expect(screen.getByRole('button', { name: 'Как подстроены интересы' })).toBeInTheDocument()
    await user.click(reset)

    expect(await screen.findByText(/^Отмечайте публикации в ленте и выпусках/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Как подстроены интересы' })).toBeNull()
    expect(resets).toEqual(['reset'])
  })
})
