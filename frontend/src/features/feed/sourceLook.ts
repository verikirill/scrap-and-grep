// Tag colours a source can get (styles/tags.css); grey is left out.
const TINTS = ['blue', 'violet', 'teal', 'green', 'amber', 'orange', 'red', 'pink'] as const

/** A source's colour, the same wherever it shows: its avatar and its name. */
export const sourceTint = (sourceId: number) => TINTS[Math.abs(sourceId) % TINTS.length]

/** Up to two letters for an avatar, as Telegram draws a chat without a photo. */
export function initials(name: string): string {
  const words = name.split(/[^\p{L}\p{N}]+/u).filter(Boolean)
  return (
    words
      .slice(0, 2)
      .map((word) => word[0])
      .join('')
      .toUpperCase() || '?'
  )
}
