import { ApiError } from './api'

/** What went wrong in the reader's words, and what they can do about it. */
export type Failure = { title: string; hint: string }

const NETWORK: Failure = {
  title: 'Нет связи с сервером',
  hint: 'Проверьте подключение к интернету и попробуйте ещё раз.',
}
const DENIED: Failure = {
  title: 'Нет доступа',
  hint: 'Войдите заново или попросите доступ у администратора.',
}
const MISSING: Failure = {
  title: 'Не нашлось',
  hint: 'Возможно, это удалили или ссылка устарела.',
}
const THROTTLED: Failure = {
  title: 'Слишком много запросов',
  hint: 'Подождите немного и попробуйте снова.',
}
const DOWN: Failure = {
  title: 'Сервис временно недоступен',
  hint: 'Попробуйте ещё раз через минуту.',
}

/** The kind of a failed API request, when its status names one; otherwise null. */
export function failureOf(error: unknown): Failure | null {
  if (!(error instanceof ApiError)) return null
  const { status } = error
  if (status === 0) return NETWORK
  if (status === 401 || status === 403) return DENIED
  if (status === 404) return MISSING
  if (status === 429) return THROTTLED
  if (status >= 500) return DOWN
  return null
}

/**
 * The server's own explanation, or null where it gave none: a request that
 * never reached it, or an answer with no detail beyond the status (lib/api.ts).
 */
export function serverDetail(error: ApiError): string | null {
  if (error.status === 0 || error.message === `Ошибка ${error.status}`) return null
  return error.message || null
}

/** The statuses that have a drawing of their own (components/ErrorIllustration.tsx). */
export type ErrorArt = 404 | 429 | 500 | 503

/**
 * The drawing for a request that failed page-wide: too many requests, or the
 * service down (any 5xx is shown asleep). Other failures keep the icon tile.
 */
export function errorArtOf(error: unknown): ErrorArt | null {
  if (!(error instanceof ApiError)) return null
  if (error.status === 429) return 429
  if (error.status >= 500) return 503
  return null
}
