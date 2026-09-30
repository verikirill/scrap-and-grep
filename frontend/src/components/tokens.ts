/** Shared easing: quick start, soft landing. Used for every entrance. */
export const EASE = [0.22, 1, 0.36, 1] as const

export const INPUT_CLASS =
  'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-text ' +
  'placeholder:text-faint transition-colors hover:border-faint focus:border-accent focus:outline-none'

/** Entrance for list rows: fade and rise, staggered only for the first screen. */
export function rowMotion(index: number) {
  return {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.35, ease: EASE, delay: Math.min(index, 10) * 0.035 },
  }
}

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-white shadow-sm hover:brightness-110 dark:text-[#0b0f17]',
  secondary: 'bg-surface text-text border border-line hover:border-faint',
  ghost: 'text-muted hover:text-text hover:bg-sunken',
  danger: 'text-danger hover:bg-danger-soft',
}

/** Button look for anything clickable: a real button, a download link, a route link. */
export function buttonClass(
  variant: ButtonVariant = 'secondary',
  size: 'sm' | 'md' = 'md',
): string {
  return [
    'inline-flex items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap',
    'transition-[filter,background-color,border-color,color,transform] duration-150',
    'active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50',
    size === 'sm' ? 'h-8 px-2.5 text-[13px]' : 'h-10 px-4 text-sm',
    BUTTON_STYLES[variant],
  ].join(' ')
}

/** Short random id. crypto.randomUUID is unavailable on plain-http LAN addresses. */
export function shortId(): string {
  return Math.random().toString(36).slice(2, 10)
}
