import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MotionConfig } from 'motion/react'
import { Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router'
import { Layout } from './components/Layout'
import { RequireAuth } from './components/RequireAuth'
import { ApiError } from './lib/api'
import { keys } from './lib/queries'
import { AuthPage } from './pages/AuthPage'
import { DigestPage } from './pages/DigestPage'

// The first screen ships in the main chunk; the other sections load on demand.
const FeedPage = lazy(() => import('./pages/FeedPage').then((m) => ({ default: m.FeedPage })))
const ProfilesPage = lazy(() =>
  import('./pages/ProfilesPage').then((m) => ({ default: m.ProfilesPage })),
)
const SourcesPage = lazy(() =>
  import('./pages/SourcesPage').then((m) => ({ default: m.SourcesPage })),
)
const ComparePage = lazy(() =>
  import('./pages/ComparePage').then((m) => ({ default: m.ComparePage })),
)
const AccountPage = lazy(() =>
  import('./pages/AccountPage').then((m) => ({ default: m.AccountPage })),
)
const WelcomePage = lazy(() =>
  import('./pages/WelcomePage').then((m) => ({ default: m.WelcomePage })),
)

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
      staleTime: 10_000,
      refetchOnWindowFocus: false,
      // A 4xx will not get better on retry; network errors and 5xx might.
      retry: (failures, error) =>
        failures < 2 && !(error instanceof ApiError && error.status >= 400 && error.status < 500),
    },
  },
})

const fallback = <div className="skeleton h-64" />

/** Pages of a signed-in reader, inside the navigation shell. */
function Shell() {
  return (
    <RequireAuth>
      <Layout>
        <Suspense fallback={fallback}>
          <Outlet />
        </Suspense>
      </Layout>
    </RequireAuth>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
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
                  <Suspense fallback={fallback}>
                    <WelcomePage />
                  </Suspense>
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
              <Route path="/account" element={<AccountPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </MotionConfig>
    </QueryClientProvider>
  )
}
