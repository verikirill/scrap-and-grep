import { z } from 'zod'

// Props come from the backend over HTTP, so they are checked here before a
// browser is started for them. The limits are what fits on a 1080x1920 frame
// and in a two minute short, with room to spare.
export const MAX_DURATION_MS = 120_000
const ms = z.number().int().min(0).max(MAX_DURATION_MS)
const line = (max: number) => z.string().trim().min(1).max(max)

/** What the news is about; picks the picture and the colour of its card. */
export const VISUALS = [
  'vulnerability',
  'attack',
  'incident',
  'regulation',
  'release',
  'research',
  'energy',
  'other',
] as const

// The QR code on the card: a plain web address, short enough to stay
// readable as a code on a phone screen.
const MAX_URL = 400
const sourceUrl = z
  .string()
  .max(MAX_URL)
  .refine((value) => /^https?:\/\/[^\s]+$/i.test(value), 'the source address must be http or https')

export const beatSchema = z
  .object({
    /** Two or three words above the title, e.g. "Уязвимость". */
    kicker: line(40),
    /** The headline as shown, up to about eight words. */
    title: line(140),
    /** A number or identifier worth a big card, e.g. "CVE-2026-20411"; null when there is none. */
    fact: line(32).nullable(),
    visual: z.enum(VISUALS),
    /** Up to three short facts shown one by one while the item is narrated. */
    points: z.array(line(60)).max(3),
    source: line(60),
    /** The article itself, for the QR code; null when there is no usable address. */
    url: sourceUrl.nullable(),
    /** When it was published, e.g. "29 сентября". */
    date: line(24).nullable(),
    startMs: ms,
    endMs: ms,
  })
  .refine((beat) => beat.startMs < beat.endMs, 'a beat must end after it starts')

/** A spoken word with its place on the audio timeline. */
export const wordSchema = z
  .object({ text: line(40), startMs: ms, endMs: ms })
  .refine((word) => word.startMs <= word.endMs, 'a word must end after it starts')

export const shortSchema = z
  .object({
    brand: line(24),
    /** The period of the digest, e.g. "23-30 сентября". */
    period: line(40),
    /** Who the digest is for, e.g. the profile name. */
    audience: line(40),
    hook: line(120),
    hookEndMs: ms,
    beats: z.array(beatSchema).min(1).max(7),
    outro: line(120),
    outroStartMs: ms,
    words: z.array(wordSchema).max(800),
    /** URL of the narration; null renders a silent video with the same timing. */
    audioSrc: z.string().nullable(),
    durationMs: ms.min(1000),
  })
  .refine(isInOrder, {
    message: 'the hook, the beats and the outro must follow each other within the duration',
  })

type Timeline = {
  hookEndMs: number
  beats: { startMs: number; endMs: number }[]
  outroStartMs: number
  durationMs: number
}

/** Hook, then each beat after the one before, then the outro, all inside the video. */
function isInOrder({ hookEndMs, beats, outroStartMs, durationMs }: Timeline): boolean {
  let at = hookEndMs
  for (const beat of beats) {
    if (beat.startMs < at) {
      return false
    }
    at = beat.endMs
  }
  return at <= outroStartMs && outroStartMs <= durationMs
}
