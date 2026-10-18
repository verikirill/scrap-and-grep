import { fireEvent, screen, within } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { FeedItem, ReactionKind } from '../../lib/api'
import { makeFeedItem, makeFeedReason } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { FeedCard } from './FeedCard'

/** A card as the feed keeps it: a mark changes the card's reactions at once. */
function MarkableCard({
  item,
  onReact,
}: {
  item: FeedItem
  onReact: (kind: ReactionKind, isActive: boolean) => void
}) {
  const [reactions, setReactions] = useState(item.reactions)
  return (
    <FeedCard
      item={{ ...item, reactions }}
      index={0}
      listId="snapshot-1"
      onReact={(kind, isActive) => {
        onReact(kind, isActive)
        setReactions((current) =>
          isActive ? [...current, kind] : current.filter((reaction) => reaction !== kind),
        )
      }}
    />
  )
}

function renderCard(item: FeedItem) {
  const onReact = vi.fn<(kind: ReactionKind, isActive: boolean) => void>()
  const view = renderWithProviders(<MarkableCard item={item} onReact={onReact} />)
  return { ...view, onReact }
}

describe('FeedCard', () => {
  it('names the source, its kind and the reasons, and links the article and its original', () => {
    const item = makeFeedItem({ source_category: 'ics' })
    renderCard(item)
    const card = screen.getByRole('article')

    expect(within(card).getByText(item.source_name)).toBeInTheDocument()
    expect(within(card).getByText('АСУ ТП')).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: item.title })).toHaveAttribute(
      'href',
      `/articles/${item.article_id}`,
    )
    expect(
      within(card).getByRole('link', { name: `«${item.title}» на сайте источника` }),
    ).toHaveAttribute('href', item.url)
    expect(within(card).getByText('Интерес «Уязвимости АСУ ТП»')).toBeInTheDocument()
    expect(within(card).queryByText('прочитано')).toBeNull()
  })

  it('marks the article read once, by a click or a middle click, but not by the right button', async () => {
    const item = makeFeedItem()
    const { user, onReact } = renderCard(item)
    const title = screen.getByRole('link', { name: item.title })

    fireEvent(title, new MouseEvent('auxclick', { bubbles: true, button: 2 }))
    expect(onReact).not.toHaveBeenCalled()

    fireEvent(title, new MouseEvent('auxclick', { bubbles: true, button: 1 }))
    expect(onReact).toHaveBeenCalledWith('open', true)
    expect(screen.getByText('прочитано')).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: item.title }))
    await user.click(screen.getByRole('link', { name: `«${item.title}» на сайте источника` }))
    expect(onReact).toHaveBeenCalledTimes(1)
  })

  it('opens what the score is made of, signed where a part corrects it', async () => {
    const item = makeFeedItem({
      score: 0.62,
      parts: { interest: 0.46, fresh: 0.18, avoid: -0.2, collab: 0.001, resume: 0.18 },
    })
    const { user } = renderCard(item)
    const why = screen.getByRole('button', { name: 'Причины подбора' })
    expect(why).toHaveAttribute('aria-expanded', 'false')

    await user.click(why)

    const rows = screen
      .getAllByRole('term')
      .map((term) => [term.textContent, term.nextElementSibling?.textContent])
    expect(rows).toEqual([
      ['Совпадение с интересами', '0.46'],
      ['Близость к опыту из резюме', '0.18'],
      ['Свежесть', '+0.18'],
      ['Близко к тому, что вы скрывали', '-0.20'],
      ['Итоговая оценка', '0.62'],
    ])
  })

  it('has no breakdown for a pick made to explore or an article without parts', () => {
    const { unmount } = renderCard(
      makeFeedItem({
        explore: true,
        reasons: [makeFeedReason({ kind: 'explore', text: 'Новое для вас' })],
      }),
    )
    expect(screen.getByText('Новое для вас')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Причины подбора' })).toBeNull()
    unmount()

    renderCard(makeFeedItem({ parts: {} }))
    expect(screen.queryByRole('button', { name: 'Причины подбора' })).toBeNull()
  })

  it('presses a mark and takes it back with a second press', async () => {
    const item = makeFeedItem()
    const { user, onReact } = renderCard(item)
    const save = screen.getByRole('button', { name: `Сохранить: ${item.title}` })
    expect(save).not.toBePressed()

    await user.click(save)
    expect(save).toBePressed()
    expect(save).toHaveAttribute('title', 'Убрать из сохранённого')
    await user.click(save)

    expect(save).not.toBePressed()
    expect(onReact.mock.calls).toEqual([
      ['save', true],
      ['save', false],
    ])
  })

  it('folds a disliked article into a line that brings it back', async () => {
    const item = makeFeedItem()
    const { user, onReact } = renderCard(item)

    await user.click(screen.getByRole('button', { name: `Меньше такого: ${item.title}` }))

    expect(screen.getByRole('status')).toHaveTextContent(`Меньше похожих: ${item.title}`)
    expect(screen.queryByRole('link', { name: item.title })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Вернуть в ленту' }))

    expect(await screen.findByRole('link', { name: item.title })).toBeInTheDocument()
    expect(onReact.mock.calls).toEqual([
      ['dislike', true],
      ['dislike', false],
    ])
  })
})
