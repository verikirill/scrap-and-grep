// What stands in for a reader's picture while there is none: the initials of
// the name on a hue of its own. Both come from the name, so they stay the same
// on every visit.

/** Up to two letters of a name: «Анна Петрова» -> «АП», «Гость» -> «Г». */
export function nameInitials(name: string): string {
  const words = name.split(/[^\p{L}\p{N}]+/u).filter(Boolean)
  return (
    words
      .slice(0, 2)
      .map((word) => word[0])
      .join('')
      .toUpperCase() || '?'
  )
}

/** A hue of the reader's own, the same on every visit: from the name, not at random. */
export function nameHue(name: string): number {
  let seed = 7
  for (const char of name) seed = (seed * 31 + char.charCodeAt(0)) % 3600
  return seed % 360
}
