// The catalogue of sources: a source and lists of them, how the polls of the
// last day went, what the worker found at an address a reader wants to add, and
// which sources have a picture.
import type { DetectResult, DetectedSource, Source, SourceHealth, api } from '../../lib/api'
import { SOURCES, nth } from './catalog'

function sourceAt(index: number): Source {
  return {
    id: index + 1,
    ...nth(SOURCES, index),
    enabled: true,
    last_fetched_at: '2026-10-14T08:45:00Z',
    last_status: 'ok',
    last_error: null,
    consecutive_failures: 0,
    fetch_method: 'plain',
    fetch_note: null,
    fetch_via_proxy: false,
    can_edit: false,
  }
}

/** SecurityLab.ru, id 1, read by a plain request without trouble. */
export function makeSource(overrides: Partial<Source> = {}): Source {
  return { ...sourceAt(0), ...overrides }
}

/** `count` sources, ids 1 to count: one per category, then one in English. */
export function makeSources(count: number, overrides: Partial<Source> = {}): Source[] {
  return Array.from({ length: count }, (_, index) => ({ ...sourceAt(index), ...overrides }))
}

type FailingSource = SourceHealth['failing'][number]
type SilentSource = SourceHealth['silent'][number]

/** The reader's words for each kind of failure, all of them as the server sends them. */
const ERROR_KINDS: Record<string, string> = {
  dns: 'сайт не найден',
  tls: 'ошибка сертификата',
  refused: 'сайт не пускает бота',
  stub: 'проверка на бота',
  timeout: 'сайт не ответил вовремя',
  connect: 'нет соединения',
  http: 'ошибка на сайте',
  markup: 'сменилась вёрстка',
  unsafe: 'адрес во внутренней сети',
  other: 'другая ошибка',
}

/** Минэнерго России (source 3) timing out since last night. */
export function makeFailingSource(overrides: Partial<FailingSource> = {}): FailingSource {
  return {
    source_id: 3,
    name: 'Минэнерго России',
    failures: 6,
    kind: 'timeout',
    error: 'ReadTimeout: timed out',
    since: '2026-10-13T20:15:00Z',
    ...overrides,
  }
}

/** CISA ICS Advisories (source 6): two days silent, never more than 26 hours before. */
export function makeSilentSource(overrides: Partial<SilentSource> = {}): SilentSource {
  return {
    source_id: 6,
    name: 'CISA ICS Advisories',
    last_article: '2026-10-12T09:30:00Z',
    longest_gap_hours: 26,
    ...overrides,
  }
}

/** A day of polls of a hundred sources, four an hour: one fails, one is silent. */
export function makeSourceHealth(overrides: Partial<SourceHealth> = {}): SourceHealth {
  return {
    hours: 24,
    polls: 9600,
    ok: 9412,
    errors: { timeout: 112, refused: 54, markup: 22 },
    kinds: { ...ERROR_KINDS },
    failing: [makeFailingSource()],
    silent: [makeSilentSource()],
    ...overrides,
  }
}

/** The answer to "what is at this address": the id to ask for the result by. */
export type DetectJob = Awaited<ReturnType<typeof api.detectSource>>

export function makeDetectJob(overrides: Partial<DetectJob> = {}): DetectJob {
  return { request_id: 'f3a91c07d25e4b68a0c4e19b7d3f6a52', ...overrides }
}

/** A feed found at an address, with its latest entries. */
export function makeDetectedSource(overrides: Partial<DetectedSource> = {}): DetectedSource {
  return {
    kind: 'rss',
    address: 'https://habr.com/ru/rss/hubs/scada/articles/all/?fl=ru',
    name: 'Хабр: SCADA',
    site_url: 'https://habr.com/ru/hubs/scada/',
    language: 'ru',
    link_selector: null,
    fetch_method: 'plain',
    fetch_note: null,
    samples: [
      {
        title: 'Как мы сегментировали технологическую сеть подстанции без её остановки',
        url: 'https://habr.com/ru/articles/851204/',
        published_at: '2026-10-13T11:05:00Z',
      },
      {
        title: 'Разбираем GOOSE-сообщения МЭК 61850: что видно в трафике и как это защитить',
        url: 'https://habr.com/ru/articles/850877/',
        published_at: '2026-10-11T08:40:00Z',
      },
    ],
    ...overrides,
  }
}

/** The worker's finished answer. While it looks: { status: 'pending', found: null }. */
export function makeDetectResult(overrides: Partial<DetectResult> = {}): DetectResult {
  return { status: 'done', found: makeDetectedSource(), error: null, ...overrides }
}

/** Source id to the version of its picture, for the sources that have one. */
export type SourceAvatars = Awaited<ReturnType<typeof api.sourceAvatars>>

/** Pictures of sources 1 and 2; jsdom does not load them, so no handler is needed. */
export function makeSourceAvatars(overrides: SourceAvatars = {}): SourceAvatars {
  return { '1': '5e1f0a7c', '2': '9b3d4e21', ...overrides }
}
