// The API as the tests see it: MSW answers the app's real fetch calls, so a
// test goes through lib/api.ts and the react-query hooks unchanged. Handlers
// here are the quiet defaults; a test adds its own with server.use().
import { HttpResponse, http } from 'msw'
import { setupServer } from 'msw/node'
import { API_BASE } from '../lib/api'
import { makeMe, makeMeta } from './fixtures'

/** The address a handler matches: the app's relative API path, resolved against jsdom's origin. */
export const apiUrl = (path: string) => `${API_BASE}${path}`

export const defaultHandlers = [
  http.get(apiUrl('/auth/me'), () => HttpResponse.json(makeMe())),
  http.get(apiUrl('/meta'), () => HttpResponse.json(makeMeta())),
]

export const server = setupServer(...defaultHandlers)

/** Requests no handler answered during the current test, as "GET /api/v1/x". */
export const unhandled: string[] = []

/** Requests started and not yet answered, and when the last one started. */
const inFlight = new Set<string>()
let lastStart = 0

server.events.on('request:start', ({ requestId }) => {
  inFlight.add(requestId)
  lastStart = Date.now()
})
server.events.on('request:end', ({ requestId }) => inFlight.delete(requestId))
server.events.on('request:unhandled', ({ request, requestId }) => {
  // An unhandled request fails and may never report its end.
  inFlight.delete(requestId)
  const url = new URL(request.url)
  unhandled.push(`${request.method} ${url.pathname}${url.search}`)
})

/**
 * Wait until requests the last screen sent are answered: one fired at the very
 * end of a test must meet that test's handlers, not the next test's.
 */
export async function settleRequests({ quietMs = 20, timeoutMs = 1000 } = {}): Promise<void> {
  const until = Date.now() + timeoutMs
  while (Date.now() < until) {
    if (inFlight.size === 0 && Date.now() - lastStart >= quietMs) return
    await new Promise((resolve) => setTimeout(resolve, 10))
  }
}
