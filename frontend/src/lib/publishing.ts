// Publishing to Telegram channels. Shapes mirror
// backend/src/radar/api/routes/publishing.py and radar/publishing/settings.py.
import { json, query, request } from './api'

export type Tone = 'punchy' | 'neutral' | 'expert' | 'custom'
export type LinkMode = 'none' | 'inline' | 'preview' | 'button'
export type PostFormat = 'classic' | 'rich'
export type PostStatus =
  | 'composing'
  | 'draft'
  | 'queued'
  | 'sending'
  | 'sent'
  | 'failed'
  | 'skipped'

export interface ChannelSettings {
  style: {
    tone: Tone
    instructions: string
    audience: string
    emoji: string
    length: 'short' | 'medium' | 'long'
    bullets: boolean
    ending: boolean
    hashtags: boolean
    signature: string
  }
  links: { mode: LinkMode; inline_text: string; button_text: string; utm: string }
  format: {
    kind: PostFormat
    media: 'auto' | 'none'
    caption_above_media: boolean
    silent: boolean
    protect_content: boolean
  }
  schedule: {
    mode: 'interval' | 'times'
    every_minutes: number
    window_start: string
    window_end: string
    times: string[]
    days: number[]
    jitter_minutes: number
    timezone: string
    max_per_day: number
    prepare_minutes: number
  }
  selection: {
    freshness_hours: number
    min_score: number
    network: 'share' | 'spread'
    network_hours: number
  }
  digest: { enabled: boolean; weekday: number; time: string; items: number; days: number }
  approval: 'auto' | 'manual'
}

export interface Bot {
  id: string
  username: string
  name: string
  token_hint: string
  status: string
  last_error: string | null
  created_at: string
  channels: number
}

export interface Channel {
  id: string
  bot_id: string
  bot_username: string
  chat_id: number
  username: string | null
  title: string
  enabled: boolean
  profile_id: string | null
  settings: ChannelSettings
  status: string
  last_error: string | null
  next_slot: string | null
  created_at: string
  counts: Partial<Record<PostStatus, number>>
}

export interface Media {
  kind: 'photo' | 'video'
  url: string
}

export interface PostButton {
  text: string
  url: string
}

export interface PostContent {
  format: PostFormat
  html: string
  media: Media[]
  buttons: PostButton[]
  preview_url: string | null
  caption_above_media: boolean
  silent: boolean
  protect: boolean
}

export interface ArticleBrief {
  id: number
  title: string
  url: string
  source: string
  image_url: string | null
}

export interface Post {
  id: string
  channel_id: string
  kind: 'news' | 'digest'
  status: PostStatus
  slot_at: string | null
  not_before: string | null
  content: PostContent | null
  problems: string[]
  by_model: boolean
  message_url: string | null
  error: string | null
  created_at: string
  sent_at: string | null
  articles: ArticleBrief[]
}

export interface Defaults {
  settings: ChannelSettings
  enabled: boolean
  /** Posts go to the mock Bot API, not to Telegram. */
  mock: boolean
}

export const publishingApi = {
  defaults: () => request<Defaults>('/publishing/defaults'),
  bots: () => request<Bot[]>('/publishing/bots'),
  addBot: (token: string) => request<Bot>('/publishing/bots', json('POST', { token })),
  deleteBot: (id: string) => request<void>(`/publishing/bots/${id}`, { method: 'DELETE' }),
  channels: () => request<Channel[]>('/publishing/channels'),
  addChannel: (botId: string, chat: string, profileId: string | null) =>
    request<Channel>(
      '/publishing/channels',
      json('POST', { bot_id: botId, chat, profile_id: profileId }),
    ),
  updateChannel: (
    id: string,
    patch: {
      enabled?: boolean
      profile_id?: string | null
      bot_id?: string
      settings?: ChannelSettings
    },
  ) => {
    const body = { ...patch, clear_profile: patch.profile_id === null }
    return request<Channel>(`/publishing/channels/${id}`, json('PATCH', body))
  },
  deleteChannel: (id: string) => request<void>(`/publishing/channels/${id}`, { method: 'DELETE' }),
  posts: (channelId?: string) =>
    request<Post[]>(`/publishing/posts${query({ channel_id: channelId, limit: 100 })}`),
  createPost: (
    channelId: string,
    body: { kind?: 'news' | 'digest'; article_id?: number; publish?: boolean },
  ) => request<Post>(`/publishing/channels/${channelId}/posts`, json('POST', body)),
  updatePost: (
    id: string,
    body: { content?: PostContent; not_before?: string | null; approve?: boolean },
  ) => request<Post>(`/publishing/posts/${id}`, json('PATCH', body)),
  publishPost: (id: string) => request<Post>(`/publishing/posts/${id}/publish`, { method: 'POST' }),
  deletePost: (id: string) => request<void>(`/publishing/posts/${id}`, { method: 'DELETE' }),
}

export const STATUS_LABEL: Record<PostStatus, string> = {
  composing: 'Пишется',
  draft: 'Черновик',
  queued: 'В очереди',
  sending: 'Отправляется',
  sent: 'Опубликован',
  failed: 'Ошибка',
  skipped: 'Пропущен',
}

export const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
