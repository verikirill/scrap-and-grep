// Rendering with what the app root gives every page (src/App.tsx): a query
// client, a router and the toast region. Animations are skipped in setup.ts.
import { Toast } from '@heroui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, renderHook } from '@testing-library/react'
import type { RenderHookOptions } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import type { InitialEntry } from 'react-router'

/** The app's client without retries: a failed request fails the test at once. */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  })
}

type ProviderOptions = {
  /** The address the router starts at; an object carries navigation state too. */
  route?: InitialEntry
  /** The route pattern the element is mounted under, so useParams() works. */
  path?: string
  client?: QueryClient
}

type RenderOptions = ProviderOptions & {
  /** user-event options; with fake timers: { advanceTimers: vi.advanceTimersByTime }. */
  userOptions?: Parameters<typeof userEvent.setup>[0]
}

/** The current address, readable as screen.getByTestId('location'). */
function LocationProbe() {
  const location = useLocation()
  return (
    <span hidden data-testid="location">
      {location.pathname + location.search}
    </span>
  )
}

function makeWrapper({ route = '/', path, client }: ProviderOptions & { client: QueryClient }) {
  return function Providers({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>
          {path ? (
            <Routes>
              <Route path={path} element={children} />
              <Route path="*" element={null} />
            </Routes>
          ) : (
            children
          )}
          <LocationProbe />
        </MemoryRouter>
        <Toast.Provider placement="bottom" />
      </QueryClientProvider>
    )
  }
}

export function renderWithProviders(ui: ReactElement, options: RenderOptions = {}) {
  const client = options.client ?? createTestQueryClient()
  const user = userEvent.setup(options.userOptions)
  const result = render(ui, { wrapper: makeWrapper({ ...options, client }) })
  return { ...result, client, user }
}

export function renderHookWithProviders<Result, Props>(
  hook: (props: Props) => Result,
  options: ProviderOptions & Pick<RenderHookOptions<Props>, 'initialProps'> = {},
) {
  const client = options.client ?? createTestQueryClient()
  const result = renderHook(hook, {
    initialProps: options.initialProps,
    wrapper: makeWrapper({ ...options, client }),
  })
  return { ...result, client }
}
