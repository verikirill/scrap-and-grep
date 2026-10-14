// The list of issues and building one: lib/queries.ts hooks of the digest page.
import { act } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { makeSchedule, makeSummary } from '../test/fixtures'
import { createTestQueryClient, renderHookWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import type { DigestSummary } from './api'
import { keys, useCreateDigest, useDeleteDigest, useDigest, useDigests } from './queries'

/** Serve the list, counting reads; the next answer can be changed between them. */
function serveList(first: DigestSummary[]) {
  const state = { reads: 0, list: first, query: '' }
  server.use(
    http.get(apiUrl('/digests'), ({ request }) => {
      state.reads += 1
      state.query = new URL(request.url).search
      return HttpResponse.json(state.list)
    }),
  )
  return state
}

describe('useDigests', () => {
  afterEach(() => vi.useRealTimers())

  it('asks for the last forty issues', async () => {
    const state = serveList([makeSummary()])
    const { result } = renderHookWithProviders(() => useDigests())
    await vi.waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(state.query).toBe('?limit=40')
  })

  it('polls every four seconds while an issue is being built, and stops when it is done', async () => {
    vi.useFakeTimers()
    const state = serveList([makeSummary({ status: 'running' })])
    const { result } = renderHookWithProviders(() => useDigests())
    await vi.waitFor(() => expect(state.reads).toBe(1))

    state.list = [makeSummary({ status: 'done' })]
    await act(() => vi.advanceTimersByTimeAsync(4_000))
    await vi.waitFor(() => expect(result.current.data?.[0].status).toBe('done'))
    expect(state.reads).toBe(2)

    await act(() => vi.advanceTimersByTimeAsync(120_000))
    expect(state.reads).toBe(2)
  })

  it('looks once a minute for an issue a schedule may add', async () => {
    vi.useFakeTimers()
    const state = serveList([makeSummary()])
    // The digest page has the schedules: one profile builds by itself.
    const client = createTestQueryClient()
    client.setQueryData(keys.schedules, [makeSchedule()])
    renderHookWithProviders(() => useDigests(), { client })
    await vi.waitFor(() => expect(state.reads).toBe(1))

    await act(() => vi.advanceTimersByTimeAsync(59_000))
    expect(state.reads).toBe(1)
    await act(() => vi.advanceTimersByTimeAsync(1_000))
    await vi.waitFor(() => expect(state.reads).toBe(2))
  })
})

describe('useDigest', () => {
  afterEach(() => vi.useRealTimers())

  it('polls an issue being built until it is done', async () => {
    vi.useFakeTimers()
    let reads = 0
    server.use(
      http.get(apiUrl('/digests/digest-1'), () => {
        reads += 1
        return HttpResponse.json(makeSummary({ status: reads < 3 ? 'queued' : 'done' }))
      }),
    )
    const { result } = renderHookWithProviders(() => useDigest('digest-1'))
    await vi.waitFor(() => expect(reads).toBe(1))

    await act(() => vi.advanceTimersByTimeAsync(8_000))
    await vi.waitFor(() => expect(result.current.data?.status).toBe('done'))
    await act(() => vi.advanceTimersByTimeAsync(60_000))
    expect(reads).toBe(3)
  })

  it('asks for nothing without an issue', () => {
    const { result } = renderHookWithProviders(() => useDigest(undefined))
    expect(result.current.fetchStatus).toBe('idle')
  })
})

describe('building and deleting', () => {
  it('puts a new issue on top of the list at once', async () => {
    serveList([makeSummary({ id: 'digest-1' })])
    server.use(
      http.post(apiUrl('/digests'), () =>
        HttpResponse.json(makeSummary({ id: 'digest-2', status: 'queued' })),
      ),
    )
    const { result } = renderHookWithProviders(() => ({
      list: useDigests(),
      create: useCreateDigest(),
    }))
    await vi.waitFor(() => expect(result.current.list.data).toHaveLength(1))

    await act(() =>
      result.current.create.mutateAsync({ profileId: 'profile-1', period: { days: 1 } }),
    )

    await vi.waitFor(() =>
      expect(result.current.list.data?.map((item) => item.id)).toEqual(['digest-2', 'digest-1']),
    )
  })

  it('reads the list again after a deletion', async () => {
    const state = serveList([makeSummary({ id: 'digest-2' }), makeSummary({ id: 'digest-1' })])
    server.use(
      http.delete(apiUrl('/digests/digest-2'), () => {
        state.list = [makeSummary({ id: 'digest-1' })]
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const { result } = renderHookWithProviders(() => ({
      list: useDigests(),
      remove: useDeleteDigest(),
    }))
    await vi.waitFor(() => expect(result.current.list.data).toHaveLength(2))

    await act(() => result.current.remove.mutateAsync('digest-2'))

    await vi.waitFor(() =>
      expect(result.current.list.data?.map((item) => item.id)).toEqual(['digest-1']),
    )
  })
})
