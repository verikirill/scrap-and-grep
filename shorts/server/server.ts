// HTTP service the backend worker calls to turn a script and its narration
// into an MP4. It listens on the internal Docker network only.
//
//   POST /v1/render  {"props": ShortProps without audioSrc, "audio": base64 WAV | null}
//                    -> 200 video/mp4, 400 bad props, 413 too big, 503 busy, 504 too slow
//   GET  /healthz    -> {"status": "ok", "queued": n}
import { createServer } from 'node:http'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { ensureBrowser, makeCancelSignal } from '@remotion/renderer'
import { z } from 'zod'
import { shortSchema } from '../src/schema.ts'
import type { ShortProps } from '../src/types.ts'
import { hold, isWav, serveAsset } from './assets.ts'
import { HttpError, log, readBody, sendJson } from './http.ts'
import { SerialQueue } from './queue.ts'
import { bundled, renderShort } from './render.ts'

/** A positive number from the environment; a typo stops the service at start. */
function setting(name: string, fallback: number | null): number | null {
  const raw = process.env[name]
  if (!raw) {
    return fallback
  }
  const value = Number(raw)
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${name} must be a positive number, got "${raw}"`)
  }
  return value
}

const PORT = setting('PORT', 3000) as number
const HOST = process.env.HOST ?? '0.0.0.0'
// Two minutes of 24 kHz 16-bit mono is 5.8 MB, 7.7 MB as base64.
const MAX_BODY_BYTES = 16 * 1024 * 1024
const RENDER_TIMEOUT_MS = setting('RENDER_TIMEOUT_MS', 10 * 60 * 1000) as number
// Browser tabs rendering frames in parallel; null lets Remotion pick.
const CONCURRENCY = setting('RENDER_CONCURRENCY', null)
const QUEUE_LIMIT = 4
const LOGGED_ERROR_CHARS = 300

const requestSchema = z.object({
  props: z.record(z.string(), z.unknown()),
  audio: z.string().nullable(),
})

type Job = { props: ShortProps; audio: Buffer | null }

const queue = new SerialQueue(QUEUE_LIMIT)

function parseRequest(body: Buffer): Job {
  let json: unknown
  try {
    json = JSON.parse(body.toString('utf8'))
  } catch {
    throw new HttpError(400, 'the body is not JSON')
  }
  const request = requestSchema.safeParse(json)
  if (!request.success) {
    throw new HttpError(400, z.prettifyError(request.error))
  }
  // The audio address is ours to give, whatever the caller sent.
  const props = shortSchema.safeParse({ ...request.data.props, audioSrc: null })
  if (!props.success) {
    throw new HttpError(400, z.prettifyError(props.error))
  }
  const audio = request.data.audio === null ? null : Buffer.from(request.data.audio, 'base64')
  if (audio && !isWav(audio)) {
    throw new HttpError(400, 'audio must be a WAV file')
  }
  return { props: props.data, audio }
}

async function renderJob(job: Job, cancelSignal: ReturnType<typeof makeCancelSignal>['cancelSignal']) {
  const asset = job.audio ? hold(job.audio) : null
  const started = performance.now()
  try {
    const rendered = await renderShort({
      props: { ...job.props, audioSrc: asset ? `http://127.0.0.1:${PORT}${asset.path}` : null },
      concurrency: CONCURRENCY,
      cancelSignal,
    })
    log('rendered', {
      frames: rendered.frames,
      seconds: Math.round(performance.now() - started) / 1000,
      bytes: rendered.video?.length ?? 0,
    })
    return rendered.video
  } finally {
    asset?.release()
  }
}

async function render(req: IncomingMessage, res: ServerResponse) {
  // The place in line is taken before the body is read, so the limit also
  // bounds how many bodies are held in memory at once.
  const leave = queue.enter()
  if (!leave) {
    throw new HttpError(503, 'the renderer is busy')
  }
  const { cancelSignal, cancel } = makeCancelSignal()
  let job: Job | null = null
  // A worker that gave up must not keep its place in line, nor its audio in
  // memory, while it waits for its turn.
  res.on('close', () => {
    if (!res.writableFinished) {
      job = null
      cancel()
      leave()
    }
  })
  try {
    job = parseRequest(await readBody(req, MAX_BODY_BYTES))
    const video = await queue.run(async () => {
      const current = job
      if (current === null || res.destroyed) {
        return null
      }
      let isTimedOut = false
      const timer = setTimeout(() => {
        isTimedOut = true
        cancel()
      }, RENDER_TIMEOUT_MS)
      try {
        return await renderJob(current, cancelSignal)
      } catch (error) {
        throw isTimedOut ? new HttpError(504, 'the render took too long') : error
      } finally {
        clearTimeout(timer)
      }
    })
    if (!video || res.destroyed) {
      return
    }
    res.writeHead(200, { 'Content-Type': 'video/mp4', 'Content-Length': String(video.length) })
    res.end(video)
  } finally {
    leave()
  }
}

function pathOf(req: IncomingMessage): string {
  try {
    return new URL(req.url ?? '/', 'http://localhost').pathname
  } catch {
    throw new HttpError(400, 'bad request target')
  }
}

async function handle(req: IncomingMessage, res: ServerResponse) {
  const pathname = pathOf(req)
  if (serveAsset(req, res, pathname)) {
    return
  }
  if (req.method === 'GET' && pathname === '/healthz') {
    sendJson(res, 200, { status: 'ok', queued: queue.size })
    return
  }
  if (req.method === 'POST' && pathname === '/v1/render') {
    await render(req, res)
    return
  }
  sendJson(res, 404, { detail: 'not found' })
}

function describe(error: unknown): string {
  // Chrome's messages may quote the page; the log gets the start only.
  const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error)
  return message.slice(0, LOGGED_ERROR_CHARS)
}

const server = createServer((req, res) => {
  handle(req, res).catch((error: unknown) => {
    if (res.headersSent || res.destroyed) {
      return
    }
    if (error instanceof HttpError) {
      const retry: Record<string, string> = error.status === 503 ? { 'Retry-After': '30' } : {}
      sendJson(res, error.status, { detail: error.message }, retry)
      return
    }
    log('render_failed', { error: describe(error) })
    sendJson(res, 500, { detail: 'render failed' })
  })
})

// A late rejection from inside the browser after a cancelled render must not
// take the service down with the renders of other requests.
process.on('unhandledRejection', (reason) => log('unhandled_rejection', { error: describe(reason) }))

// Fail at start rather than on the first request: the browser and the bundle
// are both baked into the image, so these calls only check they are there.
await ensureBrowser()
await bundled()
server.listen(PORT, HOST, () => log('listening', { host: HOST, port: PORT }))

process.on('SIGTERM', () => server.close())
