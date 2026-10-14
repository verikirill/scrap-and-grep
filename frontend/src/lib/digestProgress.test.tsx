import { act } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { eventSources } from '../test/browser'
import { makeDigest, makeSummary } from '../test/fixtures'
import { renderHookWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'
import type { DigestSummary } from './api'
import { useDigest, useDigestProgress } from './queries'

describe('useDigestProgress', () => {
  it('follows a build over server-sent events', () => {
    const { result } = renderHookWithProviders(
      ({ digest }: { digest: DigestSummary }) => useDigestProgress(digest),
      { initialProps: { digest: makeSummary({ status: 'running' }) } },
    )
    expect(eventSources).toHaveLength(1)
    expect(eventSources[0].url).toBe('/api/v1/digests/digest-1/events')
    expect(result.current).toBeNull()

    const event = { status: 'running', stage: 'grade', progress: 0.4, done: 3, total: 10 }
    act(() => eventSources[0].emit('progress', event))
    expect(result.current).toEqual(event)
  })

  it('opens no stream for a finished issue', () => {
    renderHookWithProviders(() => useDigestProgress(makeSummary({ status: 'done' })))
    expect(eventSources).toHaveLength(0)
  })

  it('closes the stream at the end and fetches the finished issue', async () => {
    let reads = 0
    server.use(
      http.get(apiUrl('/digests/digest-1'), () => {
        reads += 1
        return HttpResponse.json(makeDigest({ status: reads === 1 ? 'running' : 'done' }))
      }),
    )
    const { result } = renderHookWithProviders(() => {
      const digest = useDigest('digest-1')
      useDigestProgress(digest.data)
      return digest
    })
    await vi.waitFor(() => expect(result.current.data?.status).toBe('running'))
    const source = eventSources.at(-1)
    act(() => source?.emit('progress', { status: 'done', stage: 'done', progress: 1 }))

    expect(source?.readyState).toBe(2)
    await vi.waitFor(() => expect(result.current.data?.status).toBe('done'))
  })

  it('does not carry one issue’s progress into the next one', () => {
    const { result, rerender } = renderHookWithProviders(
      ({ digest }: { digest: DigestSummary }) => useDigestProgress(digest),
      { initialProps: { digest: makeSummary({ id: 'a', status: 'running' }) } },
    )
    act(() => eventSources[0].emit('progress', { status: 'running', progress: 0.9 }))
    rerender({ digest: makeSummary({ id: 'b', status: 'running' }) })
    expect(result.current).toBeNull()
  })

  it('ignores an event it cannot read', () => {
    const { result } = renderHookWithProviders(() =>
      useDigestProgress(makeSummary({ status: 'running' })),
    )
    act(() => {
      eventSources[0].dispatchEvent(new MessageEvent('progress', { data: 'not json' }))
    })
    expect(result.current).toBeNull()
  })

  it('asks the API where the build stands when the stream breaks', async () => {
    let reads = 0
    server.use(
      http.get(apiUrl('/digests/digest-1'), () => {
        reads += 1
        return HttpResponse.json(makeDigest({ status: reads === 1 ? 'running' : 'done' }))
      }),
      http.get(apiUrl('/digests'), () => HttpResponse.json([makeSummary()])),
    )
    const { result } = renderHookWithProviders(() => {
      const digest = useDigest('digest-1')
      useDigestProgress(digest.data)
      return digest
    })
    await vi.waitFor(() => expect(result.current.data?.status).toBe('running'))

    act(() => eventSources.at(-1)?.fail())

    await vi.waitFor(() => expect(result.current.data?.status).toBe('done'))
  })

  it('closes the stream when the reader leaves the issue', () => {
    const { unmount } = renderHookWithProviders(() =>
      useDigestProgress(makeSummary({ status: 'queued' })),
    )
    expect(eventSources[0].readyState).toBe(1)
    unmount()
    expect(eventSources[0].readyState).toBe(2)
  })
})
