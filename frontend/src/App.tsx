import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MotionConfig } from 'motion/react'
import { Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { Layout } from './components/Layout'
import { ApiError } from './lib/api'
import { DigestPage } from './pages/DigestPage'

// The first screen ships in the main chunk; the other sections load on demand.
const ProfilesPage = lazy(() =>
  import('./pages/ProfilesPage').then((m) => ({ default: m.ProfilesPage })),
)
const SourcesPage = lazy(() =>
  import('./pages/SourcesPage').then((m) => ({ default: m.SourcesPage })),
)
const ComparePage = lazy(() =>
  import('./pages/ComparePage').then((m) => ({ default: m.ComparePage })),
)

const queryClient = new QueryClient({
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

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* Honour the OS "reduce motion" setting for every animation at once. */}
      <MotionConfig reducedMotion="user">
        <BrowserRouter>
          <Layout>
            <Suspense fallback={<div className="skeleton h-64" />}>
              <Routes>
                <Route path="/" element={<DigestPage />} />
                <Route path="/digests/:digestId" element={<DigestPage />} />
                <Route path="/profiles" element={<ProfilesPage />} />
                <Route path="/sources" element={<SourcesPage />} />
                <Route path="/compare" element={<ComparePage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </Layout>
        </BrowserRouter>
      </MotionConfig>
    </QueryClientProvider>
  )
}
