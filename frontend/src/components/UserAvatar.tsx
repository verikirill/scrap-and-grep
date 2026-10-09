import clsx from 'clsx'
import { useState } from 'react'
import type { Me } from '../lib/api'

type Props = {
  me: Pick<Me, 'display_name' | 'avatar_url'>
  size: number
  className?: string
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

/**
 * The reader's picture, or their initials on a soft gradient of a hue of
 * their own while there is none: two readers without a picture look apart.
 */
export function UserAvatar({ me, size, className }: Props) {
  // A picture that failed to load falls back to the initials, until a new one is set.
  const [broken, setBroken] = useState<string | null>(null)
  if (me.avatar_url && broken !== me.avatar_url) {
    return (
      <img
        src={me.avatar_url}
        alt=""
        width={size}
        height={size}
        decoding="async"
        onError={() => setBroken(me.avatar_url)}
        className={clsx('shrink-0 rounded-full object-cover', className)}
        style={{ width: size, height: size }}
      />
    )
  }
  const hue = nameHue(me.display_name)
  return (
    <span
      aria-hidden
      className={clsx(
        'grid shrink-0 place-items-center rounded-full leading-none font-semibold tracking-tight text-white select-none',
        'shadow-[inset_0_0_0_1px_rgb(255_255_255/0.22),inset_0_1px_0_rgb(255_255_255/0.25)]',
        className,
      )}
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.38),
        background: `linear-gradient(135deg, oklch(0.74 0.13 ${hue}), oklch(0.55 0.17 ${(hue + 45) % 360}))`,
        textShadow: '0 1px 2px rgb(0 0 0 / 0.18)',
      }}
    >
      {nameInitials(me.display_name)}
    </span>
  )
}
