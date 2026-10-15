import { QueryClientProvider } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { MotionConfig } from 'motion/react'
import { Suspense, useEffect } from 'react'
import { BrowserRouter, Outlet, Route, Routes, useLocation } from 'react-router'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Layout } from './components/Layout'
import { RequireAuth } from './components/RequireAuth'
import { PageSkeleton } from './components/loading'
import { createQueryClient } from './lib/queryClient'
import { Toast } from '@heroui/react'
import { AuthPage } from './pages/AuthPage'
import { DigestPage } from './pages/DigestPage'
import { NotFoundPage } from './pages/NotFoundPage'
import {
  AccountPage,
  AnalyticsPage,
  ArticlePage,
  ChannelsPage,
  ComparePage,
  FeedPage,
  ProfilesPage,
  SharePage,
  SourcesPage,
  WelcomePage,
  prefetchAllRoutes,
} from './routes'

/** The client of the running app; a test passes one of its own. */
const queryClient = createQueryClient()

// The code of a page is on its way: the page's outline, announced as loading.
const fallback = <PageSkeleton />

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

export default function App({ client = queryClient }: { client?: QueryClient }) {
  useEffect(prefetchAllRoutes, [])
  return (
    <QueryClientProvider client={client}>
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
              <Route path="/articles/:articleId" element={<ArticlePage />} />
              <Route path="/profiles" element={<ProfilesPage />} />
              <Route path="/sources" element={<SourcesPage />} />
              <Route path="/compare" element={<ComparePage />} />
              <Route path="/channels" element={<ChannelsPage />} />
              <Route path="/account" element={<AccountPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/share/:token" element={<SharePage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </MotionConfig>
      {/* Above the phone's navigation bar and the bars that sit on it. */}
      <Toast.Provider placement="bottom" />
    </QueryClientProvider>
  )
}
