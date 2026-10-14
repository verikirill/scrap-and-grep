import { render, screen } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setVisible } from '../test/browser'
import { apiUrl, server } from '../test/server'
import type { SeenItem } from './api'
import { useSeen } from './impressions'

type Batch = { items: SeenItem[]; context: string; list_id: string | null }

function Card({
  id,
  position,
  isWatched = true,
}: {
  id: number
  position: number
  isWatched?: boolean
}) {
  const ref = useSeen(id, 'feed', isWatched, { listId: 'snapshot-1', position, slot: 'ranked' })
  return <article ref={ref}>Статья {id}</article>
}

/** The browser tells the page it was hidden or shown again. */
function setTabVisible(isVisible: boolean) {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    value: isVisible ? 'visible' : 'hidden',
  })
  document.dispatchEvent(new Event('visibilitychange'))
}

let batches: Batch[] = []

beforeEach(() => {
  batches = []
  server.use(
    http.post(apiUrl('/impressions'), async ({ request }) => {
      batches.push((await request.json()) as Batch)
      return new HttpResponse(null, { status: 204 })
    }),
  )
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  Reflect.deleteProperty(document, 'visibilityState')
})

describe('useSeen', () => {
  it('reports a card half on screen for most of a second, in one batch per list', async () => {
    render(
      <>
        <Card id={1} position={1} />
        <Card id={2} position={2} />
      </>,
    )
    setVisible(screen.getByText('Статья 1'), 0.6)
    setVisible(screen.getByText('Статья 2'), 1)
    vi.advanceTimersByTime(800)
    expect(batches).toEqual([])

    // The batch leaves after a pause, so a scroll through a list is one request.
    vi.advanceTimersByTime(4000)
    await vi.waitFor(() => expect(batches).toHaveLength(1))
    expect(batches[0]).toEqual({
      context: 'feed',
      list_id: 'snapshot-1',
      items: [
        { article_id: 1, position: 1, slot: 'ranked' },
        { article_id: 2, position: 2, slot: 'ranked' },
      ],
    })
  })

  // A card read in full beside the one under test: once its batch has left,
  // anything the other card would have sent has left too.
  it('does not count a card flicked past', async () => {
    render(
      <>
        <Card id={3} position={1} />
        <Card id={30} position={2} />
      </>,
    )
    const card = screen.getByText('Статья 3')
    setVisible(card, 1)
    setVisible(screen.getByText('Статья 30'), 1)
    vi.advanceTimersByTime(500)
    setVisible(card, 0)
    vi.advanceTimersByTime(10_000)
    await vi.waitFor(() => expect(batches).toHaveLength(1))
    expect(batches[0].items.map((item) => item.article_id)).toEqual([30])
  })

  it('does not watch a card the reader has already marked', async () => {
    render(
      <>
        <Card id={4} position={1} isWatched={false} />
        <Card id={40} position={2} />
      </>,
    )
    setVisible(screen.getByText('Статья 4'), 1)
    setVisible(screen.getByText('Статья 40'), 1)
    vi.advanceTimersByTime(10_000)
    await vi.waitFor(() => expect(batches).toHaveLength(1))
    expect(batches[0].items.map((item) => item.article_id)).toEqual([40])
  })

  it('sends what is waiting when the reader leaves the tab', async () => {
    render(<Card id={5} position={4} />)
    setVisible(screen.getByText('Статья 5'), 1)
    vi.advanceTimersByTime(800)

    setTabVisible(false)

    await vi.waitFor(() => expect(batches).toHaveLength(1))
    expect(batches[0].items).toEqual([{ article_id: 5, position: 4, slot: 'ranked' }])
  })

  it('does not count a card left on screen when the tab was hidden, until the reader is back', async () => {
    render(
      <>
        <Card id={6} position={1} />
        <Card id={60} position={2} />
        <Card id={61} position={3} />
      </>,
    )
    const card = screen.getByText('Статья 6')
    setVisible(screen.getByText('Статья 60'), 1)
    vi.advanceTimersByTime(800)
    setVisible(card, 1)
    vi.advanceTimersByTime(500)

    setTabVisible(false)
    await vi.waitFor(() => expect(batches).toHaveLength(1))
    expect(batches[0].items.map((item) => item.article_id)).toEqual([60])

    // Away for a second, back, and away again after reading another card:
    // the first card's half second before the tab was left still does not count.
    vi.advanceTimersByTime(1000)
    setTabVisible(true)
    setVisible(screen.getByText('Статья 61'), 1)
    vi.advanceTimersByTime(800)
    setTabVisible(false)
    await vi.waitFor(() => expect(batches).toHaveLength(2))
    expect(batches[1].items.map((item) => item.article_id)).toEqual([61])

    // Back on the tab, the browser reports the card still on screen and it is watched anew.
    setTabVisible(true)
    setVisible(card, 1)
    vi.advanceTimersByTime(800 + 4000)
    await vi.waitFor(() => expect(batches).toHaveLength(3))
    expect(batches[2].items).toEqual([{ article_id: 6, position: 1, slot: 'ranked' }])
  })

  it('sends sixty cards at once without waiting, and the rest after the pause', async () => {
    const ids = Array.from({ length: 61 }, (_, index) => 1000 + index)
    render(
      <>
        {ids.map((id, index) => (
          <Card key={id} id={id} position={index + 1} />
        ))}
      </>,
    )
    for (const id of ids) setVisible(screen.getByText(`Статья ${id}`), 1)

    vi.advanceTimersByTime(800)

    await vi.waitFor(() => expect(batches).toHaveLength(1))
    expect(batches[0].items).toHaveLength(60)
    expect(batches[0].items.map((item) => item.article_id)).toEqual(ids.slice(0, 60))
    vi.advanceTimersByTime(4000)
    await vi.waitFor(() => expect(batches).toHaveLength(2))
    expect(batches[1].items.map((item) => item.article_id)).toEqual([1060])
  })
})
