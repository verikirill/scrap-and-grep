import { MutationCache, QueryCache, QueryClient, keepPreviousData } from '@tanstack/react-query'
import { ApiError } from './api'
import { keys } from './queries'

/**
 * A 401 from any request means the session ended (expired, signed out in
 * another tab, account deleted). Forget who was signed in; the route guard
 * then shows the sign-in page.
 */
function signOutOnUnauthorized(client: QueryClient, error: unknown): void {
  if (error instanceof ApiError && error.status === 401) client.setQueryData(keys.me, null)
}

/** The query client of the app, made once by App; a test makes one of its own. */
export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError: (error) => signOutOnUnauthorized(client, error) }),
    mutationCache: new MutationCache({ onError: (error) => signOutOnUnauthorized(client, error) }),
    defaultOptions: {
      queries: {
        // Data stays fresh for half a minute and the previous answer stays on
        // screen while the next loads: switching tabs and filters never blanks a page.
        staleTime: 30_000,
        placeholderData: keepPreviousData,
        refetchOnWindowFocus: false,
        // A 4xx will not get better on retry; network errors and 5xx might.
        retry: (failures, error) =>
          failures < 2 && !(error instanceof ApiError && error.status >= 400 && error.status < 500),
      },
    },
  })
  return client
}
