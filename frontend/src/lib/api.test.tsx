// The API client: what it sends and how a server's refusal reaches the reader.
// A .tsx test so it runs in jsdom, where MSW answers fetch.
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { apiUrl, server } from '../test/server'
import { ApiError, api, query, request } from './api'

/** Answer one request and keep what was sent. */
function capture(method: 'get' | 'post' | 'delete', path: string, reply: () => Response) {
  const sent: { contentType: string | null; body: string; search: string }[] = []
  server.use(
    http[method](apiUrl(path), async ({ request: incoming }) => {
      sent.push({
        contentType: incoming.headers.get('content-type'),
        body: await incoming.text(),
        search: new URL(incoming.url).search,
      })
      return reply()
    }),
  )
  return sent
}

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  const error = await promise.then(
    () => null,
    (caught: unknown) => caught,
  )
  if (!(error instanceof ApiError)) throw new Error(`expected an ApiError, got ${String(error)}`)
  return error
}

describe('request', () => {
  it('sends JSON with its type, and a request without a body with no type', async () => {
    const posted = capture('post', '/profiles', () => HttpResponse.json({ id: 'profile-1' }))
    const got = capture('get', '/profiles', () => HttpResponse.json([]))

    await request('/profiles', { method: 'POST', body: JSON.stringify({ name: 'АСУ ТП' }) })
    await request('/profiles')

    expect(posted).toEqual([
      { contentType: 'application/json', body: '{"name":"АСУ ТП"}', search: '' },
    ])
    expect(got[0].contentType).toBeNull()
  })

  it('gives back the server’s answer, and nothing for 204', async () => {
    server.use(
      http.get(apiUrl('/meta'), () => HttpResponse.json({ version: '1.2' })),
      http.delete(apiUrl('/digests/digest-1'), () => new HttpResponse(null, { status: 204 })),
    )
    await expect(request('/meta')).resolves.toEqual({ version: '1.2' })
    await expect(api.deleteDigest('digest-1')).resolves.toBeUndefined()
  })

  it('passes on the server’s own words about a refusal, with its status', async () => {
    server.use(
      http.get(apiUrl('/profiles'), () =>
        HttpResponse.json({ detail: 'Профиль не найден' }, { status: 404 }),
      ),
    )
    const error = await failure(request('/profiles'))
    expect(error.status).toBe(404)
    expect(error.message).toBe('Профиль не найден')
  })

  it('names the fields of a validation error the way FastAPI lists them', async () => {
    server.use(
      http.put(apiUrl('/digest-schedules/profile-1'), () =>
        HttpResponse.json(
          {
            detail: [
              { loc: ['body', 'time'], msg: 'Неверный формат времени' },
              { loc: ['body'], msg: 'Нужен день недели' },
            ],
          },
          { status: 422 },
        ),
      ),
    )
    const error = await failure(request('/digest-schedules/profile-1', { method: 'PUT' }))
    expect(error.message).toBe('time: Неверный формат времени; Нужен день недели')
  })

  it('falls back to the status when a refusal says nothing readable', async () => {
    server.use(
      http.get(
        apiUrl('/feed'),
        () => new HttpResponse('<html>Bad gateway</html>', { status: 502 }),
      ),
      http.get(apiUrl('/sources'), () => HttpResponse.json({ error: 'x' }, { status: 500 })),
    )
    expect((await failure(request('/feed'))).message).toBe('Ошибка 502')
    expect((await failure(request('/sources'))).message).toBe('Ошибка 500')
  })

  it('says the service is out of reach when the network fails', async () => {
    server.use(http.get(apiUrl('/meta'), () => HttpResponse.error()))
    const error = await failure(request('/meta'))
    expect(error.status).toBe(0)
    expect(error.message).toBe('Сервис недоступен. Попробуйте обновить страницу через минуту.')
  })
})

describe('query', () => {
  it('leaves out empty values and repeats a list', () => {
    expect(query({ order: 'new', q: '', offset: 0, profile_id: undefined })).toBe(
      '?order=new&offset=0',
    )
    expect(query({ article_id: ['1', '2'] })).toBe('?article_id=1&article_id=2')
    expect(query({ q: 'МЭК 61850 & CVE' })).toBe('?q=%D0%9C%D0%AD%D0%9A+61850+%26+CVE')
    expect(query({ q: undefined })).toBe('')
  })
})

describe('building an issue', () => {
  it('asks for a number of days back from now', async () => {
    const sent = capture('post', '/digests', () => HttpResponse.json({ id: 'digest-9' }))
    await api.createDigest('profile-1', { days: 7 })
    expect(JSON.parse(sent[0].body)).toEqual({ profile_id: 'profile-1', period_days: 7 })
  })

  it('asks for two dates as exact moments, for both audiences too', async () => {
    const sent = capture('post', '/digests/both', () => HttpResponse.json([]))
    await api.createDigestsForBoth('profile-1', {
      start: new Date('2026-10-01T00:00:00+03:00'),
      end: new Date('2026-10-07T23:59:59+03:00'),
    })
    expect(JSON.parse(sent[0].body)).toEqual({
      profile_id: 'profile-1',
      period_days: null,
      period_start: '2026-09-30T21:00:00.000Z',
      period_end: '2026-10-07T20:59:59.000Z',
    })
  })
})
