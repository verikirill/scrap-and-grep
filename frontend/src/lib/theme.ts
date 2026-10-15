/** Where the reader's choice of theme is remembered. */
export const THEME_KEY = 'radar-theme'

/** The theme to start with: the reader's own choice, or else the system's. */
export function prefersDark(): boolean {
  const stored = localStorage.getItem(THEME_KEY)
  if (stored) return stored === 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}
