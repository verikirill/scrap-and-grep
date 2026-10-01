import { z } from 'zod'
import { shortSchema } from '../src/schema.ts'
import type { ShortProps } from '../src/types.ts'
import { isWav, pictureType } from './assets.ts'
import { HttpError } from './http.ts'

// A news picture is a few hundred kilobytes; the backend leaves out larger
// ones, so a bigger one here is a mistake, not a picture worth waiting for.
export const MAX_PICTURE_BYTES = 3 * 1024 * 1024

const requestSchema = z.object({
  props: z.record(z.string(), z.unknown()),
  audio: z.string().nullable(),
  // One per beat, in order: base64 of a JPEG, PNG or WebP, or null.
  images: z.array(z.string().nullable()).max(7).default([]),
})

export type Picture = { data: Buffer; type: string; extension: string }
export type Job = { props: ShortProps; audio: Buffer | null; pictures: (Picture | null)[] }

function picture(encoded: string | null, index: number): Picture | null {
  if (encoded === null) {
    return null
  }
  // Four base64 characters carry three bytes; checked before decoding.
  if ((encoded.length / 4) * 3 > MAX_PICTURE_BYTES) {
    throw new HttpError(413, `picture ${index + 1} is too large`)
  }
  const data = Buffer.from(encoded, 'base64')
  const kind = pictureType(data)
  if (!kind) {
    throw new HttpError(400, `picture ${index + 1} is not a JPEG, PNG or WebP file`)
  }
  return { data, ...kind }
}

/** The render request, checked: props, narration and the pictures of the beats. */
export function parseRequest(body: Buffer): Job {
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
  // The audio and picture addresses are ours to give, whatever the caller sent.
  const parsed = shortSchema.safeParse({ ...request.data.props, audioSrc: null })
  if (!parsed.success) {
    throw new HttpError(400, z.prettifyError(parsed.error))
  }
  const props = { ...parsed.data, beats: parsed.data.beats.map((beat) => ({ ...beat, imageSrc: null })) }
  if (request.data.images.length > props.beats.length) {
    throw new HttpError(400, 'more pictures than news items')
  }
  const audio = request.data.audio === null ? null : Buffer.from(request.data.audio, 'base64')
  if (audio && !isWav(audio)) {
    throw new HttpError(400, 'audio must be a WAV file')
  }
  return { props, audio, pictures: request.data.images.map(picture) }
}
