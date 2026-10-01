import { randomBytes } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'

// Narration and pictures of the renders in progress. The headless browser
// that draws the frames fetches them over HTTP from this same process, so
// nothing touches the disk, and the entries disappear when the render ends.
const held = new Map<string, { data: Buffer; type: string }>()

const PREFIX = '/assets/'
const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])

export function isWav(data: Buffer): boolean {
  return (
    data.length > 44 &&
    data.toString('latin1', 0, 4) === 'RIFF' &&
    data.toString('latin1', 8, 12) === 'WAVE'
  )
}

/**
 * The kind of a still picture by its first bytes, whatever the caller says.
 * GIF is left out: its animation would run on the browser's clock, not the
 * video's, and differ between renders.
 */
export function pictureType(data: Buffer): { type: string; extension: string } | null {
  if (data.length > 3 && data[0] === 0xff && data[1] === 0xd8 && data[2] === 0xff) {
    return { type: 'image/jpeg', extension: 'jpg' }
  }
  if (data.subarray(0, PNG.length).equals(PNG)) {
    return { type: 'image/png', extension: 'png' }
  }
  if (data.length > 12 && data.toString('latin1', 0, 4) === 'RIFF' && data.toString('latin1', 8, 12) === 'WEBP') {
    return { type: 'image/webp', extension: 'webp' }
  }
  return null
}

/** Keep a file for one render and return its path; call the result to drop it. */
export function hold(data: Buffer, type: string, extension: string): { path: string; release: () => void } {
  const token = randomBytes(16).toString('hex')
  held.set(token, { data, type })
  return { path: `${PREFIX}${token}.${extension}`, release: () => held.delete(token) }
}

// The browser reads the files with range requests, and from another origin
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
  const token = pathname.slice(PREFIX.length).replace(/\.[a-z0-9]+$/, '')
  const asset = held.get(token)
  if (!asset || (req.method !== 'GET' && req.method !== 'HEAD')) {
    res.writeHead(404, CORS).end()
    return true
  }
  const { data, type } = asset
  const range = req.headers.range ? parseRange(req.headers.range, data.length) : null
  if (req.headers.range && !range) {
    res.writeHead(416, { ...CORS, 'Content-Range': `bytes */${data.length}` }).end()
    return true
  }
  const [start, end] = range ?? [0, data.length - 1]
  const headers = {
    ...CORS,
    'Accept-Ranges': 'bytes',
    'Content-Type': type,
    'Content-Length': String(end - start + 1),
    ...(range ? { 'Content-Range': `bytes ${start}-${end}/${data.length}` } : {}),
  }
  res.writeHead(range ? 206 : 200, headers)
  res.end(req.method === 'HEAD' ? undefined : data.subarray(start, end + 1))
  return true
}
