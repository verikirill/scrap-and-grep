import { PALETTE } from './palette.ts'

/**
 * Colours and type of the short: the dark Material roles of the web app
 * (palette.ts is generated from the same seed), so a video and the site look
 * like one product. Only the karaoke highlight is the video's own.
 */
export const COLORS = {
  ink: PALETTE.surfaceContainerLowest,
  surface: PALETTE.surfaceContainer,
  line: 'rgba(255, 255, 255, 0.08)',
  text: PALETTE.onSurface,
  muted: PALETTE.onSurfaceVariant,
  accent: PALETTE.primary,
  spark: PALETTE.spark,
  // The karaoke highlight: the colour every short-video viewer reads as "now".
  caption: '#ffe14d',
} as const

/** A #rrggbb colour with its opacity, for gradients and glows. */
export function alpha(color: string, share: number): string {
  const byte = Math.round(Math.min(1, Math.max(0, share)) * 255)
  return `${color}${byte.toString(16).padStart(2, '0')}`
}

export const DISPLAY_FONT = 'Unbounded'
export const TEXT_FONT = 'Onest'

export const WIDTH = 1080
export const HEIGHT = 1920
export const FPS = 30

/** Space the platforms cover with their own buttons and captions. */
export const SAFE = {
  top: 170,
  bottom: 380,
  side: 72,
} as const
