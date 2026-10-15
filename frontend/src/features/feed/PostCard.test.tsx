import { fireEvent, screen, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { API_BASE } from '../../lib/api'
import type { FeedItem, ReactionKind } from '../../lib/api'
import { makeFeedItem, makeFeedReason } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { apiUrl, server } from '../../test/server'
import { PostCard } from './PostCard'

/** The server's source pictures: source id to the picture's version. */
function serveAvatars(avatars: Record<string, string> = {}) {
  let asked = 0
  server.use(
    http.get(apiUrl('/sources/avatars'), () => {
      asked += 1
      return HttpResponse.json(avatars)
    }),
  )
  return () => asked
}

/** A post with its source's picture looked up, as the feed draws it. */
async function renderPost(item: FeedItem) {
  const asked = serveAvatars()
  const onReact = vi.fn<(kind: ReactionKind, isActive: boolean) => void>()
  const view = renderWithProviders(
    <PostCard
      item={item}
      index={0}
      placement={{ listId: 'snapshot-1', position: 1, slot: 'ranked' }}
      onReact={onReact}
    />,
  )
  await vi.waitFor(() => expect(asked()).toBe(1))
  return { ...view, onReact, post: screen.getByRole('article', { name: item.title }) }
}

describe('PostCard', () => {
  it('shows the article’s picture and leaves a post of text when the site will not give it', async () => {
    const item = makeFeedItem({ has_picture: true })
    const { post } = await renderPost(item)
    // The picture is decoration: the headline is the link for a keyboard and a screen reader.
    const picture = post.querySelector('img')
    expect(picture).toHaveAttribute('src', `${API_BASE}/articles/${item.article_id}/picture`)
    expect(within(post).getAllByRole('link', { name: item.title })).toHaveLength(1)

    fireEvent.error(picture!)

    expect(post.querySelector('img')).toBeNull()
    expect(within(post).getByRole('link', { name: item.title })).toBeInTheDocument()
  })

  it('names one reason and opens the others with the score on request', async () => {
    const item = makeFeedItem({
      reasons: [
        makeFeedReason(),
        makeFeedReason({ kind: 'resume', text: 'Опыт из резюме: SCADA' }),
        makeFeedReason({ kind: 'collab', text: 'Читают коллеги' }),
      ],
    })
    const { user, post } = await renderPost(item)
    const why = within(post).getByRole('button', { name: /Причины подбора статьи/ })
    expect(why).toHaveTextContent('Интерес «Уязвимости АСУ ТП»и ещё 2')
    expect(within(post).queryByText('Опыт из резюме: SCADA')).toBeNull()

    await user.click(why)

    expect(why).toHaveAttribute('aria-expanded', 'true')
    expect(within(post).getByText('Опыт из резюме: SCADA')).toBeInTheDocument()
    expect(within(post).getByText('Читают коллеги')).toBeInTheDocument()
    expect(within(post).getByText('Итоговая оценка')).toBeInTheDocument()
  })

  it('shows a lone reason as text when there is nothing more to explain', async () => {
    const { post } = await renderPost(
      makeFeedItem({ parts: {}, reasons: [makeFeedReason({ text: 'Интерес «Атаки»' })] }),
    )
    expect(within(post).getByText('Интерес «Атаки»')).toBeInTheDocument()
    expect(within(post).queryByRole('button', { name: /Причины подбора/ })).toBeNull()
  })

  it('marks the article read by a middle click and shows it read', async () => {
    const item = makeFeedItem()
    const { post, onReact, rerender } = await renderPost(item)

    fireEvent(
      within(post).getByRole('link', { name: item.title }),
      new MouseEvent('auxclick', { bubbles: true, button: 1 }),
    )
    expect(onReact).toHaveBeenCalledWith('open', true)

    rerender(
      <PostCard
        item={{ ...item, reactions: ['open'] }}
        index={0}
        placement={{ listId: 'snapshot-1', position: 1, slot: 'ranked' }}
        onReact={onReact}
      />,
    )
    expect(screen.getByLabelText('Прочитано')).toBeInTheDocument()
  })

  it('leaves a service line, as a chat does, for an article the reader hid', async () => {
    const item = makeFeedItem({ reactions: ['hide'] })
    const onReact = vi.fn<(kind: ReactionKind, isActive: boolean) => void>()
    const { user } = renderWithProviders(
      <PostCard
        item={item}
        index={0}
        placement={{ listId: 'snapshot-1', position: 1, slot: 'ranked' }}
        onReact={onReact}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent(`Скрыто: ${item.title}`)
    expect(screen.queryByRole('article')).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Вернуть в ленту' }))

    expect(onReact).toHaveBeenCalledWith('hide', false)
  })
})
