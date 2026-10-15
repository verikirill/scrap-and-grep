import { act } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { makePost } from '../test/fixtures'
import { renderHookWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import type { Post } from './publishing'
import { usePosts } from './publishingQueries'

/** The queue as the server sees it on each read; what each read asked for is kept. */
function servePosts(answer: (read: number) => Post[]) {
  const asked: string[] = []
  server.use(
    http.get(apiUrl('/publishing/posts'), ({ request }) => {
      asked.push(new URL(request.url).search)
      return HttpResponse.json(answer(asked.length))
    }),
  )
  return asked
}

/** Let `ms` pass and say whether the queue is being read again. */
function after(result: { current: { isFetching: boolean } }, ms: number): boolean {
  act(() => vi.advanceTimersByTime(ms))
  return result.current.isFetching
}

describe('usePosts', () => {
  it('reads a channel’s queue every 3 seconds while a post is on its way, then every 20', async () => {
    vi.useFakeTimers()
    const post = makePost()
    const asked = servePosts((read) => [
      { ...post, status: read === 1 ? 'composing' : read === 2 ? 'sending' : 'sent' },
    ])
    const { result } = renderHookWithProviders(() => usePosts('channel-1'))
    await vi.waitFor(() => expect(result.current.data?.[0].status).toBe('composing'))

    // vi.waitFor moves the clock by its own steps too: the bounds leave room for them.
    expect(after(result, 2_500)).toBe(false)
    expect(after(result, 600)).toBe(true)
    await vi.waitFor(() => expect(result.current.data?.[0].status).toBe('sending'))
    expect(after(result, 3_100)).toBe(true)
    await vi.waitFor(() => expect(result.current.data?.[0].status).toBe('sent'))

    // Nothing moves any more: the next read is twenty seconds away.
    expect(after(result, 15_000)).toBe(false)
    expect(after(result, 5_100)).toBe(true)
    await vi.waitFor(() => expect(asked).toHaveLength(4))
    expect(asked[0]).toBe('?channel_id=channel-1&limit=100')
    await vi.waitFor(() => expect(result.current.isFetching).toBe(false))
  })

  it('reads the queue of all channels without naming one', async () => {
    const asked = servePosts(() => [])
    const { result } = renderHookWithProviders(() => usePosts())

    await vi.waitFor(() => expect(result.current.data).toEqual([]))
    expect(asked).toEqual(['?limit=100'])
  })
})
