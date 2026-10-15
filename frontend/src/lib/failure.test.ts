import { describe, expect, it } from 'vitest'
import { ApiError } from './api'
import { errorArtOf, failureOf, serverDetail } from './failure'

describe('failureOf', () => {
  it.each([
    [0, 'Нет связи с сервером'],
    [401, 'Нет доступа'],
    [403, 'Нет доступа'],
    [404, 'Не нашлось'],
    [429, 'Слишком много запросов'],
    [500, 'Сервис временно недоступен'],
    [503, 'Сервис временно недоступен'],
  ])('names a request that failed with %i', (status, title) => {
    expect(failureOf(new ApiError(status, 'x'))?.title).toBe(title)
  })

  it('leaves other failures to their own message', () => {
    expect(failureOf(new ApiError(409, 'Источник уже добавлен.'))).toBeNull()
    expect(failureOf(new ApiError(422, 'name: field required'))).toBeNull()
    expect(failureOf(new Error('boom'))).toBeNull()
    expect(failureOf('boom')).toBeNull()
  })
})

describe('serverDetail', () => {
  it('keeps what the server said and drops what it did not', () => {
    expect(serverDetail(new ApiError(503, 'База данных недоступна'))).toBe('База данных недоступна')
    expect(serverDetail(new ApiError(502, 'Ошибка 502'))).toBeNull()
    expect(serverDetail(new ApiError(0, 'Сервис недоступен.'))).toBeNull()
    expect(serverDetail(new ApiError(500, ''))).toBeNull()
  })
})

describe('errorArtOf', () => {
  it('draws too many requests, and any server failure as the service asleep', () => {
    expect(errorArtOf(new ApiError(429, 'x'))).toBe(429)
    expect(errorArtOf(new ApiError(500, 'x'))).toBe(503)
    expect(errorArtOf(new ApiError(503, 'x'))).toBe(503)
  })

  it('leaves the rest to the icon tile', () => {
    expect(errorArtOf(new ApiError(0, 'x'))).toBeNull()
    expect(errorArtOf(new ApiError(404, 'x'))).toBeNull()
    expect(errorArtOf(new Error('boom'))).toBeNull()
  })
})
