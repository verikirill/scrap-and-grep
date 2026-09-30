// Typed client for the backend API. Shapes mirror backend/src/radar/api/schemas.py
// and backend/src/radar/views.py.

export type SourceCategory = 'security' | 'ics' | 'it' | 'energy' | 'regulator'

export interface Interest {
  id: string
  title: string
  description: string
  keywords: string[]
  weight: number
}

export interface ProfileSpec {
  name: string
  role: string
  interests: Interest[]
  exclusions: string[]
  min_score: number
  max_items: number
  languages: string[]
  categories: SourceCategory[]
}

export interface Profile {
  id: string
  version: number
  spec: ProfileSpec
  created_at: string
  updated_at: string
}

export interface Source {
  id: number
  slug: string
  name: string
  feed_url: string
  site_url: string | null
  category: SourceCategory
  language: string
  enabled: boolean
  fetch_full_text: boolean
  last_fetched_at: string | null
  last_status: string | null
  last_error: string | null
  consecutive_failures: number
  articles: number
  articles_last_day: number
}

export interface SourceCreate {
  name: string
  feed_url: string
  category: SourceCategory
  language: 'ru' | 'en'
  fetch_full_text: boolean
}

export interface Article {
  id: number
  url: string
  title: string
  summary: string
  has_full_text: boolean
  source_id: number
  source_name: string
  source_category: SourceCategory
  language: string
  tags: string[]
  published_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface TimelinePoint {
  day: string
  category: SourceCategory
  count: number
}

export type DigestStatus = 'queued' | 'running' | 'done' | 'failed'

export interface DigestStats {
  window_total?: number
  candidates?: number
  selected?: number
  topics?: number
  sources?: number
  duplicates_merged?: number
  lexical_only?: boolean
  embedding_model?: string
  llm?: string
  graded_by_model?: number
  written_by_model?: number
  degraded?: boolean
  duration_seconds?: number
}

export interface DigestSummary {
  id: string
  profile_id: string | null
  profile_name: string
  profile_version: number
  period_start: string
  period_end: string
  status: DigestStatus
  stage: string | null
  progress: number
  error: string | null
  title: string | null
  stats: DigestStats
  created_at: string
  finished_at: string | null
}

export interface Duplicate {
  title: string
  url: string
  source_name: string
}

export interface DigestItem {
  article_id: number
  url: string
  title: string
  headline: string
  source_name: string
  source_category: SourceCategory
  language: string
  published_at: string
  score: number
  retrieval_score: number
  relevance: number
  interest_id: string | null
  interest_title: string | null
  reason: string
  summary: string
  why: string
  duplicates: Duplicate[]
  reject_reason: string | null
}

export interface Topic {
  title: string
  overview: string
  items: DigestItem[]
}

export interface Digest extends DigestSummary {
  profile: ProfileSpec
  highlights: string[]
  topics: Topic[]
  rejected: DigestItem[]
}

export interface PreviewItem {
  article_id: number
  url: string
  title: string
  source_name: string
  published_at: string
  score: number
  interest_id: string
  interest_title: string | null
  lexical_hit: boolean
  selected: boolean
  reject_reason: string | null
}

export interface Preview {
  window_total: number
  candidates: number
  selected: number
  lexical_only: boolean
  embedding_model: string
  items: PreviewItem[]
}

export interface ScoreChange {
  item: DigestItem
  base_score: number
  delta: number
}

export interface InterestChange {
  id: string
  title: string
  change: 'added' | 'removed' | 'changed'
}

export interface Comparison {
  base_id: string
  other_id: string
  added: DigestItem[]
  removed: DigestItem[]
  kept: ScoreChange[]
  interest_changes: InterestChange[]
  settings_changed: string[]
}

export interface Meta {
  version: string
  embedding_provider: string
  embedding_model: string
  llm_provider: string
  llm_model: string
  articles: number
  articles_last_day: number
  embedded: number
  oldest_article: string | null
  newest_article: string | null
  sources: number
  sources_failing: number
}

export interface ProgressEvent {
  status: DigestStatus
  stage?: string | null
  progress?: number
  done?: number | null
  total?: number | null
  error?: string | null
}

export const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function describe(detail: unknown, status: number): string {
  if (typeof detail === 'string') return detail
  // FastAPI validation errors: [{loc: [...], msg: "..."}]
  if (Array.isArray(detail)) {
    return detail
      .map((entry: { loc?: unknown[]; msg?: string }) => {
        const field = (entry.loc ?? []).filter((part) => part !== 'body').join('.')
        return field ? `${field}: ${entry.msg}` : entry.msg
      })
      .join('; ')
  }
  return `Ошибка ${status}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    })
  } catch {
    throw new ApiError(0, 'Сервис недоступен. Проверьте, что контейнеры запущены.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, describe(body?.detail, response.status))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
})

function query(params: Record<string, string | number | string[] | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '') continue
    for (const item of Array.isArray(value) ? value : [value]) search.append(key, String(item))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  meta: () => request<Meta>('/meta'),

  profiles: () => request<Profile[]>('/profiles'),
  createProfile: (spec: ProfileSpec) => request<Profile>('/profiles', json('POST', spec)),
  updateProfile: (id: string, spec: ProfileSpec) =>
    request<Profile>(`/profiles/${id}`, json('PUT', spec)),
  deleteProfile: (id: string) => request<void>(`/profiles/${id}`, { method: 'DELETE' }),
  preview: (profile: ProfileSpec, periodDays: number, signal?: AbortSignal) =>
    request<Preview>('/selection/preview', {
      ...json('POST', { profile, period_days: periodDays }),
      signal,
    }),

  sources: () => request<Source[]>('/sources'),
  createSource: (source: SourceCreate) => request<Source>('/sources', json('POST', source)),
  updateSource: (id: number, patch: Partial<Pick<Source, 'enabled' | 'fetch_full_text'>>) =>
    request<Source>(`/sources/${id}`, json('PATCH', patch)),
  deleteSource: (id: number) => request<void>(`/sources/${id}`, { method: 'DELETE' }),
  refreshSources: () => request<{ status: string }>('/sources/refresh', { method: 'POST' }),
  refreshSource: (id: number) =>
    request<{ status: string }>(`/sources/${id}/refresh`, { method: 'POST' }),

  articles: (params: {
    q?: string
    category?: string[]
    language?: string[]
    limit: number
    offset: number
  }) => request<Page<Article>>(`/articles${query(params)}`),
  timeline: (days: number) => request<TimelinePoint[]>(`/articles/timeline${query({ days })}`),

  digests: (profileId?: string) =>
    request<DigestSummary[]>(`/digests${query({ profile_id: profileId, limit: 40 })}`),
  digest: (id: string) => request<Digest>(`/digests/${id}`),
  createDigest: (profileId: string, periodDays: number) =>
    request<DigestSummary>(
      '/digests',
      json('POST', { profile_id: profileId, period_days: periodDays }),
    ),
  deleteDigest: (id: string) => request<void>(`/digests/${id}`, { method: 'DELETE' }),
  compare: (base: string, other: string) =>
    request<Comparison>(`/digests/compare${query({ base, other })}`),

  exportUrl: (id: string, format: 'md' | 'docx') => `${API_BASE}/digests/${id}/export.${format}`,
  eventsUrl: (id: string) => `${API_BASE}/digests/${id}/events`,
}
