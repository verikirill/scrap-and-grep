import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { DURATION } from '../components/tokens'
import { THEME_KEY, prefersDark } from './theme'

/** How long the colours of one theme take to fade into the other. */
const THEME_FADE_MS = DURATION.medium * 1000
/**
 * On <html> while the new theme sweeps across the screen from corner to corner
 * (index.css). The sweep is a CSS animation of ::view-transition-new(root):
 * Firefox does not run element.animate() on that pseudo-element.
 */
const THEME_SWEEP_CLASS = 'theme-sweeping'
/** On <html> while the colours fade without view transitions (index.css). */
const THEME_FADE_CLASS = 'theme-fading'

export function useDarkMode(): [boolean, () => void] {
  const [dark, setDark] = useState(prefersDark)
  const fadeTimer = useRef<number | undefined>(undefined)
  useLayoutEffect(() => {
    const root = document.documentElement
    // Outside a fade every colour changes in one frame: with each element's
    // own transitions on, text and chips lagged behind the backgrounds.
    const isFading = root.classList.contains(THEME_FADE_CLASS)
    if (!isFading) root.classList.add('theme-switching')
    root.classList.toggle('dark', dark)
    void root.offsetHeight
    root.classList.remove('theme-switching')
    localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light')
  }, [dark])
  useEffect(
    () => () => {
      window.clearTimeout(fadeTimer.current)
      document.documentElement.classList.remove(THEME_FADE_CLASS)
    },
    [],
  )
  // The new theme sweeps over the old one from corner to corner. The first
  // paint and a reader who turned motion down get the theme at once.
  const toggle = () => {
    const flip = () => flushSync(() => setDark((value) => !value))
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      flip()
      return
    }
    if (document.startViewTransition) {
      // A picture of the new page is uncovered over a picture of the old one,
      // which stays still underneath: nothing fades, so nothing flickers.
      const root = document.documentElement
      root.classList.add(THEME_SWEEP_CLASS)
      document
        .startViewTransition(flip)
        // Skipped (another transition began): the theme has changed all the same.
        .finished.catch(() => {})
        .finally(() => root.classList.remove(THEME_SWEEP_CLASS))
      return
    }
    // Without view transitions every element eases its own colours for a moment.
    const root = document.documentElement
    window.clearTimeout(fadeTimer.current)
    root.classList.add(THEME_FADE_CLASS)
    flip()
    fadeTimer.current = window.setTimeout(
      () => root.classList.remove(THEME_FADE_CLASS),
      THEME_FADE_MS,
    )
  }
  return [dark, toggle]
}
