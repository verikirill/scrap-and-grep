// Typed client for the backend API. Shapes mirror backend/src/radar/api/schemas.py
// and backend/src/radar/views.py.

import type { CardFieldKey } from './cardFields'
import type { DigestBlockKey } from './digestBlocks'
import type { Membership } from './company'

export type { CardFieldKey } from './cardFields'
export type { DigestBlockKey } from './digestBlocks'

export type SourceCategory = 'security' | 'ics' | 'it' | 'energy' | 'regulator'

export interface Interest {
  id: string
  title: string
  description: string
  keywords: string[]
  weight: number
}

/** Specialists get a card per attack and vulnerability, management a brief with tags. */
export type Audience = 'specialist' | 'management'

export interface ProfileSpec {
  name: string
  role: string
  interests: Interest[]
  exclusions: string[]
  min_score: number
  max_items: number
  languages: string[]
  categories: SourceCategory[]
  audience: Audience
  /** Products the company runs: an entry naming one goes first in its topic. */
  systems?: string[]
  /** Card rows the reader does not want to see; none hidden by default. */
  hidden_card_fields?: CardFieldKey[]
  /** Blocks of the digest page the reader does not want to see; all show by default. */
  hidden_digest_blocks?: DigestBlockKey[]
}

export interface Profile {
  id: string
  version: number
  spec: ProfileSpec
  /** Keys of the app's icon and colour sets (lib/profileLook), or #rrggbb; null until picked. */
  icon: string | null
  color: string | null
  /** The link that hands a copy to another reader; null while nothing is shared. */
  share_token: string | null
  /** Whether the profile follows its reader's marks. */
  adaptive: boolean
  /** The company team the profile follows: the manager's changes reach it until the reader edits it. */
  team_id?: string | null
  /** What the profile's audience suggests: the period of a digest and a schedule. */
  defaults: ProfileDefaults
  created_at: string
  updated_at: string
}

/** A ready profile for a typical role, to start from instead of a blank one. */
export interface ProfileTemplate {
  spec: ProfileSpec
  icon: string | null
  color: string | null
}

export interface ScheduleDefault {
  cadence: Cadence
  /** Monday is 0; weekly schedules only. */
  weekday: number | null
  /** HH:MM, the reader's local time. */
  time: string
}

export interface ProfileDefaults {
  period_days: number
  schedule: ScheduleDefault
}

/** What one interest of a profile has learned from the reader's marks. */
export interface InterestLearning {
  interest_id: string
  title: string
  stated_weight: number
  /** The weight the feed and digests use now. */
  weight: number
  factor: number
  /** How far the interest's meaning moved towards what was liked, 0..1. */
  drift: number
  positives: number
  negatives: number
  skipped: number
}

export interface Suggestion {
  id: string
  kind: 'interest' | 'exclusion'
  source: 'likes' | 'dislikes' | 'similar_readers'
  title: string
  description: string
  keywords: string[]
  articles: { id: number; title: string; url: string; source_name: string }[]
  created_at: string
}

export interface Adaptation {
  adaptive: boolean
  since: string | null
  updated_at: string | null
  interests: InterestLearning[]
  suggestions: Suggestion[]
}

/** A profile someone sent by link, before the reader decides to take it. */
export interface SharedProfile {
  spec: ProfileSpec
  icon: string | null
  color: string | null
  /** The reader's own profile with the same content: their original or an earlier copy. */
  own_id: string | null
}

/**
 * A feed, a public Telegram channel, a site's news page without a feed, a
 * WordPress site's API, or the trending vulnerabilities page of PT.
 */
export type SourceKind = 'rss' | 'telegram' | 'page' | 'wordpress' | 'pt_trending' | 'broadcom'

/** The step of the fetch ladder that reads a source (backend ingest/fetch.py). */
export type FetchMethod = 'plain' | 'browser_headers' | 'impersonate' | 'browser' | 'solver'

export interface Source {
  id: number
  slug: string
  name: string
  kind: SourceKind
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
  /** How the source is read, and why not by a plain request. */
  fetch_method?: FetchMethod | null
  fetch_note?: string | null
  fetch_via_proxy?: boolean
  articles: number
  articles_last_day: number
  /** The reader may change and remove it: an administrator, or its author. */
  can_edit?: boolean
}

export interface DetectedSource {
  kind: 'rss' | 'telegram' | 'page' | 'wordpress'
  /** What is polled: the feed, the page, the API, or a channel's name. */
  address: string
  name: string
  site_url: string | null
  language: string
  link_selector: string | null
  fetch_method: FetchMethod | null
  fetch_note: string | null
  samples: { title: string; url: string; published_at: string | null }[]
}

/** The worker's answer about an address, or that it is still looking. */
export interface DetectResult {
  status: 'pending' | 'done'
  found: DetectedSource | null
  error: string | null
}

type SourceCreateCommon = {
  category: SourceCategory
  language: 'ru' | 'en'
  fetch_full_text: boolean
}

export type SourceCreate =
  | (SourceCreateCommon & { kind: 'rss'; name: string; feed_url: string })
  | (SourceCreateCommon & {
      kind: 'page' | 'wordpress'
      name: string
      /** The news page, or the WordPress posts API. */
      feed_url: string
      site_url?: string
      link_selector?: string
    })
  | (SourceCreateCommon & {
      kind: 'telegram'
      /** "@name" or the channel's t.me address. */
      channel: string
      /** Without one the channel's own title is taken. */
      name?: string
    })

/** How the sources did over the last day: GET /sources/health. */
export interface SourceHealth {
  hours: number
  polls: number
  ok: number
  /** Failed polls by kind, the most frequent first. */
  errors: Record<string, number>
  /** The reader's words for each kind of error. */
  kinds: Record<string, string>
  failing: {
    source_id: number
    name: string
    failures: number
    kind: string | null
    error: string | null
    /** The last poll that went well, within the week polls are kept. */
    since: string | null
  }[]
  /** Silent longer than the longest pause between two of their articles in 30 days. */
  silent: { source_id: number; name: string; last_article: string; longest_gap_hours: number }[]
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
  /** In a search: found by the words of the query, or only by its meaning. */
  match?: 'words' | 'meaning' | null
}

/** A run of text with one set of marks; `href` is always http(s). */
export interface Span {
  text: string
  b?: boolean
  i?: boolean
  code?: boolean
  href?: string
}

export type Block =
  | { type: 'p'; spans: Span[] }
  | { type: 'quote'; spans: Span[] }
  | { type: 'h'; level: 2 | 3 | 4 | 5; text: string }
  | { type: 'list'; ordered: boolean; items: Span[][] }
  | { type: 'code'; text: string }
  | { type: 'image'; id: string; alt?: string }
  | { type: 'table'; head: string[] | null; rows: string[][] }

/** An article opened in the app: its text as blocks, read from its page. */
export interface ArticleRead {
  id: number
  url: string
  title: string
  author: string | null
  source_id: number
  source_name: string
  source_category: SourceCategory
  language: string
  tags: string[]
  published_at: string
  reading_minutes: number | null
  /** False when the page could not be read and the feed's text stands in. */
  complete: boolean
  /** The language of the text itself, told by its letters: en and zh are offered in Russian. */
  text_language: TextLanguage
  blocks: Block[]
}

/** The language an article is written in; other is one the reader does not translate. */
export type TextLanguage = 'ru' | 'en' | 'zh' | 'other'

/**
 * An article in Russian. "original" when it is in Russian already,
 * "unavailable" with the reason when it cannot be translated now: the reader
 * then shows the original.
 */
export interface ArticleTranslation {
  id: number
  status: 'translated' | 'original' | 'unavailable'
  source_language: TextLanguage
  language: 'ru'
  title: string | null
  blocks: Block[] | null
  /** Fragments the model could not translate faithfully, left in the original. */
  kept_original: number
  reason: string | null
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
  personalized?: number
  /** Interests that learned from the reader, as the digest used them. */
  adaptation?: Record<string, { factor: number; drift: number; positives: number }>
  duration_seconds?: number
}

/** A digest's period: days back from now, or two dates. */
export type DigestPeriod = { days: number } | { start: Date; end: Date }

/** A key an AI assistant uses to reach the reader's news over MCP. */
export interface McpKey {
  id: string
  name: string
  /** The first characters, to tell keys apart; the key itself is shown once. */
  prefix: string
  created_at: string
  last_used_at: string | null
}

export interface NewMcpKey extends McpKey {
  token: string
}

export interface DigestSummary {
  /** "schedule" when the reader's schedule ordered it. */
  origin?: 'manual' | 'schedule'
  id: string
  profile_id: string | null
  profile_name: string
  profile_version: number
  /** Who it was written for; a profile built for both audiences gives two digests. */
  audience?: Audience
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
  /** How the source gets past a site that refuses a bot; empty for a plain read. */
  source_read_via?: string
  language: string
  published_at: string
  score: number
  retrieval_score: number
  /** Part of the score that came from the reader's own likes and rejections. */
  personal: number
  personal_note: string
  relevance: number
  interest_id: string | null
  interest_title: string | null
  reason: string
  summary: string
  why: string
  duplicates: Duplicate[]
  reject_reason: string | null
  /** Minutes to read the full text; null until its page has been read. */
  reading_minutes: number | null
  /** What the publication reports, as the organizers' dataset groups it. */
  kind: RecordKind
  /** The dataset's priority of an attack or a vulnerability. */
  priority: Priority | null
  priority_reason: string
  /** The card in the dataset's order; "нет данных" where the article is silent. */
  fields: CardField[]
  /** The card rows the reader's profile hides; already left out of `fields`. */
  hidden_fields?: CardFieldKey[]
  /** Management tags, in words. */
  tag_labels: string[]
  /** Addresses a Telegram post cites. */
  links: string[]
  /** What the check against the article's text took out. */
  unsupported: string[]
  /** The reader's own systems the entry names. */
  ours?: string[]
  /** The attack card as data: indicators, ATT&CK techniques and the flaws it used. */
  attack?: AttackData | null
  /** The vulnerability card as data: its CVE and BDU ids. */
  vulnerability?: VulnerabilityData | null
  /** What the reference bases say of the entry's CVE and BDU ids. */
  references?: VulnerabilityReference[]
}

export type ExploitState = 'in_the_wild' | 'public' | 'none' | 'unknown'

export interface VulnerabilityData {
  ids: string[]
  name: string
  cvss_score: string
  exploit: ExploitState
}

/** One CVE or BDU id in CISA KEV, NVD, the BDU, EPSS and Exploit-DB; dates as YYYY-MM-DD. */
export interface VulnerabilityReference {
  id: string
  kev_added: string | null
  kev_due: string | null
  kev_ransomware: boolean
  bdu_id: string
  bdu_cvss: string
  bdu_in_attacks: boolean
  nvd_cvss: string
  nvd_exploitation: string
  nvd_published?: string | null
  exploit_published?: string | null
  epss: number | null
  exploits: string[]
}

export interface AttackTechnique {
  id: string
  name: string
}

export interface AttackData {
  /** Addresses, domains and hashes the article printed, defanged. */
  indicators: string[]
  techniques: AttackTechnique[]
  vulnerabilities: string[]
}

/** The digest's machine-readable exports: a report, and threat intelligence for a SOC. */
export type ExportFormat = 'md' | 'docx' | 'stix.json' | 'misp.json' | 'csv'

export interface AskCitation {
  number: number
  headline: string
  url: string
}

export interface AskAnswer {
  answer: string
  citations: AskCitation[]
  /** False when the digest's entries do not hold the answer. */
  is_in_digest: boolean
}

export type RecordKind = 'attack' | 'vulnerability' | 'news'
export type Priority = 'high' | 'medium' | 'low'

export interface CardField {
  key: CardFieldKey
  label: string
  value: string
}

export interface Topic {
  title: string
  overview: string
  items: DigestItem[]
}

export interface Digest extends DigestSummary {
  profile: ProfileSpec
  highlights: string[]
  /** Management only: what the period means for the company. */
  implications: string[]
  /** The handwork the issue spares, by the rule it states. */
  manual?: ManualWork | null
  /** Specialist: the high-priority entries as a checklist for the shift. */
  plan?: PlanEntry[]
  /** Specialist: what became known about vulnerabilities of earlier issues. */
  changes?: VulnerabilityChange[]
  /** Management: entries per dataset tag, beside the previous issue's. */
  numbers?: TagCount[]
  numbers_title?: string
  topics: Topic[]
  rejected: DigestItem[]
  /** The blocks around the entries the reader's profile hides now. */
  hidden_digest_blocks?: DigestBlockKey[]
}

export interface ManualWork {
  headlines: number
  entries: number
  minutes: number
  seconds: number | null
  /** The analyst's measured pace the minutes are counted at. */
  seconds_per_headline: number
  minutes_per_entry: number
}

export interface PlanEntry {
  headline: string
  url: string
  kind: RecordKind
  steps: string[]
  facts: string[]
  /** The reader ticked it off; kept with the digest on the server. */
  done: boolean
}

export interface VulnerabilityChange {
  id: string
  headline: string
  url: string
  since: string
  what: string[]
}

export interface TagCount {
  tag: string
  label: string
  count: number
  before: number | null
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
  demo_login: boolean
  /** The sign-in page enters the shared reader and administrator accounts with one click. */
  preset_login: boolean
  registration_open: boolean
  /** False: a visitor without a session is entered as a guest, no sign-in screen. */
  sign_in_required: boolean
  /** Every reader may add sources, not only the administrator. */
  open_catalog: boolean
  resume_parser: 'builtin' | 'docling'
  resume_formats: string[]
  resume_max_bytes: number
  /** Short videos of digests can be ordered on this server. */
  shorts: boolean
  /** ...and they get a voice; without it captions carry the story. */
  shorts_voice: boolean
  /** Voices a reader can pick; empty when there is no choice to give. */
  short_voices: VoiceOption[]
  /** What speaks: the voice service (Qwen3-TTS) or Yandex SpeechKit; null without a voice. */
  voice_engine?: VoiceEngine | null
}

export type VoiceEngine = 'qwen3-tts' | 'yandex'

export interface VoiceOption {
  id: string
  title: string
  default: boolean
  /** Whether a few seconds of the voice can be heard before picking it. */
  sample?: boolean
}

export type VideoStage = 'script' | 'voice' | 'render'

export interface Video {
  status: DigestStatus
  stage: VideoStage | null
  progress: number
  error: string | null
  /** "qwen3-tts:<speaker>" or "yandex:<voice>", or null for a silent video with captions. */
  voice: string | null
  /** The voice the reader picked, one of Meta.short_voices. */
  requested_voice: string | null
  by_model: boolean
  duration_ms: number | null
  size_bytes: number | null
  created_at: string
  finished_at: string | null
  /** Where to watch it; set once it is done. */
  url: string | null
}

export interface User {
  id: string
  email: string
  display_name: string
  is_admin: boolean
  is_demo: boolean
  /** A shared account entered with one click: many people use it, nobody deletes it. */
  is_shared: boolean
}

/** The shared accounts behind the one-click buttons of the sign-in page. */
export type SharedAccountKey = 'reader' | 'admin'

/** The nine ready pictures, served from /brand/avatars/<name>.webp. */
export type AvatarPreset =
  | 'green'
  | 'blue'
  | 'yellow'
  | 'orange'
  | 'teal'
  | 'purple'
  | 'red'
  | 'sky'
  | 'grey'

/** What the account shows as its picture: the uploaded photo wins over the preset. */
export interface AvatarChoice {
  avatar_url: string | null
  avatar_preset: AvatarPreset
}

export interface Me extends User {
  profiles: number
  resume_status: ResumeStatus | null
  /** The reader's picture; a new one gets a new address. */
  avatar_url: string | null
  /** The ready picture shown while there is no uploaded one. */
  avatar_preset: AvatarPreset
  feed_view: FeedView
  feed_order: FeedOrder
  /** Digest sections the reader keeps folded, by title. */
  folded_sections?: string[]
  /** The menu sections by path, in the order the reader dragged them; empty keeps the app's. */
  nav_order?: string[]
  /** When the first-run introduction was finished or skipped; null until then. */
  onboarded_at: string | null
  /** The company space the account manages or was made for; null for neither. */
  company?: Membership | null
}

/** How the feed looks: cards with the reasons in full, or posts as in a Telegram channel. */
export type FeedView = 'cards' | 'telegram'

/** Which order the feed is in: the relevant articles newest first, or by score. */
export type FeedOrder = 'new' | 'top'

export interface Settings {
  feed_view: FeedView
  feed_order: FeedOrder
  folded_sections: string[]
  nav_order: string[]
}

/** Articles that arrived after the feed on screen was ranked and pass the reader's interests. */
export interface FeedFresh {
  fresh: number
}

export type Cadence = 'daily' | 'weekdays' | 'weekly'

/** A profile's digest built by itself, at the reader's local time. */
export interface DigestSchedule {
  profile_id: string
  cadence: Cadence
  /** Monday is 0; weekly schedules only. */
  weekday: number | null
  /** HH:MM in `timezone`. */
  time: string
  timezone: string
  next_run_at: string
  last_run_at: string | null
  last_digest_id: string | null
}

export type ScheduleInput = Pick<DigestSchedule, 'cadence' | 'weekday' | 'time' | 'timezone'>

export type ResumeStatus = 'processing' | 'ready' | 'failed'

export interface ResumeFacts {
  headline: string
  seniority: 'junior' | 'middle' | 'senior' | 'lead' | 'executive' | 'unknown'
  summary: string
  skills: string[]
  domains: string[]
  by_model: boolean
}

export interface Resume {
  status: ResumeStatus
  error: string | null
  file_format: string
  size_bytes: number
  parser: 'builtin' | 'docling' | null
  facts: ResumeFacts | null
  suggestion: ProfileSpec | null
  created_at: string
  processed_at: string | null
}

export type ReactionKind = 'like' | 'dislike' | 'save' | 'hide' | 'open'

export interface FeedReason {
  kind: 'interest' | 'resume' | 'learned' | 'collab' | 'source' | 'explore'
  text: string
}

export interface FeedItem {
  article_id: number
  url: string
  title: string
  summary: string
  source_id: number
  source_name: string
  source_category: SourceCategory
  language: string
  published_at: string
  score: number
  explore: boolean
  /** Minutes to read the full text; null until its page has been read. */
  reading_minutes: number | null
  /** The article has a picture of its own, at api.articlePictureUrl. */
  has_picture: boolean
  /** In the newest-first order: met before the order was made, so it comes after the rest. */
  seen: boolean
  reasons: FeedReason[]
  /** Contribution of each part of the evidence; empty for saved items. */
  parts: Record<string, number>
  reactions: ReactionKind[]
  /** Why it is in the list and its place there, counted from 1. */
  slot: ListSlot
  position: number
}

export type ListSlot = 'ranked' | 'explore' | 'newest' | 'saved' | 'digest'

/**
 * Where the reader met an article: the list (a feed snapshot or a digest), the
 * place in it and why it was there. Sent along with what the reader did, for
 * the analytics and for teaching the feed's ranker.
 */
export interface Placement {
  listId: string | null
  position: number
  slot: ListSlot
}

export interface SeenItem {
  article_id: number
  position: number
  slot: ListSlot
}

function placementBody(placement: Placement | undefined) {
  return placement
    ? { list_id: placement.listId, position: placement.position, slot: placement.slot }
    : {}
}

export interface FeedPage {
  items: FeedItem[]
  total: number
  limit: number
  offset: number
  generated_at: string
  /** Names the ranking the page was cut from; pass it back for the next page. */
  snapshot: string | null
  /** When that ranking was made: what arrived since is offered as new. */
  built_at?: string | null
}

export interface TasteFacet {
  kind: 'interest' | 'resume' | 'learned' | 'avoid'
  label: string
  weight: number
}

export interface Taste {
  confidence: number
  positives: number
  negatives: number
  facets: TasteFacet[]
  sources: { source_id: number; name: string; affinity: number }[]
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

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: init?.headers ?? (init?.body ? { 'Content-Type': 'application/json' } : undefined),
    })
  } catch {
    throw new ApiError(0, 'Сервис недоступен. Попробуйте обновить страницу через минуту.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, describe(body?.detail, response.status))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Counts over distinct reader-article pairs, and the rates between them. */
export interface Rates {
  /** Seen on screen, or acted on: an article opened at once has no impression. */
  seen: number
  opened: number
  /** Liked or saved. */
  liked: number
  /** Disliked or hidden. */
  rejected: number
  ctr: number
  /** 95% Wilson interval of the CTR: narrower than the truth, a guide only. */
  ctr_low: number
  ctr_high: number
  like_rate: number
  reject_rate: number
  /** Enough seen for the rate to mean something. */
  enough: boolean
}

export interface AnalyticsTotals extends Rates {
  readers: number
  served: number
  digests_built: number
  digests_opened: number
  mcp_calls: number
  suggestions_accepted: number
  suggestions_dismissed: number
}

export interface RankerRun {
  version: string
  status: 'active' | 'rejected' | 'retired'
  created_at: string
  lists: number
  rows: number
  hand_ndcg: number | null
  model_ndcg: number | null
  note: string
}

export interface Analytics {
  enabled: boolean
  start: string
  end: string
  guests: boolean
  totals: AnalyticsTotals | null
  previous: AnalyticsTotals | null
  daily: (Rates & { day: string; readers: number })[]
  slots: (Rates & { slot: string })[]
  sources_best: (Rates & { source_id: number; name: string })[]
  sources_rejected: (Rates & { source_id: number; name: string })[]
  categories: (Rates & { category: string })[]
  adaptation: (Rates & { adaptive: boolean; readers: number })[]
  variants: (Rates & { variant: string; readers: number })[]
  last_event_at: string | null
  queue: { waiting: number; set_aside: number } | null
  ranker: { share: number; active: string | null; runs: RankerRun[] } | null
}

export const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
})

export function query(params: Record<string, string | number | string[] | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === '') continue
    for (const item of Array.isArray(value) ? value : [value]) search.append(key, String(item))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

function digestBody(profileId: string, period: DigestPeriod) {
  return 'days' in period
    ? { profile_id: profileId, period_days: period.days }
    : {
        profile_id: profileId,
        period_days: null,
        period_start: period.start.toISOString(),
        period_end: period.end.toISOString(),
      }
}

export const api = {
  meta: () => request<Meta>('/meta'),
  analytics: (days: number, guests: boolean) =>
    request<Analytics>(`/analytics/overview${query({ days, guests: String(guests) })}`),

  /** `null` when nobody is signed in. */
  me: () => request<Me | null>('/auth/me'),
  login: (email: string, password: string) =>
    request<User>('/auth/login', json('POST', { email, password })),
  register: (email: string, password: string, displayName: string) =>
    request<User>('/auth/register', json('POST', { email, password, display_name: displayName })),
  demoLogin: () => request<User>('/auth/demo', { method: 'POST' }),
  /** One click into a shared account: no password, the same account for everyone. */
  sharedLogin: (account: SharedAccountKey) =>
    request<User>(`/auth/preset/${account}`, { method: 'POST' }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  deleteAccount: (password: string) => request<void>('/auth/me/delete', json('POST', { password })),
  updateSettings: (settings: Partial<Settings>) =>
    request<Settings>('/auth/me/settings', json('PATCH', settings)),
  /** The first-run introduction is done (or skipped): it is not offered again. */
  finishOnboarding: () =>
    request<{ onboarded_at: string }>('/auth/me/onboarded', { method: 'POST' }),
  mcpKeys: () => request<McpKey[]>('/mcp/keys'),
  /** The picture goes as the raw body; the server squares and re-encodes it. */
  uploadAvatar: (file: File) =>
    request<AvatarChoice>('/auth/me/avatar', {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
    }),
  /** A ready picture instead of a photo: an uploaded photo is removed. */
  pickAvatar: (preset: AvatarPreset) =>
    request<AvatarChoice>('/auth/me/avatar-preset', json('PUT', { preset })),
  deleteAvatar: () => request<void>('/auth/me/avatar', { method: 'DELETE' }),
  schedules: () => request<DigestSchedule[]>('/digest-schedules'),
  putSchedule: (profileId: string, schedule: ScheduleInput) =>
    request<DigestSchedule>(`/profiles/${profileId}/schedule`, json('PUT', schedule)),
  deleteSchedule: (profileId: string) =>
    request<void>(`/profiles/${profileId}/schedule`, { method: 'DELETE' }),
  createMcpKey: (name: string) => request<NewMcpKey>('/mcp/keys', json('POST', { name })),
  revokeMcpKey: (id: string) => request<void>(`/mcp/keys/${id}`, { method: 'DELETE' }),

  /** `null` when no resume has been uploaded. */
  resume: () => request<Resume | null>('/resume'),
  /** The file goes as the raw body; its name only helps to tell text formats apart. */
  uploadResume: (file: File) =>
    request<Resume>('/resume', {
      method: 'POST',
      body: file,
      headers: {
        'Content-Type': 'application/octet-stream',
        'X-File-Name': encodeURIComponent(file.name),
      },
    }),
  deleteResume: () => request<void>('/resume', { method: 'DELETE' }),

  feed: (order: FeedOrder, limit: number, offset: number, snapshot?: string) =>
    request<FeedPage>(`/feed${query({ order, limit, offset, snapshot })}`),
  feedFresh: (since: string) => request<FeedFresh>(`/feed/fresh${query({ since })}`),
  saved: (limit: number, offset: number) =>
    request<FeedPage>(`/feed/saved${query({ limit, offset })}`),
  taste: () => request<Taste>('/taste'),
  reactions: (articleIds: number[]) =>
    request<Record<string, ReactionKind[]>>(
      `/reactions${query({ article_id: articleIds.map(String) })}`,
    ),
  feedback: (
    articleId: number,
    kind: ReactionKind,
    isActive: boolean,
    context: 'feed' | 'digest',
    placement?: Placement,
  ) =>
    request<void>('/feedback', {
      ...json('POST', {
        article_id: articleId,
        kind,
        active: isActive,
        context,
        ...placementBody(placement),
      }),
      // An opened link navigates away; the request must outlive the page.
      keepalive: true,
    }),

  profiles: () => request<Profile[]>('/profiles'),
  profileTemplates: () => request<ProfileTemplate[]>('/profile-templates'),
  createProfile: (spec: ProfileSpec) => request<Profile>('/profiles', json('POST', spec)),
  updateProfile: (id: string, spec: ProfileSpec) =>
    request<Profile>(`/profiles/${id}`, json('PUT', spec)),
  deleteProfile: (id: string) => request<void>(`/profiles/${id}`, { method: 'DELETE' }),
  setProfileLook: (id: string, look: { icon: string | null; color: string | null }) =>
    request<Profile>(`/profiles/${id}/look`, json('PATCH', look)),
  adaptation: (id: string) => request<Adaptation>(`/profiles/${id}/adaptation`),
  setAdaptive: (id: string, adaptive: boolean) =>
    request<Adaptation>(`/profiles/${id}/adaptation`, json('PATCH', { adaptive })),
  resetAdaptation: (id: string) =>
    request<Adaptation>(`/profiles/${id}/adaptation/reset`, { method: 'POST' }),
  acceptSuggestion: (profileId: string, suggestionId: string) =>
    request<Profile>(`/profiles/${profileId}/suggestions/${suggestionId}/accept`, {
      method: 'POST',
    }),
  dismissSuggestion: (profileId: string, suggestionId: string) =>
    request<void>(`/profiles/${profileId}/suggestions/${suggestionId}/dismiss`, {
      method: 'POST',
    }),
  recordImpressions: (items: SeenItem[], context: 'feed' | 'digest', listId: string | null) =>
    request<void>('/impressions', {
      ...json('POST', { items, context, list_id: listId }),
      keepalive: true,
    }),
  shareProfile: (id: string) => request<Profile>(`/profiles/${id}/share`, { method: 'POST' }),
  unshareProfile: (id: string) => request<Profile>(`/profiles/${id}/share`, { method: 'DELETE' }),
  sharedProfile: (token: string) =>
    request<SharedProfile>(`/shared-profiles/${encodeURIComponent(token)}`),
  acceptSharedProfile: (token: string) =>
    request<Profile>(`/shared-profiles/${encodeURIComponent(token)}/accept`, { method: 'POST' }),
  preview: (profile: ProfileSpec, periodDays: number, signal?: AbortSignal) =>
    request<Preview>('/selection/preview', {
      ...json('POST', { profile, period_days: periodDays }),
      signal,
    }),

  sources: () => request<Source[]>('/sources'),
  sourceHealth: () => request<SourceHealth>('/sources/health'),
  /** Source id -> version of its picture, for the sources that have one. */
  sourceAvatars: () => request<Record<string, string>>('/sources/avatars'),
  createSource: (source: SourceCreate) => request<Source>('/sources', json('POST', source)),
  detectSource: (address: string, linkSelector?: string) =>
    request<{ request_id: string }>(
      '/sources/detect',
      json('POST', { address, link_selector: linkSelector || null }),
    ),
  detectResult: (requestId: string) =>
    request<DetectResult>(`/sources/detect/${encodeURIComponent(requestId)}`),
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
  article: (id: number) => request<ArticleRead>(`/articles/${id}`),
  /** The article in Russian, translated by the model once and kept for every reader. */
  articleTranslation: (id: number) =>
    request<ArticleTranslation>(`/articles/${id}/translation${query({ to: 'ru' })}`),
  /** The article's own picture, the one a post in the feed shows. */
  articlePictureUrl: (articleId: number) => `${API_BASE}/articles/${articleId}/picture`,
  /** A picture of an opened article, fetched by the API from the address the page gave. */
  articleImageUrl: (articleId: number, imageId: string) =>
    `${API_BASE}/articles/${articleId}/images/${encodeURIComponent(imageId)}`,

  digests: (profileId?: string) =>
    request<DigestSummary[]>(`/digests${query({ profile_id: profileId, limit: 40 })}`),
  digest: (id: string) => request<Digest>(`/digests/${id}`),
  /** A period is a number of days back from now, or two dates. */
  createDigest: (profileId: string, period: DigestPeriod) =>
    request<DigestSummary>('/digests', json('POST', digestBody(profileId, period))),
  /** A specialist's digest and a management one, the second built after the
   * first on its cached grades. */
  createDigestsForBoth: (profileId: string, period: DigestPeriod) =>
    request<DigestSummary[]>('/digests/both', json('POST', digestBody(profileId, period))),
  deleteDigest: (id: string) => request<void>(`/digests/${id}`, { method: 'DELETE' }),
  compare: (base: string, other: string) =>
    request<Comparison>(`/digests/compare${query({ base, other })}`),

  /** `null` when no video of the digest was ordered. */
  short: (digestId: string) => request<Video | null>(`/digests/${digestId}/short`),
  createShort: (digestId: string, voice: string | null) =>
    request<Video>(`/digests/${digestId}/short`, json('POST', { voice })),

  exportUrl: (id: string, format: ExportFormat) => `${API_BASE}/digests/${id}/export.${format}`,
  /** Tick a line of the shift plan off or untick it; the answer lists the ticked lines. */
  tickPlan: (id: string, url: string, done: boolean) =>
    request<{ done: string[] }>(`/digests/${id}/plan`, json('PUT', { url, done })),
  askDigest: (id: string, question: string) =>
    request<AskAnswer>(`/digests/${id}/ask`, json('POST', { question })),
  eventsUrl: (id: string) => `${API_BASE}/digests/${id}/events`,
  /** Management digests only; `available` is false without a voice service. */
  briefing: (digestId: string) => request<BriefingState>(`/digests/${digestId}/briefing`),
  createBriefing: (digestId: string, voice: string | null) =>
    request<Briefing>(`/digests/${digestId}/briefing`, json('POST', { voice })),
  /** Whether a digest can be sent by email here, and to whom by default. */
  mailState: (digestId: string) => request<MailState>(`/digests/${digestId}/mail`),
  /** `null` sends it to the reader's own address. */
  mailDigest: (digestId: string, to: string | null) =>
    request<{ to: string }>(`/digests/${digestId}/mail`, json('POST', { to })),
}

/** The spoken brief of a management digest, about two minutes long. */
export interface Briefing {
  status: DigestStatus
  progress: number
  error: string | null
  /** "qwen3-tts:<speaker>" or "yandex:<voice>" once voiced. */
  voice: string | null
  /** The voice the reader picked, one of BriefingState.voices. */
  requested_voice: string | null
  /** What is said, line by line: the transcript under the player. */
  lines: string[]
  duration_ms: number | null
  size_bytes: number | null
  created_at: string
  finished_at: string | null
  /** Where to listen to it; set once it is done. */
  url: string | null
}

export interface BriefingState {
  /** False when the server has no voice service: no button then. */
  available: boolean
  /** Voices to pick from; empty when the service offers no choice. */
  voices: VoiceOption[]
  briefing: Briefing | null
}

/** Delivery of a digest by email. */
export interface MailState {
  /** False when the server has no mail server set: no button then. */
  available: boolean
  /** The reader's own address; null for a guest. */
  default_to: string | null
  /** Domains the company allows; empty allows any. */
  domains: string[]
}
