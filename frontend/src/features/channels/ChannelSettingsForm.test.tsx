import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ChannelSettings } from '../../lib/publishing'
import { makeChannelSettings } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { ChannelSettingsForm } from './ChannelSettingsForm'

const DEFAULTS = makeChannelSettings()

/** The defaults with the schedule changed: the builder replaces whole sections. */
function withSchedule(patch: Partial<ChannelSettings['schedule']>): ChannelSettings {
  return makeChannelSettings({ schedule: { ...DEFAULTS.schedule, ...patch } })
}

function renderForm(initial: ChannelSettings = DEFAULTS, isBusy = false) {
  const onSave = vi.fn<(settings: ChannelSettings) => void>()
  const view = renderWithProviders(
    <ChannelSettingsForm initial={initial} isBusy={isBusy} onSave={onSave} />,
  )
  return { ...view, onSave }
}

const saveButton = () => screen.getByRole('button', { name: 'Сохранить настройки' })
const TIME_HINT = 'Укажите время в формате ЧЧ:ММ (например, 09:30)'

describe('ChannelSettingsForm', () => {
  it('opens on the voice and gives back the channel’s settings untouched', async () => {
    const initial = makeChannelSettings({
      style: { ...DEFAULTS.style, tone: 'neutral', signature: 'Энергетика и ИБ' },
      format: { ...DEFAULTS.format, kind: 'rich' },
      schedule: { ...DEFAULTS.schedule, mode: 'times', times: ['09:00', '13:30'] },
      digest: { ...DEFAULTS.digest, enabled: true },
      approval: 'manual',
    })
    const { user, onSave } = renderForm(initial)

    expect(screen.getByRole('tab', { name: 'Голос' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('radio', { name: 'Сдержанный' })).toBeChecked()
    expect(screen.getByRole('textbox', { name: 'Подпись под постом' })).toHaveValue(
      'Энергетика и ИБ',
    )
    await user.click(screen.getByRole('tab', { name: 'Расписание' }))
    expect(screen.getByRole('radio', { name: 'В заданное время' })).toBeChecked()
    expect(screen.getByRole('button', { name: 'Убрать «13:30»' })).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Модерация' })).toBeChecked()

    await user.click(saveButton())

    expect(onSave).toHaveBeenCalledExactlyOnceWith(initial)
  })

  it('saves the voice: tone, wishes, audience, emoji, signature, length and what the post ends with', async () => {
    const { user, onSave } = renderForm()

    await user.click(screen.getByRole('radio', { name: 'Экспертный' }))
    await user.type(
      screen.getByRole('textbox', { name: /^Пожелания к тексту/ }),
      'На «вы», без жаргона',
    )
    await user.type(
      screen.getByRole('textbox', { name: /^Целевая аудитория/ }),
      'инженеры АСУ ТП подстанций',
    )
    const emoji = screen.getByRole('textbox', { name: 'Эмодзи в начале' })
    await user.clear(emoji)
    await user.type(emoji, '🛡')
    await user.type(screen.getByRole('textbox', { name: 'Подпись под постом' }), 'Радар ИБ')
    await user.click(screen.getByRole('radio', { name: 'Подробно' }))
    await user.click(screen.getByRole('switch', { name: 'Списки' }))
    await user.click(screen.getByRole('switch', { name: 'Реплика' }))
    await user.click(screen.getByRole('switch', { name: 'Хэштеги' }))
    await user.click(saveButton())

    expect(onSave).toHaveBeenCalledExactlyOnceWith({
      ...DEFAULTS,
      style: {
        tone: 'expert',
        instructions: 'На «вы», без жаргона',
        audience: 'инженеры АСУ ТП подстанций',
        emoji: '🛡',
        length: 'long',
        bullets: false,
        ending: false,
        hashtags: true,
        signature: 'Радар ИБ',
      },
    })
  })

  it('keeps an edit made in one section while the reader works in another', async () => {
    const { user, onSave } = renderForm()

    await user.click(screen.getByRole('radio', { name: 'Коротко' }))
    await user.click(screen.getByRole('tab', { name: 'Ссылки' }))
    await user.click(screen.getByRole('radio', { name: 'Кнопкой' }))
    await user.click(screen.getByRole('tab', { name: 'Голос' }))

    expect(screen.getByRole('radio', { name: 'Коротко' })).toBeChecked()
    await user.click(saveButton())
    expect(onSave.mock.calls[0][0]).toMatchObject({
      style: { length: 'short' },
      links: { mode: 'button' },
    })
  })

  it('saves where the source link goes and how it reads', async () => {
    const { user, onSave } = renderForm()
    await user.click(screen.getByRole('tab', { name: 'Ссылки' }))

    await user.click(screen.getByRole('radio', { name: 'Карточкой' }))
    const inline = screen.getByRole('textbox', { name: 'Текст ссылки' })
    await user.clear(inline)
    await user.type(inline, 'источник')
    const button = screen.getByRole('textbox', { name: 'Текст кнопки' })
    await user.clear(button)
    await user.type(button, 'Открыть статью')
    await user.type(
      screen.getByRole('textbox', { name: /^UTM-метки/ }),
      'utm_source=tg&utm_medium=channel',
    )
    await user.click(saveButton())

    expect(onSave).toHaveBeenCalledExactlyOnceWith({
      ...DEFAULTS,
      links: {
        mode: 'preview',
        inline_text: 'источник',
        button_text: 'Открыть статью',
        utm: 'utm_source=tg&utm_medium=channel',
      },
    })
  })

  it('saves the kind of post and how Telegram delivers it', async () => {
    const { user, onSave } = renderForm()
    await user.click(screen.getByRole('tab', { name: 'Формат' }))

    await user.click(screen.getByRole('radio', { name: 'Rich (новый редактор)' }))
    // The article's picture is on by default: switching it off sends no media.
    expect(screen.getByRole('switch', { name: 'Картинка' })).toBeChecked()
    await user.click(screen.getByRole('switch', { name: 'Картинка' }))
    await user.click(screen.getByRole('switch', { name: 'Подпись над картинкой' }))
    await user.click(screen.getByRole('switch', { name: 'Без звука' }))
    await user.click(screen.getByRole('switch', { name: 'Защита' }))
    await user.click(saveButton())

    expect(onSave).toHaveBeenCalledExactlyOnceWith({
      ...DEFAULTS,
      format: {
        kind: 'rich',
        media: 'none',
        caption_above_media: true,
        silent: true,
        protect_content: true,
      },
    })
  })

  it('turns the article’s picture back on', async () => {
    const { user, onSave } = renderForm(
      makeChannelSettings({ format: { ...DEFAULTS.format, media: 'none' } }),
    )
    await user.click(screen.getByRole('tab', { name: 'Формат' }))

    await user.click(screen.getByRole('switch', { name: 'Картинка' }))
    await user.click(saveButton())

    expect(onSave.mock.calls[0][0].format.media).toBe('auto')
  })

  it('asks for the weekly round-up’s day, time and size only once it is on', async () => {
    const { user, onSave } = renderForm()
    await user.click(screen.getByRole('tab', { name: 'Формат' }))
    expect(screen.queryByRole('spinbutton', { name: 'Новостей' })).toBeNull()

    await user.click(screen.getByRole('switch', { name: 'Обзор' }))
    await user.click(screen.getByRole('button', { name: /День: Пт/ }))
    const days = await screen.findByRole('listbox', { name: /^День/ })
    await user.click(within(days).getByRole('option', { name: 'Пн' }))
    // A time field is set whole: typed key by key it passes through invalid values.
    fireEvent.change(screen.getByLabelText('Время'), { target: { value: '10:00' } })
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Новостей' }), {
      target: { value: '7' },
    })
    await user.click(saveButton())

    expect(onSave).toHaveBeenCalledExactlyOnceWith({
      ...DEFAULTS,
      digest: { enabled: true, weekday: 0, time: '10:00', items: 7, days: 7 },
    })
  })

  it('saves posting every N minutes inside a window, on chosen days, with its limits', async () => {
    const { user, onSave } = renderForm()
    await user.click(screen.getByRole('tab', { name: 'Расписание' }))
    expect(screen.queryByText(TIME_HINT)).toBeNull()

    fireEvent.change(screen.getByRole('slider', { name: 'Интервал' }), {
      target: { value: '240' },
    })
    expect(screen.getByText('240 мин')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('С'), { target: { value: '08:00' } })
    fireEvent.change(screen.getByLabelText('До'), { target: { value: '20:30' } })
    const days = screen.getByRole('group', { name: 'Дни' })
    await user.click(within(days).getByRole('button', { name: 'Сб' }))
    await user.click(within(days).getByRole('button', { name: 'Вс' }))
    expect(within(days).getByRole('button', { name: 'Сб' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    fireEvent.change(screen.getByRole('slider', { name: 'Постов в день' }), {
      target: { value: '4' },
    })
    fireEvent.change(screen.getByRole('slider', { name: 'Разброс' }), { target: { value: '10' } })
    expect(screen.getByText('±10 мин')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('slider', { name: 'Заранее' }), { target: { value: '45' } })
    expect(screen.getByText('за 45 мин')).toBeInTheDocument()
    await user.click(screen.getByRole('switch', { name: 'Модерация' }))
    await user.click(saveButton())

    expect(onSave).toHaveBeenCalledExactlyOnceWith({
      ...DEFAULTS,
      schedule: {
        ...DEFAULTS.schedule,
        every_minutes: 240,
        window_start: '08:00',
        window_end: '20:30',
        days: [0, 1, 2, 3, 4],
        max_per_day: 4,
        jitter_minutes: 10,
        prepare_minutes: 45,
      },
      approval: 'manual',
    })
  })

  it('keeps the days in week order, whatever order they are turned back on', async () => {
    const { user, onSave } = renderForm()
    await user.click(screen.getByRole('tab', { name: 'Расписание' }))
    const days = screen.getByRole('group', { name: 'Дни' })
    const day = (name: string) => within(days).getByRole('button', { name })

    await user.click(day('Пн'))
    await user.click(day('Ср'))
    await user.click(day('Ср'))
    await user.click(day('Пн'))

    expect(day('Пн')).toHaveAttribute('aria-pressed', 'true')
    await user.click(saveButton())
    expect(onSave.mock.calls[0][0].schedule.days).toEqual([0, 1, 2, 3, 4, 5, 6])
  })

  it('will not save fixed times until there is at least one', async () => {
    const { user } = renderForm()
    await user.click(screen.getByRole('tab', { name: 'Расписание' }))

    await user.click(screen.getByRole('radio', { name: 'В заданное время' }))

    expect(screen.queryByRole('slider', { name: 'Интервал' })).toBeNull()
    expect(saveButton()).toBeDisabled()
    expect(screen.getByText(TIME_HINT)).toBeInTheDocument()

    await user.type(screen.getByRole('textbox', { name: 'Время постов' }), '09:30{Enter}')

    expect(saveButton()).toBeEnabled()
    expect(screen.queryByText(TIME_HINT)).toBeNull()
  })

  it.each([
    ['an hour without its leading zero', '9:30'],
    ['an hour past 23', '24:00'],
    ['minutes past 59', '12:60'],
    ['a dot for a colon', '09.30'],
  ])('will not save %s (%s) among the fixed times', async (_case, time) => {
    const { user, onSave } = renderForm(withSchedule({ mode: 'times', times: ['13:30'] }))
    await user.click(screen.getByRole('tab', { name: 'Расписание' }))
    expect(saveButton()).toBeEnabled()

    await user.type(screen.getByRole('textbox', { name: 'Время постов' }), `${time}{Enter}`)

    expect(screen.getByRole('button', { name: `Убрать «${time}»` })).toBeInTheDocument()
    expect(saveButton()).toBeDisabled()
    expect(screen.getByText(TIME_HINT)).toBeInTheDocument()
    await user.click(saveButton())
    expect(onSave).not.toHaveBeenCalled()
  })

  it('saves fixed times from midnight to 23:59 in the order they were typed', async () => {
    const { user, onSave } = renderForm()
    await user.click(screen.getByRole('tab', { name: 'Расписание' }))
    await user.click(screen.getByRole('radio', { name: 'В заданное время' }))
    const times = screen.getByRole('textbox', { name: 'Время постов' })

    await user.type(times, '23:59, 00:00{Enter}')
    await user.type(times, '9:5{Enter}')
    expect(saveButton()).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Убрать «9:5»' }))
    await user.type(times, '19:45{Enter}')
    await user.click(saveButton())

    expect(onSave).toHaveBeenCalledExactlyOnceWith({
      ...DEFAULTS,
      schedule: { ...DEFAULTS.schedule, mode: 'times', times: ['23:59', '00:00', '19:45'] },
    })
  })

  it('ignores unfinished fixed times once the channel posts every N minutes again', async () => {
    const { user, onSave } = renderForm(withSchedule({ mode: 'times', times: ['9:30'] }))
    await user.click(screen.getByRole('tab', { name: 'Расписание' }))
    expect(saveButton()).toBeDisabled()

    await user.click(screen.getByRole('radio', { name: 'Каждые N минут' }))

    expect(saveButton()).toBeEnabled()
    expect(screen.queryByText(TIME_HINT)).toBeNull()
    await user.click(saveButton())
    expect(onSave.mock.calls[0][0].schedule).toMatchObject({ mode: 'interval', every_minutes: 180 })
  })

  it('saves how fresh and how relevant a story must be, and how a story is shared between channels', async () => {
    const { user, onSave } = renderForm()
    await user.click(screen.getByRole('tab', { name: 'Отбор' }))
    expect(screen.queryByRole('slider', { name: 'Пауза' })).toBeNull()

    fireEvent.change(screen.getByRole('slider', { name: 'Свежесть' }), { target: { value: '48' } })
    expect(screen.getByText('за 48 ч')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('slider', { name: 'Порог' }), { target: { value: '0.75' } })
    expect(screen.getByText('0.75')).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: 'С интервалом по времени' }))
    fireEvent.change(screen.getByRole('slider', { name: 'Пауза' }), { target: { value: '6' } })
    expect(screen.getByText('6 ч')).toBeInTheDocument()
    await user.click(saveButton())

    expect(onSave).toHaveBeenCalledExactlyOnceWith({
      ...DEFAULTS,
      selection: { freshness_hours: 48, min_score: 0.75, network: 'spread', network_hours: 6 },
    })
  })

  it('shows the save as busy while the channel is being saved', () => {
    renderForm(DEFAULTS, true)
    expect(saveButton()).toHaveAttribute('aria-busy', 'true')
    expect(saveButton()).toBeDisabled()
  })
})
