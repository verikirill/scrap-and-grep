import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { McpKey, NewMcpKey } from '../../lib/api'
import { makeMcpKey } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { McpAccess } from './McpAccess'

// A made-up key: the test checks it is shown once and copied.
const TOKEN = 'sg_live_7f3a9c' // gitleaks:allow

/** The key store on the server: what is created is listed, what is revoked is gone. */
function serveKeys() {
  let keys: McpKey[] = []
  const names: string[] = []
  server.use(
    http.get(apiUrl('/mcp/keys'), () => HttpResponse.json(keys)),
    http.post(apiUrl('/mcp/keys'), async ({ request }) => {
      const { name } = (await request.json()) as { name: string }
      names.push(name)
      const key: NewMcpKey = {
        id: `key-${names.length}`,
        name,
        prefix: 'sg_live',
        created_at: '2026-10-14T09:00:00Z',
        last_used_at: null,
        token: TOKEN,
      }
      keys = [...keys, key]
      return HttpResponse.json(key)
    }),
    http.delete(apiUrl('/mcp/keys/:id'), ({ params }) => {
      keys = keys.filter((key) => key.id !== params.id)
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return names
}

describe('McpAccess', () => {
  it('shows a new key once, with a ready command for each assistant', async () => {
    const names = serveKeys()
    const { user } = renderWithProviders(<McpAccess />)

    await user.type(screen.getByRole('textbox', { name: 'Новый ключ' }), 'Claude на ноутбуке')
    await user.click(screen.getByRole('button', { name: 'Создать ключ' }))

    expect(
      await screen.findByText(/Ключ «Claude на ноутбуке» создан\. Скопируйте его сейчас/),
    ).toBeInTheDocument()
    expect(names).toEqual(['Claude на ноутбуке'])
    // The listed key shows its prefix only.
    expect(await screen.findByText('sg_live…')).toBeInTheDocument()

    const tabs = screen.getByRole('tablist', { name: 'Способ подключения' })
    expect(within(tabs).getByRole('tab', { name: 'Claude Code' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByRole('tabpanel')).toHaveTextContent(
      `claude mcp add --transport http scrap-and-grep http://localhost:3000/api/mcp/`,
    )

    await user.click(within(tabs).getByRole('tab', { name: 'Claude Desktop' }))
    const desktop = screen.getByRole('tabpanel')
    expect(desktop).toHaveTextContent('"mcp-remote"')
    expect(desktop).toHaveTextContent(`Authorization: Bearer ${TOKEN}`)
  })

  it('copies the key to the clipboard', async () => {
    serveKeys()
    const { user } = renderWithProviders(<McpAccess />)
    await user.click(screen.getByRole('button', { name: 'Создать ключ' }))
    await user.click(await screen.findByRole('button', { name: 'Скопировать ключ' }))
    expect(await navigator.clipboard.readText()).toBe(TOKEN)
  })

  it('names an unnamed key after the assistant and hides the token once it is revoked', async () => {
    const names = serveKeys()
    const { user } = renderWithProviders(<McpAccess />)
    await user.click(screen.getByRole('button', { name: 'Создать ключ' }))
    expect(await screen.findByText(/Ключ «Ассистент» создан/)).toBeInTheDocument()
    expect(names).toEqual(['Ассистент'])

    await user.click(await screen.findByRole('button', { name: 'Отозвать ключ «Ассистент»' }))

    expect(await screen.findByText('Ключ «Ассистент» отозван')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText(/Скопируйте его сейчас/)).toBeNull())
    await waitFor(() => expect(screen.queryByText('sg_live…')).toBeNull())
  })

  it('lists the keys with when each was last used', async () => {
    server.use(
      http.get(apiUrl('/mcp/keys'), () =>
        HttpResponse.json([
          makeMcpKey({ id: 'key-1', name: 'Cursor', last_used_at: null }),
          makeMcpKey({
            id: 'key-2',
            name: 'Claude Desktop',
            last_used_at: new Date(Date.now() - 2 * 3_600_000).toISOString(),
          }),
        ]),
      ),
    )
    renderWithProviders(<McpAccess />)

    const cursor = (await screen.findByText('Cursor')).closest('li') as HTMLElement
    expect(within(cursor).getByText(/ещё не использован/)).toBeInTheDocument()
    const desktop = screen.getByText('Claude Desktop').closest('li') as HTMLElement
    expect(within(desktop).getByText(/использован 2 часа назад/)).toBeInTheDocument()
    // Nothing but the prefix of a stored key reaches the page.
    expect(screen.queryByText(/Bearer/)).toBeNull()
  })

  it('says when the browser does not let the key be copied', async () => {
    serveKeys()
    const { user } = renderWithProviders(<McpAccess />)
    await user.click(screen.getByRole('button', { name: 'Создать ключ' }))
    const copy = await screen.findByRole('button', { name: 'Скопировать ключ' })
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('NotAllowedError'))

    await user.click(copy)

    expect(
      await screen.findByText('Не получилось скопировать, выделите текст вручную'),
    ).toBeInTheDocument()
  })

  it('shows why a key was not created, and keeps the name typed', async () => {
    serveKeys()
    server.use(
      http.post(
        apiUrl('/mcp/keys'),
        () => HttpResponse.json({ detail: 'Не больше 10 ключей' }, { status: 409 }),
        { once: true },
      ),
    )
    const { user } = renderWithProviders(<McpAccess />)

    await user.type(screen.getByRole('textbox', { name: 'Новый ключ' }), 'Cursor')
    await user.click(screen.getByRole('button', { name: 'Создать ключ' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Не больше 10 ключей')
    expect(screen.getByRole('textbox', { name: 'Новый ключ' })).toHaveValue('Cursor')
    expect(screen.queryByText(/Скопируйте его сейчас/)).toBeNull()
  })

  it('keeps a key listed when the server refuses to revoke it', async () => {
    server.use(
      http.get(apiUrl('/mcp/keys'), () => HttpResponse.json([makeMcpKey({ name: 'Cursor' })])),
      http.delete(apiUrl('/mcp/keys/:id'), () =>
        HttpResponse.json({ detail: 'Сервис недоступен' }, { status: 503 }),
      ),
    )
    const { user } = renderWithProviders(<McpAccess />)

    await user.click(await screen.findByRole('button', { name: 'Отозвать ключ «Cursor»' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Сервис недоступен')
    expect(screen.getByText('Cursor')).toBeInTheDocument()
    expect(screen.queryByText('Ключ «Cursor» отозван')).toBeNull()
  })
})
