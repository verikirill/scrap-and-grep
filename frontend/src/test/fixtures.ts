// Builders of API payloads for component tests. Each one returns a complete,
// valid object; a test overrides only the fields its behaviour depends on.
import type {
  Digest,
  DigestItem,
  DigestSchedule,
  DigestSummary,
  MailState,
  Me,
  Meta,
  Profile,
  ProfileSpec,
  Topic,
} from '../lib/api'

export function makeMe(overrides: Partial<Me> = {}): Me {
  return {
    id: 'user-1',
    email: 'analyst@example.ru',
    display_name: 'Анна Петрова',
    is_admin: false,
    is_demo: false,
    profiles: 1,
    resume_status: null,
    avatar_url: null,
    feed_view: 'cards',
    feed_order: 'new',
    folded_sections: [],
    ...overrides,
  }
}

export function makeMeta(overrides: Partial<Meta> = {}): Meta {
  return {
    version: 'test',
    embedding_provider: 'hashing',
    embedding_model: 'hashing-ngrams',
    llm_provider: 'heuristic',
    llm_model: 'heuristic',
    articles: 1200,
    articles_last_day: 40,
    embedded: 1200,
    oldest_article: null,
    newest_article: null,
    sources: 100,
    sources_failing: 0,
    demo_login: true,
    registration_open: true,
    sign_in_required: true,
    open_catalog: false,
    resume_parser: 'builtin',
    resume_formats: ['pdf', 'docx', 'txt', 'md'],
    resume_max_bytes: 8_000_000,
    shorts: false,
    shorts_voice: false,
    short_voices: [],
    ...overrides,
  }
}

export function makeSpec(overrides: Partial<ProfileSpec> = {}): ProfileSpec {
  return {
    name: 'Инженер АСУ ТП',
    role: 'Инженер по защите АСУ ТП',
    interests: [
      {
        id: 'interest-1',
        title: 'Уязвимости АСУ ТП',
        description: 'Уязвимости контроллеров и SCADA',
        keywords: ['SCADA', 'Siemens'],
        weight: 1,
      },
    ],
    exclusions: [],
    min_score: 0.5,
    max_items: 20,
    languages: ['ru', 'en'],
    categories: [],
    audience: 'specialist',
    systems: [],
    ...overrides,
  }
}

export function makeProfile(overrides: Partial<Profile> = {}): Profile {
  return {
    id: 'profile-1',
    version: 1,
    spec: makeSpec(),
    icon: null,
    color: null,
    share_token: null,
    adaptive: false,
    defaults: { period_days: 1, schedule: { cadence: 'weekdays', weekday: null, time: '09:00' } },
    created_at: '2026-10-01T09:00:00Z',
    updated_at: '2026-10-01T09:00:00Z',
    ...overrides,
  }
}

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

let nextArticle = 100

export function makeItem(overrides: Partial<DigestItem> = {}): DigestItem {
  nextArticle += 1
  return {
    article_id: nextArticle,
    url: `https://news.example.org/${nextArticle}`,
    title: `Публикация ${nextArticle}`,
    headline: `Публикация ${nextArticle}`,
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
