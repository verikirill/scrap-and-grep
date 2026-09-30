/** Colours and type of the short: the product's night palette, louder. */
export const COLORS = {
  ink: '#070a12',
  surface: '#101624',
  line: 'rgba(255, 255, 255, 0.08)',
  text: '#f2f5fb',
  muted: 'rgba(242, 245, 251, 0.62)',
  accent: '#7d9bff',
  spark: '#f5b54a',
  // The karaoke highlight: the colour every short-video viewer reads as "now".
  caption: '#ffe14d',
} as const

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
