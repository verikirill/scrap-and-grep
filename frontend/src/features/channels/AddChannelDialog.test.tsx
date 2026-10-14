import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import type { Profile } from '../../lib/api'
import type { Bot } from '../../lib/publishing'
import { makeBot, makeChannel, makeProfile, makeSpec } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { AddChannelDialog } from './AddChannelDialog'

const SOC_BOT = makeBot({ id: 'bot-2', username: 'soc_news_bot', name: 'Новости SOC' })
const LEADERSHIP = makeProfile({
  id: 'profile-2',
  spec: makeSpec({ name: 'Руководитель ИБ', audience: 'management' }),
})

type ChannelRequest = { bot_id: string; chat: string; profile_id: string | null }

/** The reader's bots and profiles, and a server that connects any channel asked for. */
function serveChannelForm({
  bots = [makeBot(), SOC_BOT],
  profiles = [makeProfile(), LEADERSHIP],
}: { bots?: Bot[]; profiles?: Profile[] } = {}) {
  const sent: ChannelRequest[] = []
  server.use(
    http.get(apiUrl('/publishing/bots'), () => HttpResponse.json(bots)),
    http.get(apiUrl('/profiles'), () => HttpResponse.json(profiles)),
    http.post(apiUrl('/publishing/channels'), async ({ request }) => {
      sent.push((await request.json()) as ChannelRequest)
      return HttpResponse.json(makeChannel(), { status: 201 })
    }),
  )
  return sent
}

const addButton = () => screen.getByRole('button', { name: 'Добавить канал' })

/** Open the dialog once the bots have loaded and the button is on. */
async function openDialog(user: ReturnType<typeof renderWithProviders>['user']) {
  await waitFor(() => expect(addButton()).toBeEnabled())
  await user.click(addButton())
  return screen.findByRole('dialog', { name: 'Новый канал' })
}

describe('AddChannelDialog', () => {
  it('is off until a bot is connected, and says so beside the button', async () => {
    serveChannelForm({ bots: [] })
    renderWithProviders(<AddChannelDialog />)

    expect(await screen.findByText('Сначала подключите бота')).toBeInTheDocument()
    expect(addButton()).toBeDisabled()
  })

  it('connects a channel with the first bot and audience, says so and closes', async () => {
    const sent = serveChannelForm()
    const { user } = renderWithProviders(<AddChannelDialog />)
    expect(screen.queryByText('Сначала подключите бота')).toBeNull()

    const dialog = await openDialog(user)
    expect(within(dialog).getByRole('button', { name: /Бот: @energy_infosec_bot/ })).toBeVisible()
    expect(within(dialog).getByRole('button', { name: /Аудитория: Инженер АСУ ТП/ })).toBeVisible()
    const submit = within(dialog).getByRole('button', { name: 'Подключить' })
    expect(submit).toBeDisabled()
    const chat = within(dialog).getByRole('textbox', { name: /^Канал/ })
    expect(chat).toHaveFocus()

    await user.type(chat, '@energy_infosec')
    await user.click(submit)

    expect(
      await screen.findByRole('alertdialog', { name: 'Канал «Энергетика и ИБ» подключён' }),
    ).toBeInTheDocument()
    expect(sent).toEqual([{ bot_id: 'bot-1', chat: '@energy_infosec', profile_id: 'profile-1' }])
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    // The next channel starts from an empty field.
    const next = await openDialog(user)
    expect(within(next).getByRole('textbox', { name: /^Канал/ })).toHaveValue('')
  })

  it('sends the bot and the audience the reader picked', async () => {
    const sent = serveChannelForm()
    const { user } = renderWithProviders(<AddChannelDialog />)
    const dialog = await openDialog(user)

    await user.click(within(dialog).getByRole('button', { name: /Бот: @energy_infosec_bot/ }))
    await user.click(
      within(await screen.findByRole('listbox', { name: /^Бот/ })).getByRole('option', {
        name: '@soc_news_bot',
      }),
    )
    await user.click(within(dialog).getByRole('button', { name: /Аудитория: Инженер АСУ ТП/ }))
    await user.click(
      within(await screen.findByRole('listbox', { name: /^Аудитория/ })).getByRole('option', {
        name: 'Руководитель ИБ',
      }),
    )
    await user.type(within(dialog).getByRole('textbox', { name: /^Канал/ }), 't.me/soc_news')
    await user.click(within(dialog).getByRole('button', { name: 'Подключить' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(sent).toEqual([{ bot_id: 'bot-2', chat: 't.me/soc_news', profile_id: 'profile-2' }])
  })

  it('connects a channel without an audience when the reader has no profile yet', async () => {
    const sent = serveChannelForm({ profiles: [] })
    const { user } = renderWithProviders(<AddChannelDialog />)
    const dialog = await openDialog(user)

    await user.type(within(dialog).getByRole('textbox', { name: /^Канал/ }), '-1002233445566')
    await user.click(within(dialog).getByRole('button', { name: 'Подключить' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(sent).toEqual([{ bot_id: 'bot-1', chat: '-1002233445566', profile_id: null }])
  })

  it('does not connect a channel named by spaces only', async () => {
    serveChannelForm()
    const { user } = renderWithProviders(<AddChannelDialog />)
    const dialog = await openDialog(user)

    await user.type(within(dialog).getByRole('textbox', { name: /^Канал/ }), '   ')

    expect(within(dialog).getByRole('button', { name: 'Подключить' })).toBeDisabled()
  })

  it('shows the refusal in the dialog, not in a toast, and forgets it on the next opening', async () => {
    serveChannelForm()
    server.use(
      http.post(apiUrl('/publishing/channels'), () =>
        HttpResponse.json(
          {
            detail:
              'Бот не видит этот чат. Добавьте бота в канал администратором и повторите попытку.',
          },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderWithProviders(<AddChannelDialog />)
    const dialog = await openDialog(user)

    await user.type(within(dialog).getByRole('textbox', { name: /^Канал/ }), '@energy_infosec')
    await user.click(within(dialog).getByRole('button', { name: 'Подключить' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'Бот не видит этот чат. Добавьте бота в канал администратором и повторите попытку.',
    )
    expect(screen.queryByRole('alertdialog')).toBeNull()

    await user.click(within(dialog).getByRole('button', { name: 'Отмена' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    const next = await openDialog(user)
    // What was typed stays for another try; the old refusal does not.
    expect(within(next).getByRole('textbox', { name: /^Канал/ })).toHaveValue('@energy_infosec')
    expect(within(next).queryByRole('alert')).toBeNull()
  })
})
