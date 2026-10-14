import { screen, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Analytics } from '../lib/api'
import { makeAnalytics, makeAnalyticsTotals, makeMe } from '../test/fixtures'
import { renderWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import { AnalyticsPage } from './AnalyticsPage'

/** An administrator's session and the overview the server counts; the queries it was asked. */
function serveAnalytics(analytics: Analytics = makeAnalytics(), me = makeMe({ is_admin: true })) {
  const asked: string[] = []
  server.use(
    http.get(apiUrl('/auth/me'), () => HttpResponse.json(me)),
    http.get(apiUrl('/analytics/overview'), ({ request }) => {
      asked.push(new URL(request.url).search)
      return HttpResponse.json(analytics)
    }),
  )
  return asked
}

describe('AnalyticsPage', () => {
  it('is closed to a reader who is not an administrator, and asks the server nothing', async () => {
    const asked = serveAnalytics(makeAnalytics(), makeMe({ is_admin: false }))
    renderWithProviders(<AnalyticsPage />)

    expect(await screen.findByText('Раздел для администратора')).toBeInTheDocument()
    expect(asked).toEqual([])
  })

  it('is closed to a guest even with the administrator flag', async () => {
    const asked = serveAnalytics(makeAnalytics(), makeMe({ is_admin: true, is_demo: true }))
    renderWithProviders(<AnalyticsPage />)

    expect(await screen.findByText('Раздел для администратора')).toBeInTheDocument()
    expect(asked).toEqual([])
  })

  it('shows the overview of the last 30 days with guests', async () => {
    const asked = serveAnalytics()
    renderWithProviders(<AnalyticsPage />)

    expect(await screen.findByText('Стрелки: изменение к предыдущим 30 дням.')).toBeInTheDocument()
    expect(asked).toEqual(['?days=30&guests=true'])
    for (const title of [
      'От показа к отметке',
      'По дням',
      'Места в ленте и выпусках',
      'Источники',
      'Категории',
      'Подстройка профилей',
      'Ранжирование ленты',
    ]) {
      expect(screen.getByRole('heading', { name: title })).toBeInTheDocument()
    }
    expect(screen.getByText(/^События: последнее событие .*, ждут записи 0\.$/)).toBeInTheDocument()
  })

  it('asks again for another period and without guests', async () => {
    const asked = serveAnalytics()
    const { user } = renderWithProviders(<AnalyticsPage />)
    await screen.findByText('Стрелки: изменение к предыдущим 30 дням.')

    await user.click(screen.getByRole('radio', { name: /7 дней/ }))
    expect(await screen.findByText('Стрелки: изменение к предыдущим 7 дням.')).toBeInTheDocument()
    await user.click(screen.getByRole('switch', { name: 'Учитывать гостей' }))

    await waitFor(() =>
      expect(asked).toEqual([
        '?days=30&guests=true',
        '?days=7&guests=true',
        '?days=7&guests=false',
      ]),
    )
    expect(screen.getByRole('switch', { name: 'Учитывать гостей' })).toHaveAttribute(
      'aria-checked',
      'false',
    )
  })

  it('says when the stand keeps no events', async () => {
    serveAnalytics(makeAnalytics({ enabled: false }))
    renderWithProviders(<AnalyticsPage />)

    expect(await screen.findByText('События выключены')).toBeInTheDocument()
    expect(screen.queryByText('Читатели')).toBeNull()
  })

  it('says when the period has no events yet', async () => {
    serveAnalytics(
      makeAnalytics({
        totals: makeAnalyticsTotals({ seen: 0, opened: 0, liked: 0, rejected: 0, served: 0 }),
      }),
    )
    renderWithProviders(<AnalyticsPage />)

    expect(await screen.findByText('Событий за период пока нет')).toBeInTheDocument()
  })

  it('tells how many events wait to be written and how many were set aside', async () => {
    serveAnalytics(makeAnalytics({ last_event_at: null, queue: { waiting: 1200, set_aside: 3 } }))
    renderWithProviders(<AnalyticsPage />)

    expect(
      await screen.findByText('События: ждут записи 1 200, отложено нечитаемых 3.'),
    ).toBeInTheDocument()
  })

  it('shows why the overview could not be counted', async () => {
    serveAnalytics()
    server.use(
      http.get(apiUrl('/analytics/overview'), () =>
        HttpResponse.json({ detail: 'ClickHouse недоступен' }, { status: 503 }),
      ),
    )
    renderWithProviders(<AnalyticsPage />)

    expect(await screen.findByRole('alert')).toHaveTextContent('ClickHouse недоступен')
    expect(screen.queryByRole('status', { name: 'Считаем' })).toBeNull()
  })
})
