// Real sources of the app's catalogue (backend/src/radar/seed.py) and stories an
// energy company's security team reads in them. List builders take the entries
// in turn, so a list shows different sources and stories.
import type { FeedItem, Source } from '../../lib/api'

type SourceEntry = Pick<
  Source,
  | 'slug'
  | 'name'
  | 'kind'
  | 'feed_url'
  | 'site_url'
  | 'category'
  | 'language'
  | 'fetch_full_text'
  | 'articles'
  | 'articles_last_day'
>

/** One source per category, then one in English. A source's id is its place here, from 1. */
export const SOURCES: SourceEntry[] = [
  {
    slug: 'securitylab',
    name: 'SecurityLab.ru',
    kind: 'rss',
    feed_url: 'https://www.securitylab.ru/_services/export/rss/',
    site_url: 'https://www.securitylab.ru',
    category: 'security',
    language: 'ru',
    fetch_full_text: true,
    articles: 2140,
    articles_last_day: 31,
  },
  {
    slug: 'kaspersky-ics-cert',
    name: 'Kaspersky ICS CERT',
    kind: 'rss',
    feed_url: 'https://ics-cert.kaspersky.ru/feed/',
    site_url: 'https://ics-cert.kaspersky.ru',
    category: 'ics',
    language: 'ru',
    fetch_full_text: false,
    articles: 386,
    articles_last_day: 2,
  },
  {
    slug: 'minenergo',
    name: 'Минэнерго России',
    kind: 'rss',
    feed_url: 'https://minenergo.gov.ru/rss',
    site_url: 'https://minenergo.gov.ru',
    category: 'energy',
    language: 'ru',
    fetch_full_text: false,
    articles: 512,
    articles_last_day: 4,
  },
  {
    slug: 'opennet',
    name: 'OpenNET',
    kind: 'rss',
    feed_url: 'https://www.opennet.ru/opennews/opennews_all_utf.rss',
    site_url: 'https://www.opennet.ru',
    category: 'it',
    language: 'ru',
    fetch_full_text: false,
    articles: 1730,
    articles_last_day: 18,
  },
  {
    slug: 'tg-bdufstecru',
    name: 'БДУ ФСТЭК России',
    kind: 'telegram',
    feed_url: 'https://t.me/s/bdufstecru',
    site_url: 'https://t.me/bdufstecru',
    category: 'regulator',
    language: 'ru',
    fetch_full_text: false,
    articles: 940,
    articles_last_day: 9,
  },
  {
    slug: 'cisa-ics',
    name: 'CISA ICS Advisories',
    kind: 'rss',
    feed_url: 'https://www.cisa.gov/cybersecurity-advisories/ics-advisories.xml',
    site_url: 'https://www.cisa.gov/news-events/cybersecurity-advisories',
    category: 'ics',
    language: 'en',
    fetch_full_text: false,
    articles: 610,
    articles_last_day: 3,
  },
]

type NewsEntry = {
  title: string
  summary: string
  url: string
  published_at: string
  tags: string[]
  /** The slug of its source in SOURCES. */
  source: string
}

/** Newest first, each from a different source. */
export const NEWS: NewsEntry[] = [
  {
    title: 'Уязвимость в контроллерах SIMATIC S7-1500 позволяет удалённо остановить ПЛК',
    summary:
      'Ошибка в веб-сервере контроллера даёт перезагрузить его без пароля. Siemens выпустила прошивку V3.1.5 и советует закрыть доступ к порту 443 из корпоративной сети.',
    url: 'https://www.securitylab.ru/news/562811.php',
    published_at: '2026-10-14T07:40:00Z',
    tags: ['Уязвимости', 'АСУ ТП', 'Siemens'],
    source: 'securitylab',
  },
  {
    title: 'Фишинг от имени Минэнерго нацелен на подрядчиков сетевых компаний',
    summary:
      'Письма о «новых требованиях к отчётности» несут загрузчик бэкдора. Злоумышленники ищут учётные данные для удалённого доступа к подстанциям.',
    url: 'https://ics-cert.kaspersky.ru/publications/minenergo-phishing-2026/',
    published_at: '2026-10-14T06:10:00Z',
    tags: ['Фишинг', 'Электроэнергетика'],
    source: 'kaspersky-ics-cert',
  },
  {
    title: 'Минэнерго утвердило требования к защите значимых объектов КИИ в электроэнергетике',
    summary:
      'Генерирующие и сетевые компании до 1 марта 2027 года переводят защиту АСУ ТП на отечественные средства и сообщают об инцидентах в НКЦКИ в течение трёх часов.',
    url: 'https://minenergo.gov.ru/press-center/news/kii-trebovaniya-2026',
    published_at: '2026-10-13T12:00:00Z',
    tags: ['КИИ', 'Регулирование'],
    source: 'minenergo',
  },
  {
    title: 'Вышел Zabbix 7.4.5 с исправлением SQL-инъекции в веб-интерфейсе',
    summary:
      'Уязвимость позволяет пользователю с правом только на чтение получить данные других учётных записей. Обновиться стоит всем, у кого интерфейс мониторинга доступен из общей сети.',
    url: 'https://www.opennet.ru/opennews/art.shtml?num=64210',
    published_at: '2026-10-13T10:20:00Z',
    tags: ['Zabbix', 'Уязвимости'],
    source: 'opennet',
  },
  {
    title: 'В БДУ внесена критическая уязвимость терминалов релейной защиты',
    summary:
      'Уязвимость BDU:2026-04210 с оценкой CVSS 9,8 позволяет изменить уставки терминала по протоколу МЭК 61850 без аутентификации. Производитель готовит обновление.',
    url: 'https://t.me/bdufstecru/2318',
    published_at: '2026-10-12T16:25:00Z',
    tags: [],
    source: 'tg-bdufstecru',
  },
  {
    title: 'Schneider Electric EcoStruxure Power Monitoring Expert',
    summary:
      'Successful exploitation of this vulnerability could allow an unauthenticated attacker to execute arbitrary code on the monitoring server.',
    url: 'https://www.cisa.gov/news-events/ics-advisories/icsa-26-286-02',
    published_at: '2026-10-12T09:30:00Z',
    tags: ['ICS'],
    source: 'cisa-ics',
  },
]

/** The entry at a place in a list, going round when the list is longer. */
export function nth<T>(entries: T[], index: number): T {
  return entries[index % entries.length]
}

/** The fixtures' today is 2026-10-14: a moment `days` days before it, in UTC. */
export function daysBefore(days: number, time = '00:00'): string {
  const [hours, minutes] = time.split(':').map(Number)
  const moment = new Date(Date.UTC(2026, 9, 14 - days, hours, minutes))
  return moment.toISOString().replace('.000Z', 'Z')
}

/** The source of a story as an article names it. */
export function sourceOf(
  news: NewsEntry,
): Pick<FeedItem, 'source_id' | 'source_name' | 'source_category' | 'language'> {
  const index = SOURCES.findIndex((source) => source.slug === news.source)
  const source = SOURCES[index]
  return {
    source_id: index + 1,
    source_name: source.name,
    source_category: source.category,
    language: source.language,
  }
}
