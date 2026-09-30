import { randomBytes } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'

// Narration of the renders in progress. The headless browser that draws the
// frames fetches it over HTTP from this same process, so nothing touches the
// disk, and the entry disappears when the render ends.
const narration = new Map<string, Buffer>()

const PREFIX = '/assets/'

export function isWav(data: Buffer): boolean {
  return (
    data.length > 44 &&
    data.toString('latin1', 0, 4) === 'RIFF' &&
    data.toString('latin1', 8, 12) === 'WAVE'
  )
}

/** Keep the audio for one render and return its path; call the result to drop it. */
export function hold(audio: Buffer): { path: string; release: () => void } {
  const token = randomBytes(16).toString('hex')
  narration.set(token, audio)
  return { path: `${PREFIX}${token}.wav`, release: () => narration.delete(token) }
}

// The browser reads the file with range requests, and from another origin
// than the bundle, so both CORS and ranges are answered.
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Range',
  'Access-Control-Expose-Headers': 'Content-Length, Content-Range, Accept-Ranges',
}

/** The byte range a Range header asks for, or null when it is not one we serve. */
export function parseRange(header: string | undefined, size: number): [number, number] | null {
  const match = header ? /^bytes=(\d*)-(\d*)$/.exec(header) : null
  if (!match || (match[1] === '' && match[2] === '')) {
    return null
  }
  // "bytes=-500" is the last 500 bytes; "bytes=-0" asks for nothing.
  const start = match[1] === '' ? Math.max(0, size - Number(match[2])) : Number(match[1])
  const end = match[1] === '' || match[2] === '' ? size - 1 : Math.min(Number(match[2]), size - 1)
  return start <= end ? [start, end] : null
}

/** Answer a request under /assets/; false when the path is not ours. */
export function serveAsset(req: IncomingMessage, res: ServerResponse, pathname: string): boolean {
  if (!pathname.startsWith(PREFIX)) {
    return false
  }
  if (req.method === 'OPTIONS') {
    res.writeHead(204, CORS).end()
    return true
  }
  const token = pathname.slice(PREFIX.length).replace(/\.wav$/, '')
  const audio = narration.get(token)
  if (!audio || (req.method !== 'GET' && req.method !== 'HEAD')) {
    res.writeHead(404, CORS).end()
    return true
  }
  const range = req.headers.range ? parseRange(req.headers.range, audio.length) : null
  if (req.headers.range && !range) {
    res.writeHead(416, { ...CORS, 'Content-Range': `bytes */${audio.length}` }).end()
    return true
  }
  const [start, end] = range ?? [0, audio.length - 1]
  const headers = {
    ...CORS,
    'Accept-Ranges': 'bytes',
    'Content-Type': 'audio/wav',
    'Content-Length': String(end - start + 1),
    ...(range ? { 'Content-Range': `bytes ${start}-${end}/${audio.length}` } : {}),
  }
  res.writeHead(range ? 206 : 200, headers)
  res.end(req.method === 'HEAD' ? undefined : audio.subarray(start, end + 1))
  return true
}
