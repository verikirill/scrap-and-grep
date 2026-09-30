import type { z } from 'zod'
import type { beatSchema, shortSchema, wordSchema } from './schema'

/** One news item of the short: what is on screen while it is narrated. */
export type Beat = z.infer<typeof beatSchema>
export type Word = z.infer<typeof wordSchema>
export type ShortProps = z.infer<typeof shortSchema>
