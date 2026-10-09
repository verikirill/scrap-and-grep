/** Scrolls to a digest entry by its number and makes it blink, so the eye finds it. */
export function showEntry(number: number) {
  const entry = document.getElementById(`entry-${number}`)
  if (!entry) return
  entry.scrollIntoView({ behavior: 'smooth', block: 'center' })
  entry.animate(
    [
      { backgroundColor: 'color-mix(in oklab, var(--accent) 16%, transparent)' },
      { backgroundColor: 'transparent' },
    ],
    { duration: 1600, easing: 'ease-out', delay: 350 },
  )
}
