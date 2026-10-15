import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { Bot } from '../../lib/publishing'
import { makeBot } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { BotsPanel } from './BotsPanel'

const TOKEN = '5544332211:AAFq7Lw2Kc9xR4mT8vB1nZ6pY3sD0hJ5Zx9Q'
const SOC_BOT = makeBot({
  id: 'bot-2',
  username: 'soc_news_bot',
  name: 'Новости SOC',
  token_hint: '5544332211:…Zx9Q',
  channels: 0,
})

/** The bots on the server: a token sent comes back as SOC_BOT, a bot removed is gone. */
function serveBots(initial: Bot[]) {
  let bots = initial
  const tokens: string[] = []
  const removed: string[] = []
  server.use(
    http.get(apiUrl('/publishing/bots'), () => HttpResponse.json(bots)),
    http.post(apiUrl('/publishing/bots'), async ({ request }) => {
      const { token } = (await request.json()) as { token: string }
      tokens.push(token)
      bots = [...bots, SOC_BOT]
      return HttpResponse.json(SOC_BOT, { status: 201 })
    }),
    http.delete(apiUrl('/publishing/bots/:id'), ({ params }) => {
      removed.push(String(params.id))
      bots = bots.filter((bot) => bot.id !== params.id)
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return { tokens, removed }
}

/** The row of a bot in the list. */
async function findRow(username: string) {
  await screen.findByText(`@${username}`)
  const row = screen
    .getAllByRole('listitem')
    .find((item) => within(item).queryByText(`@${username}`))
  if (!row) throw new Error(`@${username} is not in a list row`)
  return row
}

const tokenField = () => screen.getByLabelText('Токен бота')
const connectButton = () => screen.getByRole('button', { name: 'Подключить' })

describe('BotsPanel', () => {
  it('lists the bots with the end of their token, their channels and a mark on a failing one', async () => {
    serveBots([
      makeBot(),
      makeBot({
        id: 'bot-3',
        username: 'grid_alerts_bot',
        token_hint: '6677889900:…mW2e',
        status: 'error',
        last_error: 'Telegram отклонил токен: убедитесь, что скопировали его полностью.',
        channels: 0,
      }),
    ])
    renderWithProviders(<BotsPanel />)

    const working = await findRow('energy_infosec_bot')
    expect(within(working).getByText('7412365890:…k3Qw · каналов: 1')).toBeInTheDocument()
    expect(within(working).queryByText('ошибка')).toBeNull()
    const failing = await findRow('grid_alerts_bot')
    expect(within(failing).getByText('ошибка')).toBeInTheDocument()
  })

  it('connects a bot by its token, says so, clears the field and lists the bot', async () => {
    const { tokens } = serveBots([makeBot()])
    const { user } = renderWithProviders(<BotsPanel />)
    await findRow('energy_infosec_bot')

    await user.type(tokenField(), TOKEN)
    await user.click(connectButton())

    expect(
      await screen.findByRole('alertdialog', { name: 'Бот @soc_news_bot подключён' }),
    ).toBeInTheDocument()
    expect(tokens).toEqual([TOKEN])
    expect(tokenField()).toHaveValue('')
    expect(within(await findRow('soc_news_bot')).getByText(/каналов: 0/)).toBeInTheDocument()
  })

  it('sends a token by Enter too', async () => {
    const { tokens } = serveBots([])
    const { user } = renderWithProviders(<BotsPanel />)

    await user.type(tokenField(), `${TOKEN}{Enter}`)

    expect(await findRow('soc_news_bot')).toBeInTheDocument()
    expect(tokens).toEqual([TOKEN])
  })

  it('offers to connect only a token of 20 characters or more, spaces aside', async () => {
    serveBots([])
    const { user } = renderWithProviders(<BotsPanel />)
    expect(connectButton()).toBeDisabled()

    await user.type(tokenField(), `  ${TOKEN.slice(0, 19)}   `)
    expect(connectButton()).toBeDisabled()

    await user.clear(tokenField())
    await user.type(tokenField(), TOKEN.slice(0, 20))
    expect(connectButton()).toBeEnabled()
  })

  it('shows why Telegram refused the token in the panel and keeps what was typed', async () => {
    serveBots([])
    server.use(
      http.post(apiUrl('/publishing/bots'), () =>
        HttpResponse.json(
          { detail: 'Telegram отклонил токен: убедитесь, что скопировали его полностью.' },
          { status: 400 },
        ),
      ),
    )
    const { user } = renderWithProviders(<BotsPanel />)

    await user.type(tokenField(), TOKEN)
    await user.click(connectButton())

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Telegram отклонил токен: убедитесь, что скопировали его полностью.',
    )
    expect(tokenField()).toHaveValue(TOKEN)
    // The form says it; a toast would say it twice.
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('asks before disconnecting a bot with its channels and leaves it when the reader cancels', async () => {
    const { removed } = serveBots([makeBot(), SOC_BOT])
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const { user } = renderWithProviders(<BotsPanel />)

    await user.click(await screen.findByRole('button', { name: 'Отключить @energy_infosec_bot' }))
    expect(confirm).toHaveBeenLastCalledWith('Отключить @energy_infosec_bot и все его каналы?')
    // The second bot is disconnected for real: had the first one gone too, its
    // request would have reached the server before this one.
    await user.click(screen.getByRole('button', { name: 'Отключить @soc_news_bot' }))

    await waitFor(() => expect(screen.queryByText('@soc_news_bot')).toBeNull())
    expect(removed).toEqual(['bot-2'])
    expect(screen.getByText('@energy_infosec_bot')).toBeInTheDocument()
  })

  it('says why in a toast when a bot cannot be disconnected and keeps it listed', async () => {
    serveBots([makeBot()])
    server.use(
      http.delete(apiUrl('/publishing/bots/:id'), () =>
        HttpResponse.json({ detail: 'Бот не найден.' }, { status: 404 }),
      ),
    )
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { user } = renderWithProviders(<BotsPanel />)

    await user.click(await screen.findByRole('button', { name: 'Отключить @energy_infosec_bot' }))

    expect(await screen.findByRole('alertdialog', { name: 'Бот не найден.' })).toBeInTheDocument()
    expect(screen.getByText('@energy_infosec_bot')).toBeInTheDocument()
  })

  it('shows only the bot being disconnected as busy', async () => {
    serveBots([makeBot(), SOC_BOT])
    let answer: () => void = () => {}
    const answered = new Promise<void>((resolve) => {
      answer = resolve
    })
    server.use(
      http.delete(apiUrl('/publishing/bots/:id'), async () => {
        await answered
        return new HttpResponse(null, { status: 204 })
      }),
    )
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { user } = renderWithProviders(<BotsPanel />)

    await user.click(await screen.findByRole('button', { name: 'Отключить @soc_news_bot' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Отключить @soc_news_bot' })).toHaveAttribute(
        'aria-busy',
        'true',
      ),
    )
    expect(
      screen.getByRole('button', { name: 'Отключить @energy_infosec_bot' }),
    ).not.toHaveAttribute('aria-busy')
    answer()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Отключить @soc_news_bot' })).not.toHaveAttribute(
        'aria-busy',
      ),
    )
  })
})
