// What stands in for a reader's picture while there is no photo: one of the
// nine ready pictures, or, where none is known, the initials of the name on a
// hue of its own. Both stay the same on every visit.
import type { AvatarPreset } from './api'

/** The ready pictures in the order the picker shows them, with names for screen readers. */
export const AVATAR_PRESETS: readonly { key: AvatarPreset; label: string }[] = [
  { key: 'green', label: 'Зелёный' },
  { key: 'teal', label: 'Бирюзовый' },
  { key: 'sky', label: 'Голубой' },
  { key: 'blue', label: 'Синий' },
  { key: 'purple', label: 'Фиолетовый' },
  { key: 'red', label: 'Красный' },
  { key: 'orange', label: 'Оранжевый' },
  { key: 'yellow', label: 'Жёлтый' },
  { key: 'grey', label: 'Серый' },
]

/** The picture's address and its twice-as-sharp copy for dense screens. */
export function presetImage(preset: AvatarPreset): { src: string; srcSet: string } {
  const base = `/brand/avatars/${preset}`
  return { src: `${base}.webp`, srcSet: `${base}.webp 1x, ${base}@2x.webp 2x` }
}

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
