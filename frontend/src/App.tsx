import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
  keepPreviousData,
} from '@tanstack/react-query'
import { MotionConfig } from 'motion/react'
import { Suspense, useEffect } from 'react'
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Layout } from './components/Layout'
import { RequireAuth } from './components/RequireAuth'
import { ApiError } from './lib/api'
import { keys } from './lib/queries'
import { Toaster } from './components/ui/sonner'
import { TooltipProvider } from './components/ui/tooltip'
import { AuthPage } from './pages/AuthPage'
import { DigestPage } from './pages/DigestPage'
import {
  AccountPage,
  ChannelsPage,
  ComparePage,
  FeedPage,
  ProfilesPage,
  SharePage,
  SourcesPage,
  WelcomePage,
  prefetchAllRoutes,
} from './routes'

/**
 * A 401 from any request means the session ended (expired, signed out in
 * another tab, account deleted). Forget who was signed in; the route guard
 * then shows the sign-in page.
 */
function signOutOnUnauthorized(error: unknown): void {
  if (error instanceof ApiError && error.status === 401) queryClient.setQueryData(keys.me, null)
}

const queryClient: QueryClient = new QueryClient({
  queryCache: new QueryCache({ onError: signOutOnUnauthorized }),
  mutationCache: new MutationCache({ onError: signOutOnUnauthorized }),
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

const fallback = (
  <div className="space-y-4" aria-hidden>
    <div className="skeleton h-9 w-64" />
    <div className="skeleton h-40" />
    <div className="skeleton h-64" />
  </div>
)

/** Pages of a signed-in reader, inside the navigation shell. */
function Shell() {
  const { pathname } = useLocation()
  return (
    <RequireAuth>
      <Layout>
        {/* Keyed by the page: going elsewhere leaves a failed page behind. */}
        <ErrorBoundary key={pathname}>
          <Suspense fallback={fallback}>
            <Outlet />
          </Suspense>
        </ErrorBoundary>
      </Layout>
    </RequireAuth>
  )
}

export default function App() {
  useEffect(prefetchAllRoutes, [])
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={300}>
        {/* Honour the OS "reduce motion" setting for every animation at once. */}
        <MotionConfig reducedMotion="user">
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<AuthPage mode="login" />} />
              <Route path="/register" element={<AuthPage mode="register" />} />
              <Route
                path="/welcome"
                element={
                  <RequireAuth>
                    <ErrorBoundary>
                      <Suspense fallback={fallback}>
                        <WelcomePage />
                      </Suspense>
                    </ErrorBoundary>
                  </RequireAuth>
                }
              />
              <Route element={<Shell />}>
                <Route path="/" element={<DigestPage />} />
                <Route path="/digests/:digestId" element={<DigestPage />} />
                <Route path="/feed" element={<FeedPage />} />
                <Route path="/profiles" element={<ProfilesPage />} />
                <Route path="/sources" element={<SourcesPage />} />
                <Route path="/compare" element={<ComparePage />} />
                <Route path="/channels" element={<ChannelsPage />} />
                <Route path="/account" element={<AccountPage />} />
                <Route path="/share/:token" element={<SharePage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </MotionConfig>
        <Toaster position="bottom-center" />
      </TooltipProvider>
    </QueryClientProvider>
  )
}
