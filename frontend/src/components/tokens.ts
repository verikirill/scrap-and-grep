/** Material 3 emphasized easing: quick start, long soft landing. Every entrance uses it. */
export const EASE = [0.2, 0, 0, 1] as const
/** Material 3 durations, in seconds. */
export const DURATION = { short: 0.2, medium: 0.3, long: 0.45 } as const

/** Material 3 outlined text field. */
export const INPUT_CLASS =
  'w-full h-11 rounded-xl border border-outline bg-transparent px-3.5 text-sm text-foreground ' +
  'placeholder:text-outline transition-[border-color,box-shadow] duration-200 ' +
  'hover:border-on-surface focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary ' +
  'disabled:opacity-40'

/**
 * The same field, multi-line. The text sits as far from the top edge as from
 * the left (12px of padding plus the half-leading of a 20px line ≈ 14px), and
 * the box grows with its text instead of scrolling inside a fixed height.
 */
export const TEXTAREA_CLASS =
  INPUT_CLASS + ' h-auto min-h-20 py-3 leading-5 field-sizing-content resize-y'

/** Entrance for list rows: fade and rise, staggered only for the first screen. */
export function rowMotion(index: number) {
  return {
    initial: { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: DURATION.medium, ease: EASE, delay: Math.min(index, 10) * 0.035 },
  }
}

export type ButtonVariant = 'primary' | 'tonal' | 'secondary' | 'ghost' | 'danger'

// Material 3 buttons: filled, tonal, outlined, text, and text in the error role.
const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-primary-foreground hover:shadow-elevation-1',
  tonal: 'bg-secondary-container text-on-secondary-container hover:shadow-elevation-1',
  secondary: 'border border-outline text-primary',
  ghost: 'text-primary',
  danger: 'text-destructive',
}

/** Button look for anything clickable: a real button, a download link, a route link. */
export function buttonClass(
  variant: ButtonVariant = 'secondary',
  size: 'sm' | 'md' = 'md',
): string {
  return [
    'state-layer relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full',
    'font-medium tracking-[0.01em] whitespace-nowrap select-none',
    'transition-[box-shadow,background-color,color,opacity] duration-200',
    'disabled:pointer-events-none disabled:opacity-40',
    size === 'sm' ? 'h-8 px-3.5 text-[13px]' : 'h-10 px-5 text-sm',
    BUTTON_STYLES[variant],
  ].join(' ')
}

/** Short random id. crypto.randomUUID is unavailable on plain-http LAN addresses. */
export function shortId(): string {
  return Math.random().toString(36).slice(2, 10)
}
