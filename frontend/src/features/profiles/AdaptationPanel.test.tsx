import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { Adaptation } from '../../lib/api'
import { makeAdaptation, makeProfile } from '../../test/fixtures'
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
