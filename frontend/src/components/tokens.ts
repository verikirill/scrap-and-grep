/** Ease-out for entrances: quick start, long soft landing, as HeroUI's own motion. */
export const EASE = [0.22, 1, 0.36, 1] as const
/** Durations, in seconds. */
export const DURATION = { short: 0.2, medium: 0.3, long: 0.45 } as const

/** HeroUI text field on a plain <input>: the field background, no border, a focus ring. */
export const INPUT_CLASS = 'input input--full-width w-full'

/**
 * The same field, multi-line: HeroUI textarea that grows with its text
 * instead of scrolling inside a fixed height.
 */
export const TEXTAREA_CLASS =
  'textarea textarea--full-width w-full min-h-20 field-sizing-content resize-y'

/**
 * Entrance for list rows: fade and rise, staggered only for the first screen.
 * A quiet row is just there, as in a list the reader switched back to.
 */
export function rowMotion(index: number, isQuiet = false) {
  return {
    initial: isQuiet ? false : { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: DURATION.medium, ease: EASE, delay: Math.min(index, 10) * 0.035 },
  }
}

export type ButtonVariant = 'primary' | 'tonal' | 'secondary' | 'ghost' | 'danger' | 'cta'

// Our names for HeroUI's button variants: filled accent, soft, outlined, text, and danger;
// cta is the one main action of a screen, a skewed slab of the accent (index.css).
const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: 'button--primary',
  tonal: 'button--secondary',
  secondary: 'button--outline',
  ghost: 'button--ghost',
  danger: 'button--danger-soft',
  cta: 'cta',
}

/** Button look for anything clickable: a real button, a download link, a route link. */
export function buttonClass(
  variant: ButtonVariant = 'secondary',
  size: 'sm' | 'md' = 'md',
): string {
  return [
    'button',
    size === 'sm' ? 'button--sm' : 'button--md',
    BUTTON_VARIANTS[variant],
    'whitespace-nowrap select-none',
  ].join(' ')
}

/** Short random id. crypto.randomUUID is unavailable on plain-http LAN addresses. */
export function shortId(): string {
  return Math.random().toString(36).slice(2, 10)
}
