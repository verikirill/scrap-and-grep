// Publishing to Telegram: a channel's settings, the bot that posts, the channel,
// a post with what it says and the articles behind it, and the publishing
// service's defaults.
import type {
  ArticleBrief,
  Bot,
  Channel,
  ChannelSettings,
  Defaults,
  Media,
  Post,
  PostButton,
  PostContent,
} from '../../lib/publishing'
import { NEWS, sourceOf } from './catalog'
import { counter, nextArticleId } from './ids'

/** The service's defaults (backend publishing/settings.py): a post every three
 * hours from 9 to 21 Moscow time, published without approval. */
export function makeChannelSettings(overrides: Partial<ChannelSettings> = {}): ChannelSettings {
  return {
    style: {
      tone: 'punchy',
      instructions: '',
      audience: '',
      emoji: '⚡',
      length: 'medium',
      bullets: true,
      ending: true,
      hashtags: false,
      signature: '',
    },
    links: { mode: 'inline', inline_text: 'здесь', button_text: 'Читать источник', utm: '' },
    format: {
      kind: 'classic',
      media: 'auto',
      caption_above_media: false,
      silent: false,
      protect_content: false,
    },
    schedule: {
      mode: 'interval',
      every_minutes: 180,
      window_start: '09:00',
      window_end: '21:00',
      times: [],
      days: [0, 1, 2, 3, 4, 5, 6],
      jitter_minutes: 0,
      timezone: 'Europe/Moscow',
      max_per_day: 6,
      prepare_minutes: 20,
    },
    selection: { freshness_hours: 24, min_score: 0.5, network: 'share', network_hours: 12 },
    digest: { enabled: false, weekday: 4, time: '18:00', items: 5, days: 7 },
    approval: 'auto',
    ...overrides,
  }
}

/** The token is shown as its bot id and last four characters. */
export function makeBot(overrides: Partial<Bot> = {}): Bot {
  return {
    id: 'bot-1',
    username: 'energy_infosec_bot',
    name: 'Энергетика и ИБ',
    token_hint: '7412365890:…k3Qw',
    status: 'ok',
    last_error: null,
    created_at: '2026-10-01T09:00:00Z',
    channels: 1,
    ...overrides,
  }
}

/** A public channel of bot-1 that posts what profile-1 selects. */
export function makeChannel(overrides: Partial<Channel> = {}): Channel {
  return {
    id: 'channel-1',
    bot_id: 'bot-1',
    bot_username: 'energy_infosec_bot',
    chat_id: -1002233445566,
    username: 'energy_infosec',
    title: 'Энергетика и ИБ',
    enabled: true,
    profile_id: 'profile-1',
    settings: makeChannelSettings(),
    status: 'ok',
    last_error: null,
    next_slot: '2026-10-14T12:00:00Z',
    created_at: '2026-10-01T09:05:00Z',
    counts: { sent: 24, draft: 2, queued: 1 },
    ...overrides,
  }
}

export function makeMedia(overrides: Partial<Media> = {}): Media {
  return {
    kind: 'photo',
    url: 'https://www.securitylab.ru/upload/iblock/7c2/simatic-s7-1500.jpg',
    ...overrides,
  }
}

export function makePostButton(overrides: Partial<PostButton> = {}): PostButton {
  return { text: 'Читать источник', url: NEWS[0].url, ...overrides }
}

/** A classic post in the default style: the emoji, a bold lead, bullets and a link. */
export function makePostContent(overrides: Partial<PostContent> = {}): PostContent {
  return {
    format: 'classic',
    html: [
      '<p>⚡ <b>Уязвимость в SIMATIC S7-1500 позволяет удалённо остановить ПЛК</b></p>',
      '<ul><li>Без пароля, через веб-сервер контроллера</li><li>Исправление: прошивка V3.1.5</li></ul>',
      `<p>Подробнее <a href="${NEWS[0].url}">здесь</a></p>`,
    ].join(''),
    media: [],
    buttons: [],
    preview_url: null,
    caption_above_media: false,
    silent: false,
    protect: false,
    ...overrides,
  }
}

export function makeArticleBrief(overrides: Partial<ArticleBrief> = {}): ArticleBrief {
  const news = NEWS[0]
  return {
    id: nextArticleId(),
    title: news.title,
    url: news.url,
    source: sourceOf(news).source_name,
    image_url: null,
    ...overrides,
  }
}

const nextPost = counter()

/** A news post of channel-1, written by the model and kept as a draft. */
export function makePost(overrides: Partial<Post> = {}): Post {
  return {
    id: `post-${nextPost()}`,
    channel_id: 'channel-1',
    kind: 'news',
    status: 'draft',
    slot_at: '2026-10-14T12:00:00Z',
    not_before: null,
    content: makePostContent(),
    problems: [],
    by_model: true,
    message_url: null,
    error: null,
    created_at: '2026-10-14T11:40:00Z',
    sent_at: null,
    articles: [makeArticleBrief()],
    ...overrides,
  }
}

/** Publishing is on and posts go to Telegram itself, not to the mock Bot API. */
export function makePublishingDefaults(overrides: Partial<Defaults> = {}): Defaults {
  return { settings: makeChannelSettings(), enabled: true, mock: false, ...overrides }
}
