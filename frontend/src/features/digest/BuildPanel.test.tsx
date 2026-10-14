import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Profile } from '../../lib/api'
import { makeProfile, makeSchedule, makeSummary } from '../../test/fixtures'
import { makeManagementProfile } from '../../test/fixtures/p03'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { BuildPanel } from './BuildPanel'

type Sent = { path: string; body: Record<string, unknown> }

/** The build endpoints, recording what the panel asks for. */
function serveBuilds({ schedules = [makeSchedule()] } = {}) {
  const sent: Sent[] = []
  const record = async (request: Request) =>
    sent.push({
      path: new URL(request.url).pathname,
      body: (await request.json()) as Record<string, unknown>,
    })
  server.use(
    http.get(apiUrl('/digest-schedules'), () => HttpResponse.json(schedules)),
    http.post(apiUrl('/digests'), async ({ request }) => {
      await record(request)
      return HttpResponse.json(makeSummary({ id: 'digest-9', status: 'queued' }))
    }),
    http.post(apiUrl('/digests/both'), async ({ request }) => {
      await record(request)
      return HttpResponse.json([
        makeSummary({ id: 'digest-9', status: 'queued' }),
        makeSummary({ id: 'digest-10', status: 'queued', audience: 'management' }),
      ])
    }),
  )
  return sent
}

const TWO_PROFILES = [makeProfile(), makeManagementProfile()]

function renderPanel(
  props: { profiles?: Profile[]; initialProfileId?: string; isBuilding?: boolean } = {},
) {
  const onCreated = vi.fn()
  const result = renderWithProviders(
    <BuildPanel profiles={TWO_PROFILES} onCreated={onCreated} {...props} />,
  )
  return { ...result, onCreated }
}

/** The panel has its schedules when the schedule line under it is drawn. */
const loaded = () => screen.findByRole('button', { name: /^(Изменить|Настроить)$/ })
const profile = (name: RegExp) =>
  within(screen.getByRole('radiogroup', { name: 'Профиль читателя' })).getByRole('radio', {
    name,
  })
const period = (name: RegExp) =>
  within(screen.getByRole('radiogroup', { name: 'Период' })).getByRole('radio', { name })

describe('BuildPanel', () => {
  afterEach(() => vi.useRealTimers())

  it('builds the first profile’s issue for its audience’s period', async () => {
    const sent = serveBuilds()
    const { user, onCreated } = renderPanel()
    await loaded()
    expect(profile(/Инженер АСУ ТП/)).toBeChecked()
    expect(within(profile(/Инженер АСУ ТП/)).getByText('по будням в 09:00')).toBeInTheDocument()
    expect(period(/Сутки/)).toBeChecked()

    await user.click(screen.getByRole('button', { name: 'Собрать выпуск' }))

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith('digest-9'))
    expect(sent).toEqual([
      { path: '/api/v1/digests', body: { profile_id: 'profile-1', period_days: 1 } },
    ])
  })

  it('takes a week for a management profile, and the period the reader picks', async () => {
    const sent = serveBuilds({ schedules: [] })
    const { user, onCreated } = renderPanel()
    await loaded()

    await user.click(profile(/Руководство ИБ/))
    expect(period(/Неделя/)).toBeChecked()
    await user.click(period(/Месяц/))
    await user.click(screen.getByRole('button', { name: 'Собрать выпуск' }))

    await waitFor(() => expect(onCreated).toHaveBeenCalled())
    expect(sent[0].body).toEqual({ profile_id: 'profile-2', period_days: 30 })
  })

  it('starts from the profile the address names', async () => {
    serveBuilds()
    renderPanel({ initialProfileId: 'profile-2' })
    await loaded()
    expect(profile(/Руководство ИБ/)).toBeChecked()
    expect(profile(/Инженер АСУ ТП/)).not.toBeChecked()
  })

  it('moves between profiles with the arrow keys', async () => {
    serveBuilds()
    const { user } = renderPanel()
    await loaded()
    await user.click(profile(/Инженер АСУ ТП/))
    await user.keyboard('{ArrowRight}')
    expect(profile(/Руководство ИБ/)).toBeChecked()
    expect(profile(/Руководство ИБ/)).toHaveFocus()
  })

  it('builds for both audiences at once and opens the specialist’s issue', async () => {
    const sent = serveBuilds()
    const { user, onCreated } = renderPanel()
    await loaded()

    await user.click(screen.getByRole('button', { name: 'Специалисту и руководству' }))

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith('digest-9'))
    expect(sent).toEqual([
      { path: '/api/v1/digests/both', body: { profile_id: 'profile-1', period_days: 1 } },
    ])
  })

  it('does not start a second build while the issue on screen is still being built', async () => {
    serveBuilds()
    renderPanel({ isBuilding: true })
    await loaded()
    const building = screen.getByRole('button', { name: 'Собираем выпуск' })
    expect(building).toBeDisabled()
    expect(building).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('button', { name: 'Специалисту и руководству' })).toBeDisabled()
  })

  it('shows why the server refused to build', async () => {
    serveBuilds()
    server.use(
      http.post(apiUrl('/digests'), () =>
        HttpResponse.json({ detail: 'Профиль удалён' }, { status: 404 }),
      ),
    )
    const { user, onCreated } = renderPanel()
    await loaded()

    await user.click(screen.getByRole('button', { name: 'Собрать выпуск' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Профиль удалён')
    expect(onCreated).not.toHaveBeenCalled()
  })

  describe('custom dates', () => {
    // Noon in Moscow on 14 October 2026; only the clock is fixed, timers run.
    const NOW = new Date('2026-10-14T09:00:00Z')

    async function openCalendar() {
      vi.useFakeTimers({ toFake: ['Date'] })
      vi.setSystemTime(NOW)
      const sent = serveBuilds()
      const rendered = renderPanel()
      await loaded()
      await rendered.user.click(screen.getByRole('button', { name: 'Свои даты' }))
      const grid = await screen.findByRole('grid')
      const day = (name: RegExp) => within(grid).getByRole('button', { name })
      return { ...rendered, sent, day }
    }

    it('builds an issue for whole days, from the first one’s start to the last one’s end', async () => {
      const { user, sent, day } = await openCalendar()

      await user.click(day(/, 1 октября 2026/))
      await user.click(day(/, 3 октября 2026/))

      // A finished range closes the calendar and names itself on its button.
      await waitFor(() => expect(screen.queryByRole('grid')).toBeNull())
      const custom = screen.getByRole('button', { name: /1 окт.* – 3 окт/ })
      expect(custom).toHaveAttribute('aria-pressed', 'true')
      for (const option of within(screen.getByRole('radiogroup', { name: 'Период' })).getAllByRole(
        'radio',
      ))
        expect(option).not.toBeChecked()

      await user.click(screen.getByRole('button', { name: 'Собрать выпуск' }))

      await waitFor(() => expect(sent).toHaveLength(1))
      expect(sent[0].body).toEqual({
        profile_id: 'profile-1',
        period_days: null,
        period_start: '2026-09-30T21:00:00.000Z',
        period_end: '2026-10-03T20:59:59.999Z',
      })
    })

    it('ends a range that takes in today at the moment of the press', async () => {
      const { user, sent, day } = await openCalendar()

      await user.click(day(/, 13 октября 2026/))
      await user.click(day(/, 14 октября 2026/))
      await waitFor(() => expect(screen.queryByRole('grid')).toBeNull())
      await user.click(screen.getByRole('button', { name: 'Собрать выпуск' }))

      await waitFor(() => expect(sent).toHaveLength(1))
      expect(sent[0].body.period_end).toBe(NOW.toISOString())
    })

    it('offers no day after today', async () => {
      const { day } = await openCalendar()
      expect(day(/, 14 октября 2026/)).not.toHaveAttribute('aria-disabled', 'true')
      expect(day(/, 15 октября 2026/)).toHaveAttribute('aria-disabled', 'true')
      await screen.findByRole('grid')
    })
  })
})
