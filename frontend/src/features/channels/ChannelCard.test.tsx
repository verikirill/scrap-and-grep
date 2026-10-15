import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { Channel, ChannelSettings } from '../../lib/publishing'
import { useChannels } from '../../lib/publishingQueries'
import {
  makeChannel,
  makeChannelSettings,
  makePost,
  makeProfile,
  makeSpec,
} from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { ChannelCard } from './ChannelCard'

const DEFAULTS = makeChannelSettings()
const LEADERSHIP = makeProfile({
  id: 'profile-2',
  spec: makeSpec({ name: 'Руководитель ИБ', audience: 'management' }),
})

type ChannelPatch = {
  enabled?: boolean
  profile_id?: string | null
  settings?: ChannelSettings
  clear_profile: boolean
}

/** A patch applied the way the API applies it (backend routes/publishing.py). */
function applyPatch(channel: Channel, patch: ChannelPatch): Channel {
  const next = { ...channel }
  if (patch.enabled !== undefined) {
    next.enabled = patch.enabled
    // Turning a channel on again is the owner's way to say "fixed".
    if (patch.enabled) Object.assign(next, { status: 'ok', last_error: null })
  }
  if (patch.clear_profile) next.profile_id = null
  else if (patch.profile_id) next.profile_id = patch.profile_id
  if (patch.settings) next.settings = patch.settings
  next.next_slot = next.enabled && next.profile_id ? '2026-10-14T12:00:00Z' : null
  return next
}

/**
 * One channel on the server and what the card asks of it: patches, removal
 * and new posts. A draft asked for shows in the channel's counters.
 */
function serveChannel(initial: Channel = makeChannel()) {
  let channel: Channel | null = initial
  const patches: ChannelPatch[] = []
  const newPosts: unknown[] = []
  const removed: string[] = []
  server.use(
    http.get(apiUrl('/profiles'), () => HttpResponse.json([makeProfile(), LEADERSHIP])),
    http.get(apiUrl('/publishing/channels'), () => HttpResponse.json(channel ? [channel] : [])),
    http.patch(apiUrl('/publishing/channels/:id'), async ({ request }) => {
      const patch = (await request.json()) as ChannelPatch
      patches.push(patch)
      if (channel) channel = applyPatch(channel, patch)
      return HttpResponse.json(channel)
    }),
    http.delete(apiUrl('/publishing/channels/:id'), ({ params }) => {
      removed.push(String(params.id))
      channel = null
      return new HttpResponse(null, { status: 204 })
    }),
    http.post(apiUrl('/publishing/channels/:id/posts'), async ({ request }) => {
      const body = (await request.json()) as { publish?: boolean }
      newPosts.push(body)
      if (channel && !body.publish) {
        const draft = (channel.counts.draft ?? 0) + 1
        channel = { ...channel, counts: { ...channel.counts, draft } }
      }
      return HttpResponse.json(makePost({ status: 'composing', content: null }), { status: 202 })
    }),
  )
  return { patches, newPosts, removed }
}

/** The card as the page draws it: from the channels the server lists. */
function ListedChannel() {
  const { data: channels } = useChannels()
  if (!channels) return null
  if (channels.length === 0) return <p>Каналов нет</p>
  return <ChannelCard channel={channels[0]} index={0} isSelected={false} onSelect={() => {}} />
}

/** A card of a fixed channel, with the profiles to choose an audience from. */
function renderCard(channel: Channel, isSelected = false, onSelect = () => {}) {
  server.use(http.get(apiUrl('/profiles'), () => HttpResponse.json([makeProfile(), LEADERSHIP])))
  return renderWithProviders(
    <ChannelCard channel={channel} index={0} isSelected={isSelected} onSelect={onSelect} />,
  )
}

/** The audience field names its value once the profiles have loaded. */
const findAudience = (name: string) =>
  screen.findByRole('button', { name: new RegExp(`Аудитория канала: ${name}`) })

const DISABLED_MESSAGE =
  'Публикация отключена: укажите RADAR_SECRET_KEY для хранения токенов ботов.'

describe('ChannelCard', () => {
  it('shows the channel, its bot, how it posts, what it sent and drafted, and its next post', async () => {
    renderCard(makeChannel())

    expect(await findAudience('Инженер АСУ ТП')).toBeInTheDocument()
    expect(screen.getByText('@energy_infosec · бот @energy_infosec_bot')).toBeInTheDocument()
    expect(screen.getByText('обычные посты')).toBeInTheDocument()
    expect(screen.getByText('ссылка в тексте')).toBeInTheDocument()
    expect(screen.getByText('опубликовано: 24')).toBeInTheDocument()
    expect(screen.getByText('черновиков: 2')).toBeInTheDocument()
    expect(screen.queryByText('с модерацией')).toBeNull()
    expect(screen.queryByText('обзор недели')).toBeNull()
    expect(
      screen.getByText('следующий пост 14 окт., 15:00 · каждые 180 мин, 09:00–21:00'),
    ).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Выключить автопостинг' })).toBeChecked()
  })

  it('shows a channel without a public name by its chat id, with its moderation and weekly round-up', async () => {
    renderCard(
      makeChannel({
        username: null,
        settings: makeChannelSettings({
          format: { ...DEFAULTS.format, kind: 'rich' },
          links: { ...DEFAULTS.links, mode: 'button' },
          digest: { ...DEFAULTS.digest, enabled: true },
          approval: 'manual',
        }),
        counts: { sent: 0, queued: 3 },
      }),
    )

    expect(await findAudience('Инженер АСУ ТП')).toBeInTheDocument()
    expect(screen.getByText('id -1002233445566 · бот @energy_infosec_bot')).toBeInTheDocument()
    for (const chip of ['rich-посты', 'кнопка', 'с модерацией', 'обзор недели'])
      expect(screen.getByText(chip)).toBeInTheDocument()
    expect(screen.queryByText(/опубликовано/)).toBeNull()
    expect(screen.queryByText(/черновиков/)).toBeNull()
  })

  it.each([
    [
      'the fixed times of the next posts',
      makeChannel({
        settings: makeChannelSettings({
          schedule: { ...DEFAULTS.schedule, mode: 'times', times: ['09:00', '13:30', '18:00'] },
        }),
      }),
      'следующий пост 14 окт., 15:00 · 09:00, 13:30, 18:00',
    ],
    [
      'that autoposting is off',
      makeChannel({ enabled: false, next_slot: null }),
      'автопостинг выключен',
    ],
    [
      'to choose an audience before autoposting',
      makeChannel({ profile_id: null, next_slot: null }),
      'Выберите аудиторию, чтобы включить автопостинг',
    ],
  ])('says %s', async (_case, channel, text) => {
    renderCard(channel)
    expect(await screen.findByText(text)).toBeInTheDocument()
    await findAudience(channel.profile_id ? 'Инженер АСУ ТП' : 'Без аудитории')
  })

  it('shows why a failing channel does not post', async () => {
    renderCard(
      makeChannel({
        status: 'error',
        last_error:
          'Бот не может публиковать сообщения в канал: Forbidden: bot is not a member of the channel chat',
      }),
    )
    expect(
      await screen.findByText(
        'Бот не может публиковать сообщения в канал: Forbidden: bot is not a member of the channel chat',
      ),
    ).toBeInTheDocument()
    await findAudience('Инженер АСУ ТП')
  })

  it('switches autoposting off and shows the switch as the server keeps it', async () => {
    const { patches } = serveChannel()
    const { user } = renderWithProviders(<ListedChannel />)

    await user.click(await screen.findByRole('switch', { name: 'Выключить автопостинг' }))

    const off = await screen.findByRole('switch', { name: 'Включить автопостинг' })
    expect(off).not.toBeChecked()
    expect(screen.getByText('автопостинг выключен')).toBeInTheDocument()
    expect(patches).toEqual([{ enabled: false, clear_profile: false }])
  })

  it('says why in a toast when the server refuses to switch autoposting, and leaves the switch on', async () => {
    serveChannel()
    server.use(
      http.patch(apiUrl('/publishing/channels/:id'), () =>
        HttpResponse.json({ detail: DISABLED_MESSAGE }, { status: 503 }),
      ),
    )
    const { user } = renderWithProviders(<ListedChannel />)

    await user.click(await screen.findByRole('switch', { name: 'Выключить автопостинг' }))

    expect(await screen.findByRole('alertdialog', { name: DISABLED_MESSAGE })).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Выключить автопостинг' })).toBeChecked()
  })

  it('gives the channel another audience', async () => {
    const { patches } = serveChannel()
    const { user } = renderWithProviders(<ListedChannel />)

    await user.click(await findAudience('Инженер АСУ ТП'))
    const list = await screen.findByRole('listbox', { name: /^Аудитория канала/ })
    await user.click(within(list).getByRole('option', { name: 'Руководитель ИБ' }))

    expect(await findAudience('Руководитель ИБ')).toBeInTheDocument()
    expect(patches).toEqual([{ profile_id: 'profile-2', clear_profile: false }])
  })

  it('takes the audience away by clearing the profile, and then asks for one to post again', async () => {
    const { patches } = serveChannel()
    const { user } = renderWithProviders(<ListedChannel />)

    await user.click(await findAudience('Инженер АСУ ТП'))
    const list = await screen.findByRole('listbox', { name: /^Аудитория канала/ })
    await user.click(within(list).getByRole('option', { name: 'Без аудитории' }))

    expect(
      await screen.findByText('Выберите аудиторию, чтобы включить автопостинг'),
    ).toBeInTheDocument()
    expect(patches).toEqual([{ profile_id: null, clear_profile: true }])
  })

  it('asks for a draft, says it is on its way and counts it on the card', async () => {
    const { newPosts } = serveChannel()
    const { user } = renderWithProviders(<ListedChannel />)

    await user.click(await screen.findByRole('button', { name: 'Создать черновик' }))

    const toast = await screen.findByRole('alertdialog', { name: 'Создаём черновик' })
    expect(toast).toHaveAccessibleDescription('Пост появится в очереди через несколько секунд.')
    expect(await screen.findByText('черновиков: 3')).toBeInTheDocument()
    expect(newPosts).toEqual([{ publish: false }])
  })

  it('asks for a post to go out now and says so', async () => {
    const { newPosts } = serveChannel()
    const { user } = renderWithProviders(<ListedChannel />)

    await user.click(await screen.findByRole('button', { name: 'Опубликовать сейчас' }))

    const toast = await screen.findByRole('alertdialog', { name: 'Публикуем пост' })
    expect(toast).toHaveAccessibleDescription('Пост появится в очереди через несколько секунд.')
    expect(newPosts).toEqual([{ publish: true }])
  })

  it('shows only the pressed button as busy while the post is asked for', async () => {
    serveChannel()
    let answer: () => void = () => {}
    const answered = new Promise<void>((resolve) => {
      answer = resolve
    })
    server.use(
      http.post(apiUrl('/publishing/channels/:id/posts'), async () => {
        await answered
        return HttpResponse.json(makePost({ status: 'composing', content: null }), { status: 202 })
      }),
    )
    const { user } = renderWithProviders(<ListedChannel />)

    await user.click(await screen.findByRole('button', { name: 'Опубликовать сейчас' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Опубликовать сейчас' })).toHaveAttribute(
        'aria-busy',
        'true',
      ),
    )
    expect(screen.getByRole('button', { name: 'Создать черновик' })).not.toHaveAttribute(
      'aria-busy',
    )
    answer()
    expect(await screen.findByRole('alertdialog', { name: 'Публикуем пост' })).toBeInTheDocument()
  })

  it('says why in a toast when no post can be asked for', async () => {
    serveChannel()
    server.use(
      http.post(apiUrl('/publishing/channels/:id/posts'), () =>
        HttpResponse.json(
          { detail: 'Telegram API не отвечает. Попробуйте через минуту.' },
          { status: 502 },
        ),
      ),
    )
    const { user } = renderWithProviders(<ListedChannel />)

    await user.click(await screen.findByRole('button', { name: 'Создать черновик' }))

    expect(
      await screen.findByRole('alertdialog', {
        name: 'Telegram API не отвечает. Попробуйте через минуту.',
      }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('alertdialog', { name: 'Создаём черновик' })).toBeNull()
  })

  it('edits the settings in a sheet, saves them, says so and closes it', async () => {
    const { patches } = serveChannel()
    const { user } = renderWithProviders(<ListedChannel />)

    await user.click(await screen.findByRole('button', { name: 'Настроить' }))
    const sheet = await screen.findByRole('dialog', { name: 'Энергетика и ИБ' })
    expect(sheet).toHaveTextContent('Тон, ссылки, формат, расписание и отбор новостей.')
    await user.click(within(sheet).getByRole('radio', { name: 'Экспертный' }))
    await user.click(within(sheet).getByRole('button', { name: 'Сохранить настройки' }))

    expect(
      await screen.findByRole('alertdialog', { name: 'Настройки сохранены' }),
    ).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(patches).toEqual([
      {
        settings: makeChannelSettings({ style: { ...DEFAULTS.style, tone: 'expert' } }),
        clear_profile: false,
      },
    ])
  })

  it('keeps the settings open when the server refuses them, and says why', async () => {
    serveChannel()
    server.use(
      http.patch(apiUrl('/publishing/channels/:id'), () =>
        HttpResponse.json(
          {
            detail: [
              {
                loc: ['body', 'settings', 'schedule'],
                msg: 'Value error, the window must end after it starts',
              },
            ],
          },
          { status: 422 },
        ),
      ),
    )
    const { user } = renderWithProviders(<ListedChannel />)

    await user.click(await screen.findByRole('button', { name: 'Настроить' }))
    const sheet = await screen.findByRole('dialog', { name: 'Энергетика и ИБ' })
    await user.click(within(sheet).getByRole('tab', { name: 'Расписание' }))
    fireEvent.change(within(sheet).getByLabelText('С'), { target: { value: '21:00' } })
    fireEvent.change(within(sheet).getByLabelText('До'), { target: { value: '09:00' } })
    await user.click(within(sheet).getByRole('button', { name: 'Сохранить настройки' }))

    expect(
      await screen.findByRole('alertdialog', {
        name: 'settings.schedule: Value error, the window must end after it starts',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Энергетика и ИБ' })).toBeInTheDocument()
    expect(within(sheet).getByLabelText('С')).toHaveValue('21:00')
  })

  it('asks before disconnecting the channel and removes it only once confirmed', async () => {
    const { removed } = serveChannel()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const { user } = renderWithProviders(<ListedChannel />)

    const disconnect = await screen.findByRole('button', { name: 'Отключить канал' })
    await user.click(disconnect)
    expect(confirm).toHaveBeenLastCalledWith(
      'Отключить «Энергетика и ИБ»? Его посты удалятся из очереди.',
    )
    await user.click(disconnect)

    expect(await screen.findByText('Каналов нет')).toBeInTheDocument()
    // One request, from the confirmed click: the cancelled one sent nothing.
    expect(removed).toEqual(['channel-1'])
  })

  it('says why in a toast when the channel cannot be disconnected, and keeps it', async () => {
    serveChannel()
    server.use(
      http.delete(apiUrl('/publishing/channels/:id'), () =>
        HttpResponse.json({ detail: 'Канал не найден.' }, { status: 404 }),
      ),
    )
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { user } = renderWithProviders(<ListedChannel />)

    await user.click(await screen.findByRole('button', { name: 'Отключить канал' }))

    expect(await screen.findByRole('alertdialog', { name: 'Канал не найден.' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Настроить' })).toBeInTheDocument()
  })

  it('offers its name as the filter of the queue, pressed while it filters', async () => {
    const onSelect = vi.fn()
    const { user, rerender } = renderCard(makeChannel(), false, onSelect)
    const name = screen.getByRole('button', { name: /Энергетика и ИБ/ })
    expect(name).toHaveAttribute('aria-pressed', 'false')
    expect(name).toHaveAccessibleDescription('Показать посты этого канала')

    await user.click(name)
    expect(onSelect).toHaveBeenCalledOnce()

    rerender(<ChannelCard channel={makeChannel()} index={0} isSelected onSelect={onSelect} />)
    expect(name).toHaveAttribute('aria-pressed', 'true')
    expect(name).toHaveAccessibleDescription('Показать посты всех каналов')
    await findAudience('Инженер АСУ ТП')
  })
})
