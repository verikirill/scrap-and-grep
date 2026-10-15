import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { Briefing, BriefingState } from '../../lib/api'
import { makeBriefing, makeBriefingState, makeDigest } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { BriefingPlayer } from './BriefingPlayer'

const briefingUrl = apiUrl('/digests/digest-1/briefing')
const managementDigest = makeDigest({ audience: 'management' })

/**
 * The voice service as the server keeps it: an order starts a brief, which the
 * next read shows. Returns the voices ordered, in order.
 */
function serveBriefing(initial: BriefingState, started: Partial<Briefing> = {}) {
  let state = initial
  const ordered: (string | null)[] = []
  server.use(
    http.get(briefingUrl, () => HttpResponse.json(state)),
    http.post(briefingUrl, async ({ request }) => {
      const { voice } = (await request.json()) as { voice: string | null }
      ordered.push(voice)
      const briefing = makeBriefing({
        status: 'queued',
        progress: 0,
        lines: [],
        url: null,
        requested_voice: voice,
        ...started,
      })
      state = { ...state, briefing }
      return HttpResponse.json(briefing)
    }),
  )
  return {
    ordered,
    finish: (briefing: Briefing) => {
      state = { ...state, briefing }
    },
  }
}

describe('BriefingPlayer', () => {
  it('is not offered to a specialist’s issue, without asking the server', () => {
    // No handler: a request would fail the test.
    renderWithProviders(<BriefingPlayer digest={makeDigest({ audience: 'specialist' })} />)
    expect(screen.queryByRole('button', { name: /брифинг/ })).toBeNull()
  })

  it('is not offered when the server has no voice service', async () => {
    let asked = 0
    server.use(
      http.get(briefingUrl, () => {
        asked += 1
        return HttpResponse.json(makeBriefingState({ available: false, briefing: null }))
      }),
    )
    renderWithProviders(<BriefingPlayer digest={managementDigest} />)
    await waitFor(() => expect(asked).toBe(1))
    expect(screen.queryByRole('button', { name: /брифинг/ })).toBeNull()
  })

  it('orders the brief in the default voice on the first press and shows it queued', async () => {
    const { ordered } = serveBriefing(makeBriefingState({ briefing: null }))
    const { user } = renderWithProviders(<BriefingPlayer digest={managementDigest} />)

    await user.click(await screen.findByRole('button', { name: 'Слушать брифинг' }))

    const dialog = await screen.findByRole('dialog', { name: 'Голосовой брифинг' })
    expect(
      await within(dialog).findByRole('progressbar', { name: 'Готовность брифинга' }),
    ).toHaveAttribute('aria-valuetext', 'В очереди')
    expect(ordered).toEqual(['anchor'])
  })

  it('follows the voicing until the brief is ready to listen to', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const service = serveBriefing(
      makeBriefingState({ briefing: makeBriefing({ status: 'running', progress: 0.4 }) }),
    )
    const { user } = renderWithProviders(<BriefingPlayer digest={managementDigest} />, {
      userOptions: { advanceTimers: vi.advanceTimersByTime },
    })
    // A brief on its way shows on the button.
    await user.click(await screen.findByRole('button', { name: 'Озвучиваем брифинг' }))
    const dialog = await screen.findByRole('dialog', { name: 'Голосовой брифинг' })
    expect(within(dialog).getByRole('progressbar')).toHaveAttribute('aria-valuenow', '40')

    service.finish(makeBriefing())
    await vi.advanceTimersByTimeAsync(3_000)

    expect(await within(dialog).findByLabelText('Голосовой брифинг по выпуску')).toBeInTheDocument()
    expect(within(dialog).queryByRole('progressbar')).toBeNull()
  })

  it('plays a ready brief with its transcript, voice and download', async () => {
    serveBriefing(makeBriefingState())
    const { user } = renderWithProviders(<BriefingPlayer digest={managementDigest} />)

    await user.click(await screen.findByRole('button', { name: 'Слушать брифинг' }))

    const dialog = await screen.findByRole('dialog', { name: 'Голосовой брифинг' })
    const audio = within(dialog).getByLabelText('Голосовой брифинг по выпуску')
    expect(audio).toHaveAttribute('src', '/api/v1/digests/digest-1/briefing.wav?v=1791969120')
    // The transcript is the recording's text alternative.
    expect(audio).toHaveAccessibleDescription(/^Добрый день\. За сутки три события/)
    expect(
      within(dialog).getByText('голос: Ведущая · 3,6 МБ · готово 14 окт., 12:12'),
    ).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: 'Скачать WAV' })).toHaveAttribute(
      'href',
      '/api/v1/digests/digest-1/briefing.wav?v=1791969120&download=1',
    )
  })

  it('voices the brief again in a voice the reader picks', async () => {
    const { ordered } = serveBriefing(makeBriefingState())
    const { user } = renderWithProviders(<BriefingPlayer digest={managementDigest} />)
    await user.click(await screen.findByRole('button', { name: 'Слушать брифинг' }))
    const dialog = await screen.findByRole('dialog', { name: 'Голосовой брифинг' })

    // The last brief's voice stays picked.
    await user.click(within(dialog).getByRole('button', { name: /Голос: Ведущая$/ }))
    const list = await screen.findByRole('listbox', { name: /^Голос/ })
    await user.click(within(list).getByRole('option', { name: 'Спокойно' }))
    await user.click(within(dialog).getByRole('button', { name: 'Озвучить заново' }))

    expect(await within(dialog).findByRole('progressbar')).toHaveAttribute(
      'aria-valuetext',
      'В очереди',
    )
    expect(ordered).toEqual(['analyst'])
  })

  it('says why the voicing failed and offers to try again', async () => {
    const { ordered } = serveBriefing(
      makeBriefingState({
        briefing: makeBriefing({
          status: 'failed',
          error: 'Сервис озвучки не ответил',
          url: null,
          requested_voice: 'blogger',
        }),
      }),
    )
    const { user } = renderWithProviders(<BriefingPlayer digest={managementDigest} />)
    await user.click(await screen.findByRole('button', { name: 'Слушать брифинг' }))
    const dialog = await screen.findByRole('dialog', { name: 'Голосовой брифинг' })
    expect(within(dialog).getByText('Сервис озвучки не ответил')).toBeVisible()

    await user.click(within(dialog).getByRole('button', { name: 'Попробовать снова' }))

    expect(await within(dialog).findByRole('progressbar')).toHaveAttribute(
      'aria-valuetext',
      'В очереди',
    )
    expect(ordered).toEqual(['blogger'])
  })
})
