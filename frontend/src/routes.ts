import { lazy } from 'react'

/*
 * Pages load on demand, and are fetched ahead of need: all of them once the
 * first screen is idle, and any one the pointer rests on in the navigation.
 * Switching sections then never waits for code, and with navigation in a
 * transition the previous page stays on screen until the next one is ready.
 */
const loaders = {
  '/feed': () => import('./pages/FeedPage'),
  '/profiles': () => import('./pages/ProfilesPage'),
  '/sources': () => import('./pages/SourcesPage'),
  '/compare': () => import('./pages/ComparePage'),
  '/channels': () => import('./pages/ChannelsPage'),
  '/account': () => import('./pages/AccountPage'),
  '/welcome': () => import('./pages/WelcomePage'),
} as const

type Path = keyof typeof loaders

const started = new Set<Path>()

export function prefetchRoute(path: string): void {
  if (!(path in loaders) || started.has(path as Path)) return
  started.add(path as Path)
  void loaders[path as Path]().catch(() => started.delete(path as Path))
}

export function prefetchAllRoutes(): void {
  const run = () => Object.keys(loaders).forEach(prefetchRoute)
  if ('requestIdleCallback' in window) window.requestIdleCallback(run, { timeout: 4000 })
  else setTimeout(run, 1500)
}

export const FeedPage = lazy(() => loaders['/feed']().then((m) => ({ default: m.FeedPage })))
export const ProfilesPage = lazy(() =>
  loaders['/profiles']().then((m) => ({ default: m.ProfilesPage })),
)
export const SourcesPage = lazy(() =>
  loaders['/sources']().then((m) => ({ default: m.SourcesPage })),
)
export const ComparePage = lazy(() =>
  loaders['/compare']().then((m) => ({ default: m.ComparePage })),
)
export const ChannelsPage = lazy(() =>
  loaders['/channels']().then((m) => ({ default: m.ChannelsPage })),
)
export const AccountPage = lazy(() =>
  loaders['/account']().then((m) => ({ default: m.AccountPage })),
)
export const WelcomePage = lazy(() =>
  loaders['/welcome']().then((m) => ({ default: m.WelcomePage })),
)
