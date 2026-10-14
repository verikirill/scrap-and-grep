import { screen, waitFor, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { makeChannel, makePost, makePostContent } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import type { Post } from '../../lib/publishing'
import { PostsPanel } from './PostsPanel'

const CHANNEL = makeChannel()

/** The posts the server holds: requests change them, the next list reads them. */
function servePosts(initial: Post[]) {
  let posts = initial
  const seen: { query: URLSearchParams[]; bodies: unknown[] } = { query: [], bodies: [] }
  server.use(
    http.get(apiUrl('/publishing/posts'), ({ request }) => {
      seen.query.push(new URL(request.url).searchParams)
      return HttpResponse.json(posts)
    }),
    http.patch(apiUrl('/publishing/posts/:id'), async ({ params, request }) => {
      const body = (await request.json()) as { content?: Post['content']; approve?: boolean }
      seen.bodies.push(body)
      posts = posts.map((post) =>
        post.id === params.id
          ? {
              ...post,
              content: body.content ?? post.content,
              status: body.approve ? 'queued' : post.status,
            }
          : post,
      )
      return HttpResponse.json(posts.find((post) => post.id === params.id))
    }),
    http.post(apiUrl('/publishing/posts/:id/publish'), ({ params }) => {
      posts = posts.map((post) => (post.id === params.id ? { ...post, status: 'sending' } : post))
      return HttpResponse.json(posts.find((post) => post.id === params.id))
    }),
    http.delete(apiUrl('/publishing/posts/:id'), ({ params }) => {
      posts = posts.filter((post) => post.id !== params.id)
      return new HttpResponse(null, { status: 204 })
    }),
  )
  return seen
}

function renderPanel(channelId?: string) {
  return renderWithProviders(<PostsPanel channelId={channelId} channels={[CHANNEL]} />)
}

/** The card of the post whose status chip reads so. */
async function card(status: string) {
  const chip = await screen.findByText(status)
  return chip.closest('li') as HTMLElement
}

describe('PostsPanel', () => {
  it('asks for the posts of the channel shown and says when there are none', async () => {
    const seen = servePosts([])
    renderPanel('channel-1')

    expect(await screen.findByText('Постов пока нет')).toBeInTheDocument()
    expect(seen.query[0].get('channel_id')).toBe('channel-1')
    expect(seen.query[0].get('limit')).toBe('100')
  })

  it('offers each post the actions its status allows', async () => {
    servePosts([
      makePost({ status: 'draft' }),
      makePost({ status: 'queued' }),
      makePost({
        status: 'sent',
        sent_at: '2026-10-14T12:00:00Z',
        message_url: 'https://t.me/energy_infosec/412',
      }),
      makePost({ status: 'composing', content: null }),
    ])
    renderPanel()

    const draft = await card('Черновик')
    for (const name of ['Редактировать', 'Одобрить', 'Отправить сейчас', 'Удалить пост']) {
      expect(within(draft).getByRole('button', { name })).toBeInTheDocument()
    }

    const queued = await card('В очереди')
    expect(within(queued).queryByRole('button', { name: 'Одобрить' })).toBeNull()
    expect(within(queued).getByRole('button', { name: 'Отправить сейчас' })).toBeInTheDocument()

    const sent = await card('Опубликован')
    expect(within(sent).queryAllByRole('button')).toEqual([])
    expect(within(sent).getByText(/опубликован/)).toBeInTheDocument()
    expect(within(sent).getByRole('link', { name: 'В Telegram' })).toHaveAttribute(
      'href',
      'https://t.me/energy_infosec/412',
    )

    const composing = await card('Пишется')
    expect(within(composing).getByLabelText('Генерируем текст поста')).toBeInTheDocument()
    expect(
      within(composing)
        .getAllByRole('button')
        .map((button) => button.ariaLabel),
    ).toEqual(['Удалить пост'])
  })

  it('shows why a post failed and what the server found wrong with it', async () => {
    servePosts([
      makePost({
        status: 'failed',
        error: 'Bot API: chat not found',
        problems: ['Текст превышает лимит в 1024 знаков: сейчас 1100.'],
      }),
    ])
    renderPanel()

    const failed = await card('Ошибка')
    expect(within(failed).getByText('Bot API: chat not found')).toBeInTheDocument()
    expect(
      within(failed).getByText('Текст превышает лимит в 1024 знаков: сейчас 1100.'),
    ).toBeInTheDocument()
    expect(within(failed).getByRole('button', { name: 'Редактировать' })).toBeInTheDocument()
  })

  it('does not link to a message or an article address that could run code', async () => {
    servePosts([
      makePost({
        status: 'sent',
        message_url: 'javascript:alert(1)',
        articles: [
          {
            id: 1,
            title: 'Уязвимость',
            url: 'javascript:alert(2)',
            source: 'SecurityLab',
            image_url: null,
          },
        ],
      }),
    ])
    renderPanel()

    await card('Опубликован')
    expect(screen.getByText('В Telegram').closest('a')).not.toHaveAttribute('href')
    expect(screen.getByText('SecurityLab · Уязвимость').closest('a')).not.toHaveAttribute('href')
  })

  it('approves a draft into the queue', async () => {
    const seen = servePosts([makePost({ id: 'post-a', status: 'draft' })])
    const { user } = renderPanel()

    await user.click(within(await card('Черновик')).getByRole('button', { name: 'Одобрить' }))

    expect(await screen.findByText('Пост в очереди')).toBeInTheDocument()
    expect(seen.bodies).toEqual([{ approve: true }])
    expect(await screen.findByText('В очереди')).toBeInTheDocument()
  })

  it('sends a post now and follows it as it goes out', async () => {
    servePosts([makePost({ status: 'queued' })])
    const { user } = renderPanel()

    await user.click(
      within(await card('В очереди')).getByRole('button', { name: 'Отправить сейчас' }),
    )

    expect(await screen.findByText('Отправляем')).toBeInTheDocument()
    const sending = await card('Отправляется')
    expect(within(sending).queryByRole('button', { name: 'Удалить пост' })).toBeNull()
  })

  it('says why the server refused to send a post', async () => {
    servePosts([makePost({ id: 'post-a', status: 'queued' })])
    server.use(
      http.post(
        apiUrl('/publishing/posts/:id/publish'),
        () => HttpResponse.json({ detail: 'Бот не администратор канала' }, { status: 409 }),
        { once: true },
      ),
    )
    const { user } = renderPanel()

    await user.click(
      within(await card('В очереди')).getByRole('button', { name: 'Отправить сейчас' }),
    )

    expect(await screen.findByText('Бот не администратор канала')).toBeInTheDocument()
    expect(screen.getByText('В очереди')).toBeInTheDocument()
  })

  it('removes a deleted post from the list', async () => {
    servePosts([makePost({ status: 'draft' }), makePost({ status: 'failed' })])
    const { user } = renderPanel()

    await user.click(within(await card('Черновик')).getByRole('button', { name: 'Удалить пост' }))

    await waitFor(() => expect(screen.queryByText('Черновик')).toBeNull())
    expect(screen.getByText('Ошибка')).toBeInTheDocument()
  })

  it('edits a post in the editor and saves it as a draft', async () => {
    const seen = servePosts([
      makePost({
        id: 'post-a',
        status: 'draft',
        content: makePostContent({ html: '<p>Текст поста</p>' }),
      }),
    ])
    const { user } = renderPanel()

    await user.click(within(await card('Черновик')).getByRole('button', { name: 'Редактировать' }))
    const dialog = await screen.findByRole('dialog', { name: 'Пост для «Энергетика и ИБ»' })
    await user.click(await within(dialog).findByRole('switch', { name: 'Без звука' }))
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить черновик' }))

    expect(await screen.findByText('Черновик сохранён')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(seen.bodies).toEqual([
      {
        content: expect.objectContaining({ html: '<p>Текст поста</p>', silent: true }),
        approve: false,
      },
    ])
  })

  it('keeps the editor open with the text when saving fails', async () => {
    servePosts([makePost({ status: 'draft' })])
    server.use(
      http.patch(
        apiUrl('/publishing/posts/:id'),
        () => HttpResponse.json({ detail: 'Пост уже отправлен' }, { status: 409 }),
        { once: true },
      ),
    )
    const { user } = renderPanel()

    await user.click(within(await card('Черновик')).getByRole('button', { name: 'Редактировать' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(await within(dialog).findByRole('button', { name: 'Поставить в очередь' }))

    expect(await screen.findByText('Пост уже отправлен')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  describe('a long post', () => {
    const original = globalThis.ResizeObserver
    afterEach(() => {
      globalThis.ResizeObserver = original
    })

    it('is folded to its first screen and unfolds on demand', async () => {
      // jsdom lays nothing out: the post reports a height and is measured at once.
      vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(900)
      globalThis.ResizeObserver = class {
        private readonly callback: ResizeObserverCallback
        constructor(callback: ResizeObserverCallback) {
          this.callback = callback
        }
        observe() {
          this.callback([], this as unknown as ResizeObserver)
        }
        unobserve() {}
        disconnect() {}
      }
      servePosts([makePost({ status: 'draft' })])
      const { user } = renderPanel()

      const unfold = await screen.findByRole('button', { name: 'Показать целиком' })
      expect(unfold).toHaveAttribute('aria-expanded', 'false')
      await user.click(unfold)

      expect(screen.getByRole('button', { name: 'Свернуть' })).toHaveAttribute(
        'aria-expanded',
        'true',
      )
    })
  })
})
