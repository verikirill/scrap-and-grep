// The reader's account: who is signed in and what the server offers, the
// settings, the resume and what was read from it, keys for AI assistants over
// MCP, and the reader's picture.
import type {
  McpKey,
  Me,
  Meta,
  NewMcpKey,
  Resume,
  ResumeFacts,
  Settings,
  User,
  api,
} from '../../lib/api'
import { nth } from './catalog'
import { counter } from './ids'
import { makeInterests, makeSpec } from './profiles'

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
    // Readers in tests know the app already: the introduction is a test of its own.
    onboarded_at: '2026-10-01T09:00:00Z',
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

/** What signing in and registering answer: makeMe() without the account's extras. */
export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'user-1',
    email: 'analyst@example.ru',
    display_name: 'Анна Петрова',
    is_admin: false,
    is_demo: false,
    ...overrides,
  }
}

export function makeSettings(overrides: Partial<Settings> = {}): Settings {
  return { feed_view: 'cards', feed_order: 'new', folded_sections: [], ...overrides }
}

export function makeResumeFacts(overrides: Partial<ResumeFacts> = {}): ResumeFacts {
  return {
    headline: 'Ведущий инженер по защите АСУ ТП в электроэнергетике',
    seniority: 'senior',
    summary:
      'Восемь лет в эксплуатации и защите систем диспетчерского управления подстанций: аудит по 187-ФЗ, сегментация технологической сети, внедрение средств обнаружения атак.',
    skills: [
      'SCADA',
      'МЭК 61850',
      'МЭК 60870-5-104',
      'Modbus',
      'Kaspersky Industrial CyberSecurity',
      'PT ISIM',
      'Сегментация сети',
      '187-ФЗ',
    ],
    domains: ['АСУ ТП', 'Электроэнергетика', 'КИИ'],
    by_model: true,
    ...overrides,
  }
}

/** A resume read to the end: its facts and the profile they suggest. While the
 * worker reads it: { status: 'processing', facts: null, suggestion: null }. */
export function makeResume(overrides: Partial<Resume> = {}): Resume {
  return {
    status: 'ready',
    error: null,
    file_format: 'pdf',
    size_bytes: 186_420,
    parser: 'builtin',
    facts: makeResumeFacts(),
    suggestion: makeSpec({
      name: 'По резюме: защита АСУ ТП',
      role: 'Ведущий инженер по защите АСУ ТП в электроэнергетике',
      interests: makeInterests(3),
    }),
    created_at: '2026-10-14T08:00:00Z',
    processed_at: '2026-10-14T08:00:40Z',
    ...overrides,
  }
}

/** Keys show "tng_" and six characters of the token: enough to tell them apart. */
const KEYS: Pick<McpKey, 'name' | 'prefix'>[] = [
  { name: 'Claude Code на ноутбуке', prefix: 'tng_Xa3k9Q' },
  { name: 'Cursor', prefix: 'tng_7fLm2c' },
  { name: 'Codex в CI', prefix: 'tng_Qp0zR4' },
]

const nextKey = counter()

function mcpKeyAt(index: number): McpKey {
  return {
    id: `key-${nextKey()}`,
    ...nth(KEYS, index),
    created_at: '2026-10-10T12:00:00Z',
    last_used_at: '2026-10-14T07:55:00Z',
  }
}

export function makeMcpKey(overrides: Partial<McpKey> = {}): McpKey {
  return { ...mcpKeyAt(0), ...overrides }
}

/** `count` keys of different assistants. */
export function makeMcpKeys(count: number, overrides: Partial<McpKey> = {}): McpKey[] {
  return Array.from({ length: count }, (_, index) => ({ ...mcpKeyAt(index), ...overrides }))
}

/** The answer to creating a key: the only time the whole token is shown. */
export function makeNewMcpKey(overrides: Partial<NewMcpKey> = {}): NewMcpKey {
  return {
    ...makeMcpKey({ last_used_at: null }),
    token: 'tng_Xa3k9QvB2nR7tLw4ZcY8pE1sK6mH0dJ5uF3gA9xT2qV',
    ...overrides,
  }
}

/** The answer to uploading a picture: its address, new for every picture. */
export type Avatar = Awaited<ReturnType<typeof api.uploadAvatar>>

export function makeAvatar(overrides: Partial<Avatar> = {}): Avatar {
  return { avatar_url: '/api/v1/auth/me/avatar?v=1791966600000000', ...overrides }
}
