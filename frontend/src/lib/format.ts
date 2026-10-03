import type { Audience, SourceCategory } from './api'

const MOSCOW = 'Europe/Moscow'

const dateFormat = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'short',
  timeZone: MOSCOW,
})
const dateTimeFormat = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: MOSCOW,
})
const timeFormat = new Intl.DateTimeFormat('ru-RU', {
  hour: '2-digit',
  minute: '2-digit',
  timeZone: MOSCOW,
})
// A calendar day in Moscow as 2026-10-02, to tell today from yesterday.
const dayFormat = new Intl.DateTimeFormat('en-CA', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  timeZone: MOSCOW,
})
const DAY_MS = 86_400_000
const numberFormat = new Intl.NumberFormat('ru-RU')
const relativeFormat = new Intl.RelativeTimeFormat('ru-RU', { numeric: 'auto' })

export const formatDate = (iso: string) => dateFormat.format(new Date(iso))
export const formatDateTime = (iso: string) => dateTimeFormat.format(new Date(iso))
export const formatNumber = (value: number) => numberFormat.format(value)

export function formatRelative(iso: string, now: number = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000)
  const steps: [Intl.RelativeTimeFormatUnit, number][] = [
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
  ]
  for (const [unit, size] of steps) {
    if (Math.abs(seconds) >= size) return relativeFormat.format(Math.round(seconds / size), unit)
  }
  return 'только что'
}

/** When a post came out, as a chat shows it: "14:05" today, "вчера, 14:05", "30 сент., 14:05". */
export function formatPostTime(iso: string, now: Date = new Date()): string {
  const date = new Date(iso)
  const day = dayFormat.format(date)
  if (day === dayFormat.format(now)) return timeFormat.format(date)
  if (day === dayFormat.format(new Date(now.getTime() - DAY_MS))) {
    return `вчера, ${timeFormat.format(date)}`
  }
  return dateTimeFormat.format(date)
}

export function formatPeriod(startIso: string, endIso: string): string {
  return `${formatDate(startIso)} - ${formatDate(endIso)}`
}

/** Video length as a player shows it: 42_300 -> "0:42". */
export function formatDuration(ms: number): string {
  const seconds = Math.round(ms / 1000)
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

/** File size in megabytes with one decimal: "5,4 МБ". */
export const formatMegabytes = (bytes: number) =>
  `${(bytes / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} МБ`

/** Russian plural form: plural(5, ['статья', 'статьи', 'статей']). */
/** The period an audience reads by default: a specialist's issue covers a day, management's a week. */
export const AUDIENCE_DAYS: Record<Audience, number> = { specialist: 1, management: 7 }

/** "сутки" or "неделю": the default period of an audience, after "за". */
export const periodWords = (days: number) => (days === 1 ? 'сутки' : 'неделю')

export function plural(count: number, forms: [string, string, string]): string {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return forms[0]
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1]
  return forms[2]
}

export const CATEGORY_LABELS: Record<SourceCategory, string> = {
  security: 'Безопасность',
  ics: 'АСУ ТП',
  it: 'ИТ',
  energy: 'Энергетика',
  regulator: 'Регуляторы',
}

export const REJECT_LABELS: Record<string, string> = {
  low_score: 'ниже порога',
  excluded: 'исключение',
  duplicate: 'повтор',
  over_limit: 'выпуск заполнен',
  hidden: 'скрыто вами',
}

export const STAGE_LABELS: Record<string, string> = {
  prepare: 'Готовим публикации',
  retrieve: 'Ищем по интересам',
  grade: 'Оцениваем релевантность',
  select: 'Отбираем и убираем повторы',
  summarize: 'Пишем выжимки',
  compose: 'Собираем выпуск',
  persist: 'Сохраняем',
  done: 'Готово',
}

export const SETTING_LABELS: Record<string, string> = {
  role: 'описание роли',
  exclusions: 'исключения',
  min_score: 'порог релевантности',
  max_items: 'размер выпуска',
  languages: 'языки',
  categories: 'категории источников',
}

/** Short model name for the status line: "ollama:qwen3.5:9b" -> "qwen3.5:9b". */
export function modelLabel(id: string | undefined): string {
  if (!id) return 'н/д'
  if (id.startsWith('hashing')) return 'без модели (n-граммы)'
  if (id === 'heuristic') return 'без модели (эвристика)'
  return id.replace(/^ollama:/, '')
}

/**
 * Article and source links come from third-party feeds. Anything that is not
 * plain http(s) is dropped, so a "javascript:" URL can never reach an href.
 */
export function externalHref(url: string | null | undefined): string | undefined {
  if (!url) return undefined
  try {
    const { protocol } = new URL(url)
    return protocol === 'http:' || protocol === 'https:' ? url : undefined
  } catch {
    return undefined
  }
}
