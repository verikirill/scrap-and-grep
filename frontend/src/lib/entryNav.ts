/** Asked of the sections when an entry is folded away: the one that holds it opens. */
export const REVEAL_EVENT = 'radar:reveal-entry'
const UNFOLD_MS = 340

function scrollAndBlink(entry: HTMLElement) {
  entry.scrollIntoView({ behavior: 'smooth', block: 'center' })
  entry.animate(
    [
      { backgroundColor: 'color-mix(in oklab, var(--accent) 16%, transparent)' },
      { backgroundColor: 'transparent' },
    ],
    { duration: 1600, easing: 'ease-out', delay: 350 },
  )
}

/**
 * Scrolls to a digest entry by its number and makes it blink, so the eye
 * finds it. An entry in a folded section or past «Ещё N» is not on the page:
 * its section opens first, and the scroll follows once it has drawn.
 */
export function showEntry(number: number) {
  const entry = document.getElementById(`entry-${number}`)
  if (entry) {
    scrollAndBlink(entry)
    return
  }
  window.dispatchEvent(new CustomEvent<number>(REVEAL_EVENT, { detail: number }))
  let tries = 0
  const wait = () => {
    const shown = document.getElementById(`entry-${number}`)
    // The section unfolds over 0,28 s: a scroll before that lands short.
    if (shown) window.setTimeout(() => scrollAndBlink(shown), UNFOLD_MS)
    else if ((tries += 1) < 20) window.setTimeout(wait, 50)
  }
  window.setTimeout(wait, 50)
}
