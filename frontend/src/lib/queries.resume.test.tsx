// useResume follows the worker that reads a resume: it asks again every 1.2 s
// while the resume is being read, refreshes what the resume changes once it is
// done, and gives up after five minutes so a stuck worker is not polled forever.
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import type { Resume } from './api'
import { useMe, useResume } from './queries'
import { makeMe, makeResume } from '../test/fixtures'
import { renderHookWithProviders } from '../test/render'
import { apiUrl, server } from '../test/server'

const reading = (createdAt: number): Resume =>
  makeResume({
    status: 'processing',
    facts: null,
    suggestion: null,
    created_at: new Date(createdAt).toISOString(),
  })

/** Answers the resume requests in turn (the last one again and again), counting them. */
function serveResume(answers: Resume[]) {
  const calls = { resume: 0, me: 0 }
  server.use(
    http.get(apiUrl('/resume'), () => {
      calls.resume += 1
      return HttpResponse.json(answers[Math.min(calls.resume, answers.length) - 1])
    }),
    http.get(apiUrl('/auth/me'), () => {
      calls.me += 1
      return HttpResponse.json(makeMe())
    }),
  )
  return calls
}

function renderResume() {
  return renderHookWithProviders(() => ({ resume: useResume(), me: useMe() }))
}

describe('useResume', () => {
  it('asks every 1.2 s while the resume is read, then refreshes the account once', async () => {
    vi.useFakeTimers()
    const now = Date.now()
    const calls = serveResume([reading(now), reading(now), makeResume()])
    const { result } = renderResume()
    await vi.waitFor(() => expect(result.current.resume.data?.status).toBe('processing'))
    await vi.waitFor(() => expect(result.current.me.data).toBeTruthy())
    expect(calls).toEqual({ resume: 1, me: 1 })

    await vi.advanceTimersByTimeAsync(1_200)
    expect(calls.resume).toBe(2)
    await vi.advanceTimersByTimeAsync(1_200)

    await vi.waitFor(() => expect(result.current.resume.data?.status).toBe('ready'))
    // The feed and the account were built without the resume: they are asked again.
    await vi.waitFor(() => expect(calls.me).toBe(2))
    await vi.advanceTimersByTimeAsync(10_000)
    expect(calls.resume).toBe(3)
  })

  it('stops asking after five minutes of reading', async () => {
    vi.useFakeTimers()
    const calls = serveResume([reading(Date.now())])
    const { result } = renderResume()
    await vi.waitFor(() => expect(result.current.resume.data?.status).toBe('processing'))

    await vi.advanceTimersByTimeAsync(5 * 60_000 + 1_200)
    const asked = calls.resume
    expect(asked).toBeGreaterThan(200)
    await vi.advanceTimersByTimeAsync(10_000)

    expect(calls.resume).toBe(asked)
  })

  it('does not poll a resume already stuck when the page opens', async () => {
    vi.useFakeTimers()
    const calls = serveResume([reading(Date.now() - 6 * 60_000)])
    const { result } = renderResume()
    await vi.waitFor(() => expect(result.current.resume.data?.status).toBe('processing'))

    await vi.advanceTimersByTimeAsync(5_000)

    expect(calls.resume).toBe(1)
  })
})
