import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { ScheduleInput } from '../../lib/api'
import { makeProfile, makeSchedule } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { ScheduleControl } from './ScheduleControl'

const scheduleUrl = apiUrl('/profiles/profile-1/schedule')

describe('ScheduleControl', () => {
  it('offers a schedule starting from the profile’s suggestion and saves the reader’s choice', async () => {
    let sent: ScheduleInput | null = null
    server.use(
      http.put(scheduleUrl, async ({ request }) => {
        sent = (await request.json()) as ScheduleInput
        return HttpResponse.json(
          makeSchedule({ ...sent, timezone: 'Europe/Moscow', next_run_at: '2026-10-14T04:30:00Z' }),
        )
      }),
    )
    const { user } = renderWithProviders(
      <ScheduleControl profile={makeProfile()} schedule={null} />,
    )
    expect(
      screen.getByText('Выпуск по этому профилю может собираться автоматически по расписанию'),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Настроить' }))
    const popover = await screen.findByRole('dialog')
    // The profile suggests weekdays at 09:00.
    expect(within(popover).getByRole('radio', { name: 'По будням' })).toBeChecked()
    expect(within(popover).getByLabelText('Время')).toHaveValue('09:00')
    expect(within(popover).queryByRole('radiogroup', { name: 'День недели' })).toBeNull()

    await user.click(within(popover).getByRole('radio', { name: 'Раз в неделю' }))
    await user.click(within(popover).getByRole('radio', { name: 'Ср, среда' }))
    // A time field is set whole: typed key by key it passes through invalid values.
    fireEvent.change(within(popover).getByLabelText('Время'), { target: { value: '07:30' } })
    await user.click(within(popover).getByRole('button', { name: 'Сохранить' }))

    expect(await screen.findByText(/Следующий выпуск соберётся ср, 14 октября/)).toBeInTheDocument()
    expect(sent).toEqual({
      cadence: 'weekly',
      weekday: 2,
      time: '07:30',
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('sends no weekday for a schedule that is not weekly', async () => {
    let sent: ScheduleInput | null = null
    server.use(
      http.put(scheduleUrl, async ({ request }) => {
        sent = (await request.json()) as ScheduleInput
        return HttpResponse.json(makeSchedule({ ...sent }))
      }),
    )
    const { user } = renderWithProviders(
      <ScheduleControl profile={makeProfile()} schedule={null} />,
    )
    await user.click(screen.getByRole('button', { name: 'Настроить' }))
    const popover = await screen.findByRole('dialog')
    await user.click(within(popover).getByRole('radio', { name: 'Раз в неделю' }))
    await user.click(within(popover).getByRole('radio', { name: 'Каждый день' }))
    await user.click(within(popover).getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(sent).toMatchObject({ cadence: 'daily', weekday: null }))
  })

  it('keeps the schedule’s own time zone and turns the schedule off', async () => {
    let removed = false
    server.use(
      http.delete(scheduleUrl, () => {
        removed = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const schedule = makeSchedule({ timezone: 'Asia/Yekaterinburg' })
    const { user } = renderWithProviders(
      <ScheduleControl profile={makeProfile()} schedule={schedule} />,
    )
    expect(screen.getByText('Собирается сам по будням в 09:00')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Изменить' }))
    const popover = await screen.findByRole('dialog')
    expect(within(popover).getByText(/Время по поясу Asia\/Yekaterinburg/)).toBeInTheDocument()
    await user.click(within(popover).getByRole('button', { name: 'Отключить' }))

    expect(await screen.findByText('Расписание отключено')).toBeInTheDocument()
    expect(removed).toBe(true)
  })

  it('shows why the server refused and keeps the form open', async () => {
    server.use(
      http.put(scheduleUrl, () =>
        HttpResponse.json(
          { detail: [{ loc: ['body', 'time'], msg: 'неверное время' }] },
          { status: 422 },
        ),
      ),
    )
    const { user } = renderWithProviders(
      <ScheduleControl profile={makeProfile()} schedule={null} />,
    )
    await user.click(screen.getByRole('button', { name: 'Настроить' }))
    const popover = await screen.findByRole('dialog')
    await user.click(within(popover).getByRole('button', { name: 'Сохранить' }))
    // FastAPI's validation list reads as "field: message".
    expect(await within(popover).findByRole('alert')).toHaveTextContent('time: неверное время')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('opens on the saved schedule and saves it in its own time zone', async () => {
    let sent: ScheduleInput | null = null
    server.use(
      http.put(scheduleUrl, async ({ request }) => {
        sent = (await request.json()) as ScheduleInput
        return HttpResponse.json(makeSchedule({ ...sent }))
      }),
    )
    const schedule = makeSchedule({
      cadence: 'weekly',
      weekday: 4,
      time: '18:30',
      timezone: 'Asia/Yekaterinburg',
    })
    const { user } = renderWithProviders(
      <ScheduleControl profile={makeProfile()} schedule={schedule} />,
    )
    await user.click(screen.getByRole('button', { name: 'Изменить' }))
    const popover = await screen.findByRole('dialog')
    expect(within(popover).getByRole('radio', { name: 'Раз в неделю' })).toBeChecked()
    expect(within(popover).getByRole('radio', { name: 'Пт, пятница' })).toBeChecked()
    expect(within(popover).getByLabelText('Время')).toHaveValue('18:30')

    await user.click(within(popover).getByRole('button', { name: 'Сохранить' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(sent).toEqual({
      cadence: 'weekly',
      weekday: 4,
      time: '18:30',
      timezone: 'Asia/Yekaterinburg',
    })
  })

  it('forgets an edit the reader walked away from', async () => {
    const { user } = renderWithProviders(
      <ScheduleControl profile={makeProfile()} schedule={null} />,
    )
    await user.click(screen.getByRole('button', { name: 'Настроить' }))
    let popover = await screen.findByRole('dialog')
    await user.click(within(popover).getByRole('radio', { name: 'Каждый день' }))
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    await user.click(screen.getByRole('button', { name: 'Настроить' }))
    popover = await screen.findByRole('dialog')

    expect(within(popover).getByRole('radio', { name: 'По будням' })).toBeChecked()
  })
})
