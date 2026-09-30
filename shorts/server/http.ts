import type { IncomingMessage, ServerResponse } from 'node:http'

export class HttpError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Read the whole body, refusing it as soon as it grows past the limit. */
export async function readBody(req: IncomingMessage, limit: number): Promise<Buffer> {
  if (Number(req.headers['content-length'] ?? 0) > limit) {
    throw new HttpError(413, `the body is larger than ${limit} bytes`)
  }
  const chunks: Buffer[] = []
  let size = 0
  for await (const chunk of req) {
    const part = chunk as Buffer
    size += part.length
    if (size > limit) {
      throw new HttpError(413, `the body is larger than ${limit} bytes`)
    }
    chunks.push(part)
  }
  return Buffer.concat(chunks)
}

export function sendJson(res: ServerResponse, status: number, body: unknown, headers: Record<string, string> = {}) {
  const data = JSON.stringify(body)
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': String(Buffer.byteLength(data)),
    ...headers,
  })
  res.end(data)
}

/** One JSON line per event on stdout, for docker logs. */
export function log(event: string, fields: Record<string, unknown> = {}): void {
  process.stdout.write(`${JSON.stringify({ time: new Date().toISOString(), event, ...fields })}\n`)
}
