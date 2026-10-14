// Digests: an issue as the history lists it, the full issue with its topics and
// entries, a profile's schedule, and delivery by email.
import type {
  Digest,
  DigestItem,
  DigestSchedule,
  DigestSummary,
  MailState,
  Topic,
} from '../../lib/api'
import { nextArticleId } from './ids'
import { makeSpec } from './profiles'

export function makeSchedule(overrides: Partial<DigestSchedule> = {}): DigestSchedule {
  return {
    profile_id: 'profile-1',
    cadence: 'weekdays',
    weekday: null,
    time: '09:00',
    timezone: 'Europe/Moscow',
    next_run_at: '2026-10-15T06:00:00Z',
    last_run_at: null,
    last_digest_id: null,
    ...overrides,
  }
}

export function makeItem(overrides: Partial<DigestItem> = {}): DigestItem {
  const id = nextArticleId()
  return {
    article_id: id,
    url: `https://news.example.org/${id}`,
    title: `Публикация ${id}`,
    headline: `Публикация ${id}`,
    source_name: 'SecurityLab',
    source_category: 'security',
    language: 'ru',
    published_at: '2026-10-13T08:00:00Z',
    score: 0.81,
    retrieval_score: 0.7,
    personal: 0,
    personal_note: '',
    relevance: 0.8,
    interest_id: 'interest-1',
    interest_title: 'Уязвимости АСУ ТП',
    reason: '',
    summary: 'Краткая выжимка публикации.',
    why: '',
    duplicates: [],
    reject_reason: null,
    reading_minutes: null,
    kind: 'news',
    priority: null,
    priority_reason: '',
    fields: [],
    tag_labels: [],
    links: [],
    unsupported: [],
    ours: [],
    attack: null,
    vulnerability: null,
    references: [],
    ...overrides,
  }
}

export function makeTopic(overrides: Partial<Topic> = {}): Topic {
  return { title: 'Уязвимости', overview: '', items: [makeItem()], ...overrides }
}

export function makeSummary(overrides: Partial<DigestSummary> = {}): DigestSummary {
  return {
    origin: 'manual',
    id: 'digest-1',
    profile_id: 'profile-1',
    profile_name: 'Инженер АСУ ТП',
    profile_version: 1,
    audience: 'specialist',
    period_start: '2026-10-12T09:00:00Z',
    period_end: '2026-10-13T09:00:00Z',
    status: 'done',
    stage: 'done',
    progress: 1,
    error: null,
    title: 'Выпуск за сутки',
    stats: { window_total: 300, candidates: 40, selected: 12, sources: 9 },
    created_at: '2026-10-13T09:00:00Z',
    finished_at: '2026-10-13T09:01:00Z',
    ...overrides,
  }
}

export function makeDigest(overrides: Partial<Digest> = {}): Digest {
  return {
    ...makeSummary(),
    profile: makeSpec(),
    highlights: [],
    implications: [],
    manual: null,
    plan: [],
    changes: [],
    numbers: [],
    topics: [makeTopic()],
    rejected: [],
    ...overrides,
  }
}

export function makeMailState(overrides: Partial<MailState> = {}): MailState {
  return { available: true, default_to: 'analyst@example.ru', domains: [], ...overrides }
}
