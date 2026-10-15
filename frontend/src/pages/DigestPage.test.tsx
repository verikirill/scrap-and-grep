import { act, screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import type { Digest, DigestSummary } from '../lib/api'
import { eventSources, setMediaQueries } from '../test/browser'
import {
  makeBriefingState,
  makeDigest,
  makeMailState,
  makeProfile,
  makeSchedule,
  makeSummary,
} from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { DigestPage } from './DigestPage'

/**
 * The digest page's API: profiles, schedules, the list of issues and each
 * issue by its id. The list can change, as it does after a deletion.
 */
function serveDigests(list: DigestSummary[], digests: Record<string, Digest> = {}) {
  const state = { list, deleted: [] as string[], built: [] as unknown[] }
  server.use(
    http.get(apiUrl('/profiles'), () => HttpResponse.json([makeProfile()])),
    http.get(apiUrl('/digest-schedules'), () => HttpResponse.json([makeSchedule()])),
    http.get(apiUrl('/digests'), () => HttpResponse.json(state.list)),
    http.get(apiUrl('/digests/:id'), ({ params }) => {
      const digest = digests[String(params.id)]
      return digest
        ? HttpResponse.json(digest)
        : HttpResponse.json({ detail: 'Выпуск не найден' }, { status: 404 })
    }),
    http.delete(apiUrl('/digests/:id'), ({ params }) => {
      state.deleted.push(String(params.id))
      state.list = state.list.filter((item) => item.id !== params.id)
      return new HttpResponse(null, { status: 204 })
    }),
    http.post(apiUrl('/digests'), async ({ request }) => {
      state.built.push(await request.json())
      return HttpResponse.json(makeSummary({ id: 'digest-9', status: 'queued' }))
    }),
  )
  return state
}

function renderPage(route = '/') {
  return renderWithProviders(
    <Routes>
      <Route path="/" element={<DigestPage />} />
      <Route path="/digests/:digestId" element={<DigestPage />} />
    </Routes>,
    { route },
  )
}

const location = () => screen.getByTestId('location').textContent

/** The page has loaded when the profile card names its schedule, the last request. */
async function loaded() {
  const card = await screen.findByRole('radio', { name: /Инженер АСУ ТП/ })
  await within(card).findByText('по будням в 09:00')
}

const failed = (overrides: Partial<Digest> = {}) =>
  makeDigest({ status: 'failed', error: 'Модель не ответила', ...overrides })

describe('DigestPage', () => {
  it('says there are no issues yet, with the cat searching for them', async () => {
    serveDigests([])
    const { container } = renderPage()
    expect(await screen.findByText('Выпусков пока нет')).toBeInTheDocument()
    expect(container.querySelector('.brand-cat')).toHaveAttribute('data-pose', 'search')
    expect(screen.getByText('Здесь появятся собранные выпуски.')).toBeInTheDocument()
    await loaded()
  })

  it('opens the latest issue when the address names none', async () => {
    serveDigests(
      [
        makeSummary({ id: 'digest-2', title: 'Выпуск за неделю', status: 'failed' }),
        makeSummary({ id: 'digest-1', title: 'Выпуск за сутки', status: 'failed' }),
      ],
      { 'digest-2': failed({ id: 'digest-2', title: 'Выпуск за неделю' }) },
    )
    renderPage()
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Выпуск за неделю' }),
    ).toBeInTheDocument()
    expect(await screen.findByText('Модель не ответила')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Выпуск за неделю/ })).toHaveAttribute(
      'aria-current',
      'true',
    )
    await loaded()
  })

  it('says an issue did not open and leads back to the latest one', async () => {
    serveDigests([makeSummary({ status: 'failed' })], { 'digest-1': failed() })
    const { user } = renderPage('/digests/digest-404')

    expect(await screen.findByRole('heading', { name: 'Не удалось открыть выпуск' })).toBeVisible()
    expect(screen.getByText('Не нашлось')).toBeInTheDocument()
    expect(screen.getByText('Выпуск не найден')).toBeInTheDocument()
    await loaded()

    await user.click(screen.getByRole('button', { name: 'К последнему выпуску' }))

    expect(location()).toBe('/')
    expect(await screen.findByText('Модель не ответила')).toBeInTheDocument()
  })

  it('rebuilds a failed issue over the same number of days and opens the new one', async () => {
    const week = {
      period_start: '2026-10-06T09:00:00Z',
      period_end: '2026-10-13T09:00:00Z',
      status: 'failed' as const,
    }
    const state = serveDigests([makeSummary(week)], {
      'digest-1': failed(week),
      'digest-9': makeDigest({ id: 'digest-9', status: 'queued', stage: null, progress: 0 }),
    })
    const { user } = renderPage('/digests/digest-1')
    await loaded()

    await user.click(await screen.findByRole('button', { name: 'Собрать заново' }))

    await waitFor(() => expect(location()).toBe('/digests/digest-9'))
    expect(state.built).toEqual([{ profile_id: 'profile-1', period_days: 7 }])
    expect(await screen.findByRole('heading', { name: 'В очереди' })).toBeInTheDocument()
  })

  it('follows a build on its progress card until the issue is done', async () => {
    let reads = 0
    serveDigests([makeSummary({ status: 'running' })])
    server.use(
      http.get(apiUrl('/digests/digest-1'), () => {
        reads += 1
        return HttpResponse.json(
          reads === 1
            ? makeDigest({ status: 'running', stage: 'grade', progress: 0.3 })
            : failed({ error: 'Источники не ответили' }),
        )
      }),
    )
    renderPage()
    expect(
      await screen.findByRole('progressbar', { name: 'Готовность выпуска' }),
    ).toBeInTheDocument()
    await loaded()
    const stream = eventSources.at(-1)
    expect(stream?.url).toBe('/api/v1/digests/digest-1/events')

    act(() => stream?.emit('progress', { status: 'failed', stage: 'grade', progress: 0.3 }))

    expect(await screen.findByText('Источники не ответили')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar', { name: 'Готовность выпуска' })).toBeNull()
  })

  it('opens an issue the reader just asked for', async () => {
    serveDigests([], {
      'digest-9': makeDigest({ id: 'digest-9', status: 'queued', stage: null, progress: 0 }),
    })
    const { user } = renderPage()
    await loaded()

    await user.click(screen.getByRole('button', { name: 'Собрать выпуск' }))

    await waitFor(() => expect(location()).toBe('/digests/digest-9'))
    expect(await screen.findByRole('heading', { name: 'В очереди' })).toBeInTheDocument()
    // The new issue is at the top of the history at once.
    expect(screen.getByRole('button', { name: /^Выпуск за сутки/ })).toHaveAttribute(
      'aria-current',
      'true',
    )
  })

  it('leaves the open issue for the latest when the reader deletes it, and stays on another', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const state = serveDigests(
      [
        makeSummary({ id: 'digest-3', title: 'Третий', status: 'failed' }),
        makeSummary({ id: 'digest-2', title: 'Второй', status: 'failed' }),
        makeSummary({ id: 'digest-1', title: 'Первый', status: 'failed' }),
      ],
      {
        'digest-3': failed({ id: 'digest-3', title: 'Третий' }),
        'digest-2': failed({ id: 'digest-2', title: 'Второй', error: 'Второй не собрался' }),
      },
    )
    const { user, client } = renderPage('/digests/digest-2')
    expect(await screen.findByText('Второй не собрался')).toBeInTheDocument()
    await loaded()

    await user.click(screen.getByRole('button', { name: 'Удалить выпуск «Первый»' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: /^Первый/ })).toBeNull())
    // The deletion has run its course, a reply to it included.
    await waitFor(() => expect(client.isMutating()).toBe(0))
    await act(() => new Promise((resolve) => setTimeout(resolve, 0)))
    expect(location()).toBe('/digests/digest-2')

    await user.click(screen.getByRole('button', { name: 'Удалить выпуск «Второй»' }))
    await waitFor(() => expect(location()).toBe('/'))
    expect(await screen.findByRole('heading', { level: 1, name: 'Третий' })).toBeInTheDocument()
    expect(state.deleted).toEqual(['digest-1', 'digest-2'])
  })

  it('compares a finished issue with the previous one of its kind and switches to its twin', async () => {
    const management = makeSummary({
      id: 'digest-3',
      audience: 'management',
      created_at: '2026-10-13T09:02:00Z',
    })
    const specialist = makeSummary({ id: 'digest-2', created_at: '2026-10-13T09:01:00Z' })
    // Built the day before for the same reader; the twin above is not "previous".
    const older = makeSummary({
      id: 'digest-1',
      period_start: '2026-10-11T09:00:00Z',
      period_end: '2026-10-12T09:00:00Z',
      created_at: '2026-10-12T09:00:00Z',
    })
    // Issues drawn in full: each asks whether it can be mailed.
    const shown: string[] = []
    const briefed: string[] = []
    serveDigests([management, specialist, older], {
      'digest-2': makeDigest({ ...specialist }),
      'digest-3': makeDigest({ ...management }),
    })
    server.use(
      http.get(apiUrl('/reactions'), () => HttpResponse.json([])),
      http.get(apiUrl('/digests/:id/mail'), ({ params }) => {
        shown.push(String(params.id))
        return HttpResponse.json(makeMailState())
      }),
      // Only a manager's issue offers a voiced brief.
      http.get(apiUrl('/digests/:id/briefing'), ({ params }) => {
        briefed.push(String(params.id))
        return HttpResponse.json(makeBriefingState())
      }),
    )
    const { user } = renderPage('/digests/digest-2')
    await loaded()

    expect(await screen.findByRole('link', { name: /Сравнить с предыдущим/ })).toHaveAttribute(
      'href',
      '/compare?base=digest-1&other=digest-2',
    )
    const reading = screen.getByRole('radiogroup', { name: 'Для кого читать выпуск' })
    await user.click(within(reading).getByRole('radio', { name: /Руководитель/ }))

    expect(location()).toBe('/digests/digest-3')
    await waitFor(() => expect(shown).toContain('digest-3'))
    await waitFor(() => expect(briefed).toEqual(['digest-3']))
    // The manager's issue has no earlier one of its kind to compare with.
    expect(screen.queryByRole('link', { name: /Сравнить с предыдущим/ })).toBeNull()
    expect(
      within(screen.getByRole('radiogroup', { name: 'Для кого читать выпуск' })).getByRole(
        'radio',
        { name: /Руководитель/ },
      ),
    ).toBeChecked()
  })

  describe('on a phone', () => {
    it('folds the build form into one button while an issue is open', async () => {
      setMediaQueries({ '(max-width: 767px)': true })
      serveDigests([makeSummary({ status: 'failed' })], { 'digest-1': failed() })
      const { user } = renderPage()
      expect(await screen.findByText('Модель не ответила')).toBeInTheDocument()
      expect(screen.queryByRole('radiogroup', { name: 'Профиль читателя' })).toBeNull()

      await user.click(screen.getByRole('button', { name: 'Новый выпуск' }))

      await loaded()
      expect(screen.queryByRole('button', { name: 'Новый выпуск' })).toBeNull()
    })

    it('keeps the form open for a profile sent here to be built', async () => {
      setMediaQueries({ '(max-width: 767px)': true })
      serveDigests([makeSummary({ status: 'failed' })], { 'digest-1': failed() })
      renderPage('/?profile=profile-1')
      await loaded()
      expect(screen.queryByRole('button', { name: 'Новый выпуск' })).toBeNull()
      expect(await screen.findByText('Модель не ответила')).toBeInTheDocument()
    })
  })
})
