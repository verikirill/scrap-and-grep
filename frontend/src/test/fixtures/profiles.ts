// Profiles of interests: the spec a reader edits, the saved profile and its look,
// the preview of what a draft selects, what a profile learned from the reader's
// marks, and a profile someone sent by link.
import type {
  Adaptation,
  Interest,
  InterestLearning,
  Preview,
  PreviewItem,
  Profile,
  ProfileSpec,
  ProfileTemplate,
  SharedProfile,
  Suggestion,
} from '../../lib/api'
import { NEWS, nth, sourceOf } from './catalog'
import { counter, nextArticleId } from './ids'

const INTERESTS: Omit<Interest, 'id'>[] = [
  {
    title: 'Уязвимости АСУ ТП',
    description: 'Уязвимости контроллеров и SCADA',
    keywords: ['SCADA', 'Siemens'],
    weight: 1,
  },
  {
    title: 'Атаки на энергетику',
    description: 'Атаки и инциденты на объектах генерации и электросетевого комплекса',
    keywords: ['подстанция', 'энергосистема', 'КИИ'],
    weight: 1,
  },
  {
    title: 'Требования регуляторов',
    description: 'Приказы ФСТЭК и Минэнерго о защите значимых объектов КИИ',
    keywords: ['ФСТЭК', '187-ФЗ', 'НКЦКИ'],
    weight: 0.8,
  },
  {
    title: 'Удалённый доступ подрядчиков',
    description: 'VPN-шлюзы, RDP и доступ подрядчиков к технологической сети',
    keywords: ['VPN', 'RDP', 'подрядчик'],
    weight: 0.6,
  },
]

function interestAt(index: number): Interest {
  const interest = nth(INTERESTS, index)
  return { id: `interest-${index + 1}`, ...interest, keywords: [...interest.keywords] }
}

/** The interest makeSpec() starts with; makeItem().interest_id points at it. */
export function makeInterest(overrides: Partial<Interest> = {}): Interest {
  return { ...interestAt(0), ...overrides }
}

/** `count` different interests, interest-1 first. */
export function makeInterests(count: number, overrides: Partial<Interest> = {}): Interest[] {
  return Array.from({ length: count }, (_, index) => ({ ...interestAt(index), ...overrides }))
}

export function makeSpec(overrides: Partial<ProfileSpec> = {}): ProfileSpec {
  return {
    name: 'Инженер АСУ ТП',
    role: 'Инженер по защите АСУ ТП',
    interests: [makeInterest()],
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

/** A ready profile for a typical role, as the server offers it to a new reader. */
export function makeProfileTemplate(overrides: Partial<ProfileTemplate> = {}): ProfileTemplate {
  return {
    spec: makeSpec({ name: 'Специалист по ИБ АСУ ТП', interests: makeInterests(3) }),
    icon: 'shield',
    color: 'red',
    ...overrides,
  }
}

/** A profile's icon and colour: keys of lib/profileLook, or a colour as #rrggbb. */
export type ProfileLook = Pick<Profile, 'icon' | 'color'>

export function makeProfileLook(overrides: Partial<ProfileLook> = {}): ProfileLook {
  return { icon: 'energy', color: 'teal', ...overrides }
}

function previewItemAt(index: number): PreviewItem {
  const news = nth(NEWS, index)
  return {
    article_id: nextArticleId(),
    url: news.url,
    title: news.title,
    source_name: sourceOf(news).source_name,
    published_at: news.published_at,
    score: 0.82,
    interest_id: 'interest-1',
    interest_title: 'Уязвимости АСУ ТП',
    lexical_hit: true,
    selected: true,
    reject_reason: null,
  }
}

export function makePreviewItem(overrides: Partial<PreviewItem> = {}): PreviewItem {
  return { ...previewItemAt(0), ...overrides }
}

/** `count` candidates of different stories, all selected. */
export function makePreviewItems(
  count: number,
  overrides: Partial<PreviewItem> = {},
): PreviewItem[] {
  return Array.from({ length: count }, (_, index) => ({ ...previewItemAt(index), ...overrides }))
}

/** What a draft would select over a day: the counts and the best candidates. */
export function makePreview(overrides: Partial<Preview> = {}): Preview {
  return {
    window_total: 300,
    candidates: 40,
    selected: 12,
    lexical_only: false,
    embedding_model: 'hashing-ngrams',
    items: makePreviewItems(3),
    ...overrides,
  }
}

export function makeInterestLearning(overrides: Partial<InterestLearning> = {}): InterestLearning {
  return {
    interest_id: 'interest-1',
    title: 'Уязвимости АСУ ТП',
    stated_weight: 1,
    weight: 1.06,
    factor: 1.06,
    drift: 0.12,
    positives: 9,
    negatives: 2,
    skipped: 14,
    ...overrides,
  }
}

const nextSuggestion = counter()

/** A new topic the reader's likes suggest, with the article that led to it. */
export function makeSuggestion(overrides: Partial<Suggestion> = {}): Suggestion {
  return {
    id: `suggestion-${nextSuggestion()}`,
    kind: 'interest',
    source: 'likes',
    title: 'Безопасность ВИЭ-генерации',
    description: 'Уязвимости инверторов и систем управления солнечных и ветровых электростанций',
    keywords: ['инвертор', 'ВИЭ', 'солнечная электростанция'],
    articles: [
      {
        id: nextArticleId(),
        title: 'Уязвимости солнечных инверторов позволяют удалённо отключить генерацию',
        url: 'https://www.securitylab.ru/news/562644.php',
        source_name: 'SecurityLab.ru',
      },
    ],
    created_at: '2026-10-13T21:00:00Z',
    ...overrides,
  }
}

/** A profile that adapts, with what one interest learned and one suggestion.
 * Pair it with makeProfile({ adaptive: true }). */
export function makeAdaptation(overrides: Partial<Adaptation> = {}): Adaptation {
  return {
    adaptive: true,
    since: null,
    updated_at: '2026-10-14T06:00:00Z',
    interests: [makeInterestLearning()],
    suggestions: [makeSuggestion()],
    ...overrides,
  }
}

/** A colleague's profile opened by link, not taken by the reader yet. */
export function makeSharedProfile(overrides: Partial<SharedProfile> = {}): SharedProfile {
  return {
    spec: makeSpec({
      name: 'Защита подстанций',
      role: 'Руководитель группы ИБ АСУ ТП',
      interests: makeInterests(2),
    }),
    icon: 'energy',
    color: 'teal',
    own_id: null,
    ...overrides,
  }
}
